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

## Recorded counts (2026-06-03)

- Backend pytest: 897 passed, 0 failed, 1 skipped, 6 xfailed baseline anchors
- Harness: 6/6

Re-run after any control-plane change; update counts when the suite grows.

## Chat control-plane suites

Default flag-off baseline:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_current_chat_runtime_baseline.py -v
```

Expected: six xfailed behavioral snapshots after schema checks, zero errors.

Flag-on golden suite:

```bash
cd backend
CONTROL_PLANE_ENABLED=true PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_control_plane_golden.py -q
```

Expected: seven passed, no xfail. The suite asserts intent, evidence plan, route adjudication, SPL/MCP gating, MITRE visibility, response/synthesis mode, and `control_plane_trace`.

Phase-specific modules added by the control plane:

- `test_current_chat_runtime_baseline.py`
- `test_query_to_intent.py`
- `test_evidence_planner.py`
- `test_evidence_plan_rag_only_skip.py`
- `test_route_adjudication.py`
- `test_llm_plan_validator.py`
- `test_spl_slot_binding_validator.py`
- `test_mitre_decision_runtime.py`
- `test_response_synthesis_honesty.py`
- `test_control_plane_trace.py`
- `test_chat_control_plane_golden.py`

## Boundaries enforced

- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` (production defaults)
- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- No live LLM / no live Splunk in this script
- Pattern #2 not allowlisted
