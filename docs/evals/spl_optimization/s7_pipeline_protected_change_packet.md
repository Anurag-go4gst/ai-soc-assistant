# S7 — Protected change packet (D-S4)

**Plan:** `plans/2026-08-27_optional-phase-s-spl-optimization.md`  
**File:** `backend/app/chat/pipeline.py`  
**Base SHA (7.1):** `11a273653c3acb1a34f715ee417e2d94447b762d`  
**Packet date:** 2026-08-27

## CURRENT

| Site | Behavior |
|---|---|
| `graph_node_spl_source_resolve` ~3572 | `"producer_lineage": "llm_plan_compiler"` hardcoded for all lab-tier derived artifacts |
| `_candidate_from_llm_fallback_tuple` | No `producer_lineage` / `llm_lineage` / optimization trace on candidate |
| Optimization | Layer 2/3 not wired on live LLM candidate path |

## PROPOSED

| Site | Behavior |
|---|---|
| `resolve_producer_lineage(candidate)` | Sticky label: `llm_plan_compiler` \| `llm_fallback` \| `optimization_llm` from candidate metadata |
| `_candidate_from_llm_fallback_tuple` | Run `run_spl_optimization_chain` (Layer 2 always; Layer 3 when `ai_soc_spl_optimization_llm_enabled`); stamp `optimization_trace`, `llm_lineage=True`, `producer_lineage` |
| `graph_node_spl_source_resolve` | Use `resolve_producer_lineage(candidate)` in `llm_derived_spl_artifact` |

## ROLLBACK

Revert the S7 commit; `producer_lineage` returns to hardcoded `llm_plan_compiler`; remove optimization chain call from fallback tuple.

## Governance

- No change to `spl_validator.py` or `policy.py`
- `execution_eligible` one-way tighten only
- RACES baseline advance in same commit as edit (when run)

## Content SHA pin (pre-edit excerpt)

```
"producer_lineage": "llm_plan_compiler",
```

at `pipeline.py:3572` on base `11a27365`.
