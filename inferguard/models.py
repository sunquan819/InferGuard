from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    PLANNED = "planned"
    AUTHORIZED = "authorized"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RECOVERED = "recovered"
    ROLLED_BACK = "rolled_back"
    ESCALATED = "escalated"


class RiskLevel(StrEnum):
    L0 = "L0-readonly"
    L1 = "L1-low-reversible"
    L2 = "L2-approval-required"
    L3 = "L3-prohibited"


@dataclass(slots=True)
class Alert:
    source: str
    service: str
    signal: str
    value: float
    threshold: float
    timestamp: str
    fingerprint: str


@dataclass(slots=True)
class Evidence:
    evidence_id: str
    kind: str
    source: str
    observed_at: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Hypothesis:
    cause: str
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionPlan:
    action_id: str
    action: str
    parameters: dict[str, Any]
    risk: RiskLevel
    reversible: bool
    rollback_action: str
    expected_effect: str
    idempotency_key: str


@dataclass(slots=True)
class Verification:
    passed: bool
    checks: dict[str, bool]
    observed: dict[str, float]
    reason: str


@dataclass(slots=True)
class TraceEvent:
    actor: str
    event: str
    timestamp: str = field(default_factory=utc_now)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    incident_id: str
    title: str
    service: str
    status: IncidentStatus
    alerts: list[Alert]
    started_at: str
    evidence: list[Evidence] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    plan: ActionPlan | None = None
    verification: Verification | None = None
    trace: list[TraceEvent] = field(default_factory=list)

    def record(self, actor: str, event: str, **detail: Any) -> None:
        self.trace.append(TraceEvent(actor=actor, event=event, detail=detail))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
