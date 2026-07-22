from __future__ import annotations

from typing import Any

from .agents import RCAAgent, RecoveryAgent, RemediationAgent, SafetyAgent
from .backend import SimulatedOperationsBackend
from .models import Incident, IncidentStatus
from .skills import correlate_alerts


class IncidentCommander:
    """Local equivalent of the AgentTeams Manager coordination contract."""

    def __init__(self, scenario: dict[str, Any]):
        self.backend = SimulatedOperationsBackend(scenario)
        self.rca = RCAAgent()
        self.safety = SafetyAgent()
        self.remediation = RemediationAgent()
        self.recovery = RecoveryAgent()

    def run(self, raw_alerts: list[dict[str, Any]]) -> tuple[Incident, str]:
        incident = correlate_alerts(raw_alerts)
        # The local adapter attaches shared state exactly where AgentTeams would
        # persist an incident context artifact for Manager and Workers.
        object.__setattr__(incident, "_scenario_context", self.backend.scenario)
        incident.record("Incident Commander", "incident_opened")
        self.rca.run(incident, self.backend)
        self.remediation.plan(incident)

        if not self.safety.authorize(incident):
            incident.record("Incident Commander", "human_approval_requested")
            return incident, self.recovery.postmortem(incident)

        self.remediation.execute(incident, self.backend)
        self.recovery.verify(incident, self.backend)
        if incident.verification and incident.verification.passed:
            incident.status = IncidentStatus.RECOVERED
            incident.record("Incident Commander", "incident_resolved")
        else:
            rollback = self.backend.rollback()
            incident.status = IncidentStatus.ROLLED_BACK
            incident.record("Incident Commander", "automatic_rollback_completed", result=rollback)
        return incident, self.recovery.postmortem(incident)
