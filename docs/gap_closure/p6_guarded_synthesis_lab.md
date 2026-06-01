# P6 — Guarded synthesis lab

**Branch:** `stage/p6-guarded-synthesis-lab`

## Goal

Wire flag-gated governed synthesis and Answer Guard execution on live `/chat` without
enabling production LLM calls or changing default behavior.

## Flags (default false)

| Env | Behavior when true |
|-----|-------------------|
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | Build `GovernedSynthesisPackage` and a **deterministic lab draft** from evidence only |
| `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | Run semantic guards on the draft when synthesis produced one |

## Boundaries

- No live LLM synthesis calls in this stage (`provider=deterministic_lab`).
- `execution_eligible` stays false on drafts; MCP execution gates unchanged.
- Flag off: `/chat` matches prior surface (`synthesis_status.disabled`, no `analyst_summary`).
- Guard blocked drafts do not populate `analyst_summary`; HIL may be raised.

## Modules

| Module | Role |
|--------|------|
| `app/synthesis/lab_runner.py` | Sufficiency-gated synthesis lab |
| `app/answer_guard/runner.py` | Guard orchestration |
| `app/chat/pipeline.py` | Live wiring in `graph_node_context_finalize` |

## Verification

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p6_guarded_synthesis_lab.py -q
PYTHONPATH=../backend:.. python3 -m pytest
./scripts/run_stage3_governance_regression.sh
```
