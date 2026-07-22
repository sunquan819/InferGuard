from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import ActionPlan, Evidence, utc_now


class SimulatedOperationsBackend:
    """Deterministic backend with the same boundary as future MCP tools."""

    ALLOWED_ACTIONS = {
        "rollback_canary_revision",
        "shift_canary_traffic",
        "update_config",
        "restart_single_pod",
        "rollback_upstream_schema",
    }

    def __init__(self, scenario: dict[str, Any]):
        self.scenario = scenario
        self.state = deepcopy(scenario["runtime_state"])
        self.before_action: dict[str, Any] | None = None
        self.executed_keys: set[str] = set()

    def collect_evidence(self) -> list[Evidence]:
        items: list[Evidence] = []
        for index, item in enumerate(self.scenario["evidence"], start=1):
            items.append(
                Evidence(
                    evidence_id=f"EV-{index:03d}",
                    kind=item["kind"],
                    source=item["source"],
                    observed_at=item["observed_at"],
                    summary=item["summary"],
                    data=item.get("data", {}),
                )
            )
        return items

    def current_sli(self) -> dict[str, float]:
        return {
            metric: float(self.state[metric])
            for metric in self.scenario["slo"]
        }

    def execute(self, plan: ActionPlan) -> dict[str, Any]:
        if plan.action not in self.ALLOWED_ACTIONS:
            raise PermissionError(f"action not allowlisted: {plan.action}")
        if plan.idempotency_key in self.executed_keys:
            return {"status": "already_applied", "idempotency_key": plan.idempotency_key}

        self.before_action = deepcopy(self.state)
        if plan.action == "restart_single_pod":
            self.state["pod_restarts"] += 1
        else:
            expected = self.scenario["remediation"]
            if plan.action != expected["action"]:
                raise ValueError("action does not match the evidence-backed scenario plan")
            self.state.update(expected["effect"])

        self.executed_keys.add(plan.idempotency_key)
        return {
            "status": "applied",
            "action": plan.action,
            "changed_at": utc_now(),
            "state": deepcopy(self.state),
        }

    def rollback(self) -> dict[str, Any]:
        if self.before_action is None:
            return {"status": "noop", "reason": "no action to roll back"}
        self.state = self.before_action
        self.before_action = None
        return {"status": "rolled_back", "state": deepcopy(self.state)}

    def slo_contract(self) -> dict[str, dict[str, float | str]]:
        return deepcopy(self.scenario["slo"])
