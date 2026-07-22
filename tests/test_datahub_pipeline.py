import json
import unittest
from pathlib import Path

from inferguard.datahub import ScenarioDataHubContextProvider, _supported_arguments
from inferguard.models import IncidentStatus
from inferguard.orchestrator import IncidentCommander
from inferguard.skills import correlate_alerts


SCENARIO_PATH = (
    Path(__file__).parents[1]
    / "scenarios"
    / "datahub_customer_features_schema_break.json"
)


class DataHubPipelineTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))

    def test_datahub_context_drives_recovery(self):
        incident, postmortem = IncidentCommander(self.scenario).run(
            self.scenario["alerts"]
        )

        self.assertEqual(incident.status, IncidentStatus.RECOVERED)
        self.assertTrue(incident.verification and incident.verification.passed)
        self.assertIn("schema rename", incident.hypotheses[0].cause)
        self.assertIn("DH-003", incident.hypotheses[0].supporting_evidence)
        self.assertIn("lineage-aware schema compatibility gate", postmortem)

    def test_fixture_records_all_required_datahub_tools(self):
        incident = correlate_alerts(self.scenario["alerts"])
        evidence = ScenarioDataHubContextProvider(self.scenario).collect(incident)

        self.assertEqual([item.evidence_id for item in evidence], [
            "DH-001",
            "DH-002",
            "DH-003",
            "DH-004",
        ])
        self.assertEqual(
            {item.data["mcp_tool"] for item in evidence},
            {"search", "get_entities", "get_lineage"},
        )
        self.assertTrue(all(item.data["mode"] == "fixture" for item in evidence))

    def test_live_adapter_maps_server_schema_aliases(self):
        schema = {
            "properties": {
                "source_urn": {"type": "string"},
                "direction": {"type": "string"},
                "maxHops": {"type": "integer"},
            },
            "required": ["source_urn", "direction"],
        }

        arguments = _supported_arguments(
            schema,
            {"urn": "urn:li:dataset:test", "direction": "upstream", "max_hops": 3},
        )

        self.assertEqual(
            arguments,
            {
                "source_urn": "urn:li:dataset:test",
                "direction": "upstream",
                "maxHops": 3,
            },
        )


if __name__ == "__main__":
    unittest.main()
