# Plan 6 — execution reachability map

Measured at P0 from `backend/app/planner/executor.py`, `backend/app/tests/test_execution_seam_coverage.py`, and `backend/app/graph/resource_planner_graph.py`. Inventory is Plan 3 A1 / Plan 5 C3; **0 seams adopted**.

**C2 refresh (after C0 KEEP OFF):** VPS Arm C (`docs/evals/plan6/runs/arm_c_merge.md`, `20260813T125517Z`) confirmed the map on live `/chat`. C0 recorded **KEEP OFF** — production authority stays on the current v2 path. Nothing is retired. Inventory remains **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted**. See `docs/evals/plan6/seam_equivalence.md`.

## Dispatch-v2 beats ResourcePlan merge

In `_execution_driven_schedule_detailed` (`backend/app/planner/executor.py`):

1. Flag off (`ai_soc_resource_plan_execution_enabled=false`) → `(None, None, None)` — **zero merge code**.
2. Flag on **and** `imperative_hook_schedule_from_state(state) is not None` (dispatch-v2 projected a schedule) → `(None, "dispatch_v2_projected_schedule", None)` — merge **stands down**.
3. Flag on **and** no v2 projection → compiler + `merge_schedule` (Plan 5 C1).

COE profile sets `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true`. Therefore **Arm B (exec ON, v2 ON) is `V2_WINS`**, not Plan-5 merge activation. **Arm C (exec ON, v2 OFF)** is the only VPS arm that runs merge on composed turns.

Do not call `exec ON + v2 ON` Plan-5 execution activation while v2 still wins.

C0 Field 1 **KEEP OFF**; Field 2 **N/A**. Keep dispatch-v2 ON in the current VPS/COE posture. `CHANGE_LADDER` was not selected. Future ResourcePlan activation requires (1) evidence that the v2-OFF missed-work cases below are correctly covered, or (2) an explicitly approved `CHANGE_LADDER` / execution-seam change.

## Canonical seam (`execute_plan_dispatch`)

Exactly two call sites (`test_execution_seam_coverage.py`):

- `graph:composed_dispatch` — `pipeline.py` `graph_node_composed_dispatch`
- `imperative:composed_plan` — imperative composed-plan branch

RP-graph routing (`_rp_dispatch_route`): `non_planned_finalize` | `rag_only` | `composed_dispatch` | `workflow_spl`.

## Paths that never hit `execute_plan_dispatch`

These query shapes **cannot** exercise Plan 5 merge even when the execution flag is ON. Corpus rows must be classified by actual path.

**DECISION_REQUIRED (4)** — not adopted:

| Path | Why merge does not run |
|---|---|
| `graph:rag_only` | RP graph routes `answer_mode=rag_only` to the rag-only nodes, not composed dispatch. |
| `graph:workflow_spl` | SPL-only / no composed plan → workflow_spl nodes, not the seam. |
| `imperative:guided_hybrid` | Guided hybrid has its own loop. |
| `imperative:session_spl_refine` | Sole caller of `_run_legacy_dispatch_fallback`. |

**KEEP_SEPARATE (4)**:

| Path | Why |
|---|---|
| `graph:non_planned_finalize` | Clarification / blocked / non-planned short-circuit. |
| `imperative:non_planned` | Same class on the imperative path. |
| `trace:v2_cursor_synthesis` | Cursor synthesis, not plan dispatch. |
| `fixture:ec_demo` | Experience Center fixtures; never live LLM/MCP/trace. |

## VPS Arm C path classification (B1 / C0 evidence)

12-row corpus, exec ON, v2 OFF. Merge is **not** “activation equivalent” on rows that never hit the seam.

| Class | Count | Rows |
|---|---|---|
| **merge executed** (`degrade_reason=merge`) | 5 | `p6.t4.out_of_registry`, `p6.spl.draft`, `p6.spl.mcp`, `p6.repeat.refinement`, `p6.fail.degraded` |
| `merge_not_reachable:rag_only` | 3 | `p6.t1.knowledge`, `p6.t2.known_nontrivial`, `p6.alert.summary` |
| `merge_not_reachable:non_planned` | 2 | `p6.clarify`, `p6.unsafe` |
| `merge_not_reachable:no_schedulable_step` (`graph:workflow_spl`) | 2 | `p6.multi.knowledge_spl_mcp`, `p6.live_posture.d1_003` |

The two `workflow_spl` / `no_schedulable_step` rows **drop `spl_postprocessor`** vs Arm A/B even though merge does not run. That is why C0 rejected `V2_OFF_ON_VPS`: it would introduce known missed work. Arm C merge 5/12 remains a reachability proof, not production authority.

## Legacy fallback

`_run_legacy_dispatch_fallback` (`pipeline.py`): sole call site session-SPL-refine. Legacy branch **skips `spl_postprocessor`**. Safe because MCP gate refuses unapproved/null `normalized_spl` plus RP-graph `spl_validate`. Proof: `docs/evals/plan5/c3_fallback_equivalence.md`. **C3 KEEP 0 ADOPTED** — do not retire it; do not adopt any `DECISION_REQUIRED` seam; do not implement `CHANGE_LADDER`.

## Inline vs hook-loop

`mitre_finalize` / `cve_adapter` are PhaseRegistry `pipeline_inline`. They run inside `graph_node_context_finalize`, not the hook loops. E0 measures provenance accuracy, not a duplicated hook-loop.

## Default production `/chat`

`langgraph_orchestration_enabled=true` → `run_chat_via_resource_planner_graph`. Imperative rollback still exists; observability (A0/A1) must cover both.
