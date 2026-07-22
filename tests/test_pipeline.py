import json
from copy import deepcopy
import unittest
from pathlib import Path

from inferguard.backend import SimulatedOperationsBackend
from inferguard.models import ActionPlan, IncidentStatus, RiskLevel
from inferguard.orchestrator import IncidentCommander
from inferguard.skills import correlate_alerts


SCENARIO_PATH = Path(__file__).parents[1] / "scenarios" / "inference_kv_cache_regression.json"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))

    def test_end_to_end_incident_recovers(self):
        incident, postmortem = IncidentCommander(self.scenario).run(self.scenario["alerts"])
        self.assertEqual(incident.status, IncidentStatus.RECOVERED)
        self.assertTrue(incident.verification and incident.verification.passed)
        self.assertGreaterEqual(incident.hypotheses[0].confidence, 0.7)
        self.assertIn("Reusable runbook candidate", postmortem)

    def test_alerts_are_deduplicated_in_trace(self):
        incident = correlate_alerts(self.scenario["alerts"])
        event = incident.trace[0]
        self.assertEqual(event.detail["received"], 7)
        self.assertEqual(event.detail["unique"], 5)

    def test_backend_rejects_non_allowlisted_action(self):
        backend = SimulatedOperationsBackend(self.scenario)
        unsafe = ActionPlan(
            action_id="unsafe",
            action="delete_database",
            parameters={},
            risk=RiskLevel.L3,
            reversible=False,
            rollback_action="none",
            expected_effect="none",
            idempotency_key="unsafe",
        )
        with self.assertRaises(PermissionError):
            backend.execute(unsafe)

    def test_failed_slo_verification_triggers_rollback(self):
        scenario = deepcopy(self.scenario)
        scenario["remediation"]["effect"]["p99_ttft_ms"] = 1200
        incident, _ = IncidentCommander(scenario).run(scenario["alerts"])
        self.assertEqual(incident.status, IncidentStatus.ROLLED_BACK)
        self.assertFalse(incident.verification and incident.verification.passed)
        self.assertEqual(incident.trace[-1].event, "automatic_rollback_completed")


if __name__ == "__main__":
    unittest.main()
