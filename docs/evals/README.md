# Stage 3L / 3M Evaluations

Governance regression and shadow-route evaluation for Experience Center / coverage work. **No live MCP, no live LLM, no route authority expansion, no SPL execution.**

## Quick start

```bash
# Full regression (pytest, harness, audits, cov.q046 baseline, fail-closed MCP, 105-Q eval)
./scripts/run_stage3_governance_regression.sh

# 105-question shadow eval only
python3 scripts/eval_stage3l_105_question_shadow_routes.py
```

Outputs land under [`docs/evals/out/`](out/) (gitignored except `.gitkeep`).

Expected green counts: [`regression_baseline.md`](regression_baseline.md).

## Scripts

| Script | Purpose |
|--------|---------|
| [`scripts/run_stage3_governance_regression.sh`](../../scripts/run_stage3_governance_regression.sh) | CI/local regression bundle |
| [`scripts/eval_stage3l_105_question_shadow_routes.py`](../../scripts/eval_stage3l_105_question_shadow_routes.py) | 105-Q shadow governance eval |

## Inputs

- [`docs/stage3l_s6_105_question_operation_map.json`](../stage3l_s6_105_question_operation_map.json) — S6.2 provisional report (105 questions)
- [`backend/app/coverage/question_runtime_map_v1.json`](../../backend/app/coverage/question_runtime_map_v1.json) — S6.1 runtime map (via `question_runtime_entry`)

## Constraints (enforced)

- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false`
- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- `DEMO_LLM_SHADOW_ENABLED=false` (eval script guard)
- Deterministic router only for legacy `selected_skill` observation
- No Hugging Face / no real Splunk

## Related docs

- [stage3_eval_matrix.md](stage3_eval_matrix.md) — pass/fail rules per bucket
- [../stage3l_s8_governance_readiness_freeze.md](../stage3l_s8_governance_readiness_freeze.md) — frozen boundaries
