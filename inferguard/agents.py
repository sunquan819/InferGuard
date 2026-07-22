from __future__ import annotations

from dataclasses import dataclass

from .backend import SimulatedOperationsBackend
from .datahub import DataHubContextProvider
from .models import Incident, IncidentStatus
from .skills import (
    authorize_action,
    build_postmortem,
    collect_incident_evidence,
    plan_remediation,
    rank_root_causes,
    verify_recovery,
)


@dataclass(frozen=True)
class AgentIdentity:
    name: str
    role: str
    permissions: tuple[str, ...]


SIGNAL_ANALYST = AgentIdentity("Signal Analyst", "alert correlation", ("alerts:read",))
RCA_INVESTIGATOR = AgentIdentity(
    "RCA Investigator", "evidence-backed diagnosis", ("metrics:read", "logs:read", "deployments:read")
)
DATA_CONTEXT_ANALYST = AgentIdentity(
    "Data Context Analyst",
    "DataHub metadata and lineage enrichment",
    ("datahub:search", "datahub:entities:read", "datahub:lineage:read"),
)
SAFETY_GOVERNOR = AgentIdentity(
    "Safety Governor", "policy and authorization", ("policy:read", "approval:issue")
)
REMEDIATION_EXECUTOR = AgentIdentity(
    "Remediation Executor", "allowlisted action execution", ("runbook:execute",)
)
RECOVERY_LEARNER = AgentIdentity(
    "Recovery & Learning", "independent recovery validation and learning", ("slo:read", "knowledge:write")
)


class RCAAgent:
    def run(
        self,
        incident: Incident,
        backend: SimulatedOperationsBackend,
        context_provider: DataHubContextProvider | None = None,
    ) -> None:
        collect_incident_evidence(incident, backend)
        if context_provider is not None:
            context_evidence = context_provider.collect(incident)
            incident.evidence.extend(context_evidence)
            if context_evidence:
                incident.record(
                    DATA_CONTEXT_ANALYST.name,
                    "datahub_context_collected",
                    evidence_ids=[item.evidence_id for item in context_evidence],
                    tools=[item.data["mcp_tool"] for item in context_evidence],
                    modes=sorted({item.data["mode"] for item in context_evidence}),
                )
        rank_root_causes(incident)


class SafetyAgent:
    def authorize(self, incident: Incident) -> bool:
        return authorize_action(incident)


class RemediationAgent:
    def plan(self, incident: Incident) -> None:
        plan_remediation(incident)

    def execute(self, incident: Incident, backend: SimulatedOperationsBackend) -> dict:
        if incident.status != IncidentStatus.AUTHORIZED or incident.plan is None:
            raise PermissionError("action requires Safety Governor authorization")
        incident.status = IncidentStatus.REMEDIATING
        result = backend.execute(incident.plan)
        incident.record(self.__class__.__name__, "action_executed", result=result)
        return result


class RecoveryAgent:
    def verify(self, incident: Incident, backend: SimulatedOperationsBackend) -> None:
        incident.status = IncidentStatus.VERIFYING
        incident.verification = verify_recovery(backend)
        incident.record(
            RECOVERY_LEARNER.name,
            "recovery_verified",
            passed=incident.verification.passed,
            observed=incident.verification.observed,
        )

    def postmortem(self, incident: Incident) -> str:
        return build_postmortem(incident)
