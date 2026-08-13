# Plan 5 C3 — `_run_legacy_dispatch_fallback` vs the canonical lifecycle

Proof only. **Nothing is adopted and nothing is retired here** — `C_SEAM_ADOPTION` is closed as
"proof required, no adoption pre-approved", and this audit does not change that.

## Reachability, re-verified at `f044cdc`

| Fact | Measured |
|---|---|
| Definition | `chat/pipeline.py:5751` |
| Call sites | exactly **one**: `chat/pipeline.py:653`, the `_session_spl_refine_active` branch — **not** flag-gated |
| Guard | `_session_spl_refine_active` (`:5839`) — fresh session pins carrying `last_candidate_spl` |
| Inner v2 branch | active only when `imperative_hook_schedule_from_state(state)` is truthy, i.e. `ai_soc_pipeline_dispatch_v2_enabled` is true |
| Repo default | `ai_soc_pipeline_dispatch_v2_enabled = False` (`config.py:403`) |
| **COE host** | dispatch-v2 is **on** (recorded in `CLAUDE.md`), so the v2 branch is **live there** |
| Canonical-seam anchors | `execute_plan_dispatch` call sites re-measured as `pipeline.py:658` and `pipeline.py:2276`; `test_execution_seam_coverage.py` carried stale `655`/`2273`, now corrected |

## The two branches, as they actually run

**v2 branch** (`:5779-5803`) — its private `hook_nodes` table has 7 entries and runs the projected schedule
in order, then appends `execution` if SPL ran and `execution` is not already in state.

**Legacy branch** (`:5805-5821`), taken when dispatch-v2 is off or projects nothing:

```
rag-only lane : prepare_rag_only → rag_early
otherwise     : workflow_spl → [rag_early if pre-MCP RAG] → spl_source_resolve → execution
```

## Equivalence verdict

| Property | v2 branch | legacy branch | canonical PhaseContract |
|---|---|---|---|
| `spl_postprocessor` when SPL applicable | **yes** (projected) | **NO** | **yes** (mandatory) |
| `reference_finalize` when reference IDs applicable | **yes** (projected) | **NO** | **yes** (mandatory) |
| `ensure_workflow_plan` when SPL blocked and no workflow plan | **no** — absent from its table | **no** | **yes** (mandatory) |
| `mitre_finalize` / `cve_adapter` | dropped by the projection | never | declared **inline-mandatory**, executed in `graph_node_context_finalize` |
| Ordering authority | projected stage order | hard-coded literal order | declared `after` constraints, checked at runtime |
| Drops a contracted phase | 1 class (`ensure_workflow_plan`) | **2 classes** | 0 — `merge_schedule` re-inserts, or fails closed |

**Not equivalent, in the direction that matters.** On the one path that reaches it — a session-SPL-refine turn
with dispatch-v2 off — the fallback runs `workflow_spl → spl_source_resolve → execution` and **never runs
`spl_postprocessor`**. The C2 probe measures the same class of gap for the compiler
(`docs/evals/plan5/c2_phase_merge_probe.json`: `compiler_only_stage_drops=4/5`, `merged_stage_drops=0/5`).

Two mitigations are why this is a design gap and not a live SPL-validation hole:

1. On the RP-graph spine the governance chain runs `spl_validate` as its own node
   (`resource_planner_graph.py:799` → `mcp_execution_gate`), independently of any hook schedule.
2. `graph_node_execution` is the sole caller of `evaluate_mcp_execution`, and the MCP gate refuses a candidate
   without an approved non-null `spl_validation.normalized_spl`. A missing postprocessor therefore fails **closed**
   (no execution) rather than executing unvalidated SPL.

So the fallback is safe today by virtue of two other gates, not by virtue of running the lifecycle it owes. That is
precisely the fragility the PhaseContract removes — and precisely why retirement must be a decision, not a
side effect of the merge seam existing.

## Options for `C_SEAM_ADOPTION` (no recommendation acted on)

| Option | What changes | Risk |
|---|---|---|
| **1. Keep the fallback, keep the inventory at 0 adopted** (status quo) | Nothing. Plan 5 ships the registry/policy/contract/merge unwired at default. | None. The two gates above continue to make the gap fail closed. |
| **2. Give the fallback the PhaseContract** — validate its emitted schedule against the contract and insert missing mandatory phases | The session-SPL-refine path gains `spl_postprocessor`. **This is a production-default behaviour change on the one live path**, and on the COE host it also touches the live v2 branch. | Medium: changes what a real turn runs; needs its own measurement (parity, Cisco, 105) before approval. |
| **3. Retire `_run_legacy_dispatch_fallback` and route session-SPL-refine through `execute_plan_dispatch`** | Removes the second execution engine. | Highest: the refine path has no committed ResourcePlan, so it would need one; changes execution authority on a live path. |

**STOP.** Options 2 and 3 both change production-default execution authority, so neither is taken in Plan 5.
The inventory stays **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted**.
