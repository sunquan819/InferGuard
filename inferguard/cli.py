from __future__ import annotations

import argparse
import json
from pathlib import Path

from .orchestrator import IncidentCommander


def load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_demo(scenario_path: Path, output_dir: Path) -> int:
    scenario = load_scenario(scenario_path)
    incident, postmortem = IncidentCommander(scenario).run(scenario["alerts"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "incident.json").write_text(
        json.dumps(incident.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "postmortem.md").write_text(postmortem + "\n", encoding="utf-8")
    summary = {
        "incident_id": incident.incident_id,
        "status": incident.status,
        "top_root_cause": incident.hypotheses[0].cause,
        "confidence": incident.hypotheses[0].confidence,
        "verification": incident.verification.passed if incident.verification else None,
        "trace_events": len(incident.trace),
        "artifacts": str(output_dir.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if str(incident.status) == "recovered" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="InferGuard zero-touch AI inference operations demo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run the deterministic incident demo")
    demo.add_argument(
        "--scenario", type=Path, default=Path("scenarios/inference_kv_cache_regression.json")
    )
    demo.add_argument("--output", type=Path, default=Path("artifacts/latest"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "demo":
        return run_demo(args.scenario, args.output)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
