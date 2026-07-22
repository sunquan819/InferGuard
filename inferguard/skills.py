from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from .backend import SimulatedOperationsBackend
from .models import (
    ActionPlan,
    Alert,
    Hypothesis,
    Incident,
    IncidentStatus,
    RiskLevel,
    Verification,
)


def correlate_alerts(raw_alerts: list[dict[str, Any]]) -> Incident:
    alerts = [Alert(**item) for item in raw_alerts]
    if not alerts:
        raise ValueError("at least one alert is required")
    service_counts = Counter(alert.service for alert in alerts)
    service = service_counts.most_common(1)[0][0]
    unique_fingerprints = {alert.fingerprint for alert in alerts}
    digest = hashlib.sha256(
        f"{service}:{alerts[0].timestamp}:{','.join(sorted(unique_fingerprints))}".encode()
    ).hexdigest()[:10]
    incident = Incident(
        incident_id=f"INC-{digest.upper()}",
        title=f"{service} error rate and latency degradation",
        service=service,
        status=IncidentStatus.DETECTED,
        alerts=alerts,
        started_at=min(alert.timestamp for alert in alerts),
    )
    incident.record(
        "Signal Analyst",
        "alerts_correlated",
        received=len(alerts),
        unique=len(unique_fingerprints),
        compression_ratio=round(len(alerts) / len(unique_fingerprints), 2),
    )
    return incident


def collect_incident_evidence(
    incident: Incident, backend: SimulatedOperationsBackend
) -> None:
    incident.status = IncidentStatus.INVESTIGATING
    incident.evidence = backend.collect_evidence()
    incident.record(
        "RCA Investigator",
        "evidence_collected",
        evidence_ids=[item.evidence_id for item in incident.evidence],
    )


def rank_root_causes(incident: Incident) -> None:
    evidence_by_id = {item.evidence_id: item for item in incident.evidence}
    scenario_hypotheses = incident_context(incident)["diagnosis"]["hypotheses"]
    incident.hypotheses = []
    for candidate in scenario_hypotheses:
        supporting = [eid for eid in candidate["supporting_evidence"] if eid in evidence_by_id]
        contradicting = [eid for eid in candidate.get("contradicting_evidence", []) if eid in evidence_by_id]
        confidence = candidate["base_confidence"] + 0.04 * len(supporting) - 0.03 * len(contradicting)
        incident.hypotheses.append(
            Hypothesis(
                cause=candidate["cause"],
                confidence=min(round(confidence, 2), 0.98),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
            )
        )
    incident.hypotheses.sort(key=lambda item: item.confidence, reverse=True)
    incident.record(
        "RCA Investigator",
        "root_causes_ranked",
        top_cause=incident.hypotheses[0].cause,
        confidence=incident.hypotheses[0].confidence,
        evidence=incident.hypotheses[0].supporting_evidence,
    )


def incident_context(incident: Incident) -> dict[str, Any]:
    context = getattr(incident, "_scenario_context", None)
    if context is None:
        raise RuntimeError("incident is missing scenario context")
    return context


def plan_remediation(incident: Incident) -> None:
    top = incident.hypotheses[0]
    if top.confidence < 0.7:
        raise RuntimeError("insufficient evidence for autonomous remediation")
    remediation = incident_context(incident)["remediation"]
    incident.plan = ActionPlan(
        action_id=f"ACT-{incident.incident_id[4:]}",
        action=remediation["action"],
        parameters=remediation["parameters"],
        risk=RiskLevel(remediation["risk"]),
        reversible=remediation["reversible"],
        rollback_action=remediation["rollback_action"],
        expected_effect=remediation["expected_effect"],
        idempotency_key=f"{incident.incident_id}:{remediation['action']}:{remediation['version']}",
    )
    incident.status = IncidentStatus.PLANNED
    incident.record(
        "Remediation Executor",
        "remediation_planned",
        action=incident.plan.action,
        risk=incident.plan.risk,
        rollback=incident.plan.rollback_action,
    )


def authorize_action(incident: Incident) -> bool:
    plan = incident.plan
    if plan is None:
        raise ValueError("missing remediation plan")
    authorized = (
        plan.risk in {RiskLevel.L0, RiskLevel.L1}
        and plan.reversible
        and plan.action in SimulatedOperationsBackend.ALLOWED_ACTIONS
    )
    incident.record(
        "Safety Governor",
        "action_authorization_decided",
        authorized=authorized,
        risk=plan.risk,
        reversible=plan.reversible,
    )
    incident.status = IncidentStatus.AUTHORIZED if authorized else IncidentStatus.ESCALATED
    return authorized


def verify_recovery(backend: SimulatedOperationsBackend) -> Verification:
    observed = backend.current_sli()
    checks = {}
    for metric, rule in backend.slo_contract().items():
        operator = rule["operator"]
        target = float(rule["target"])
        checks[f"{metric}_{operator}_{target}"] = (
            observed[metric] < target if operator == "lt" else observed[metric] >= target
        )
    passed = all(checks.values())
    return Verification(
        passed=passed,
        checks=checks,
        observed=observed,
        reason="all SLO checks passed" if passed else "one or more SLO checks failed",
    )


def build_postmortem(incident: Incident) -> str:
    top = incident.hypotheses[0]
    learning = incident_context(incident)["learning"]
    return "\n".join(
        [
            f"# Postmortem: {incident.incident_id}",
            "",
            f"- Service: {incident.service}",
            f"- Status: {incident.status}",
            f"- Root cause: {top.cause} ({top.confidence:.0%} confidence)",
            f"- Evidence: {', '.join(top.supporting_evidence)}",
            f"- Remediation: {incident.plan.action if incident.plan else 'none'}",
            f"- Verification: {incident.verification.reason if incident.verification else 'not run'}",
            "",
            "## Preventive action",
            learning["preventive_action"],
            "",
            "## Reusable runbook candidate",
            learning["runbook_candidate"],
        ]
    )
