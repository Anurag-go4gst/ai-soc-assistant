# Plan 6 — P0 baseline (measured 2026-08-13)

Tree: HEAD `1d32ac66dd6c707789db8b44574bd566af401952` on branch `feat/plan6-production-activation`.
`origin/master` is the same SHA. Plan 5 architecture merge is `3d22260` (one docs commit behind this baseline).

Pre-existing unrelated dirt, **excluded** from every Plan 6 change set:
`.claude/settings.local.json`, `backend/app/chat/detail_tools/__init__.py` (whitespace-only empty `__init__.py`), plus untracked `.playwright-mcp/`, `output/`, two `g0-*.png`.

Live VPS flag values are **UNKNOWN until A4**. Local `.env` has `AI_SOC_ENV_PROFILE=development` (not used as VPS evidence).

## Measured

| Gate | Plan 5 closure | Measured at P0 | Verdict |
|---|---|---|---|
| Git SHA | `1d32ac6` branch point | `1d32ac66dd6c707789db8b44574bd566af401952` = `origin/master` | match |
| Protected manifest | `15/15` | **`protected artifacts unchanged (15 checked)`** | match |
| Targeted pytest (Verify) | — | **`37 passed`** (`test_phase_merge_activation` + `test_semantic_t4_understanding` + `test_execution_seam_coverage`) | pass |
| `ai_soc_resource_plan_execution_enabled` | default false | `config.py:410` `= False` | match |
| `ai_soc_t4_semantic_understanding_enabled` | default false | `config.py:413` `= False` | match |
| `ai_soc_live_capability_enforcement_enabled` | default false | `config.py:417` `= False` | match |
| `ai_soc_pipeline_dispatch_v2_enabled` | repo default false; COE true | `config.py:403` `= False`; `env/profiles/coe.env.example:31` `=true` | match |

Full backend pytest and governance regression are **not** P0 Verify. They run at A-GATE / F-GATE / G2.

## Dispatch-v2 vs ResourcePlan execution (do not absorb)

Flipping `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true` on a COE VPS with dispatch-v2 ON does **not** run Plan 5 `merge_schedule`. `backend/app/planner/executor.py` `_execution_driven_schedule_detailed` returns `dispatch_v2_projected_schedule` when a v2 projected schedule exists. Arm C (exec ON, v2 OFF) is the only VPS arm that exercises merge on composed turns.

## What this freeze is not

- Not a claim that ResourcePlan execution is active on the VPS.
- Not a claim that T4 serving works.
- Not a production go-live.
- Frozen truth-set `--arm both` still does not observe L4/L5.
