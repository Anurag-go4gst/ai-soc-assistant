# Stage 3 governance regression baseline

Canonical command:

```bash
./scripts/run_stage3_governance_regression.sh
```

## Expected green (fail-closed)

| Check | Expected |
|-------|----------|
| Backend pytest | **0 failed** (skipped tests documented only) |
| Test harness | **6/6** cases with `overall_pass=true` |
| Manifest promotion audit | exit 0 |
| 105-question operation map audit | exit 0 |
| cov.q046 baseline JSON | pilot id + ≥2 scenarios |
| cov.q046 Step 7 pytest | all pass |
| cov.q046 observation summary | `status=closed`, `unexpected_disagreement_count=0` |
| Stage 3M-S5 live MCP capture | blocked without flag |
| 105-Q shadow eval | `overall_pass=True` |
| SKILL_ENUM contract test | backend == harness |

## Recorded counts (2026-05-30)

- Backend pytest: ~707 passed, 0 failed, 1 skipped (`UPDATE_OBSERVATION_ARTIFACTS` optional)
- Harness: 6/6

Re-run after any control-plane change; update counts when the suite grows.

## Boundaries enforced

- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` (production defaults)
- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- No live LLM / no live Splunk in this script
- Pattern #2 not allowlisted
