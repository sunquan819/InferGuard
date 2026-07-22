# Postmortem: INC-9E09B42554

- Service: qwen-inference
- Status: recovered
- Root cause: canary max_model_len expansion exhausted v2 KV cache capacity (89% confidence)
- Evidence: EV-001, EV-002, EV-003, EV-004
- Remediation: rollback_canary_revision
- Verification: all SLO checks passed

## Preventive action
Add a pre-release capacity check that estimates KV cache concurrency whenever max_model_len changes.

## Reusable runbook candidate
When TTFT and preemption regress only on a canary route while GPU health is normal, drain canary traffic in 10% steps, restore the last-known-good revision, and verify both performance and answer quality SLOs.
