# Plan 6 Arm C — exec ON + dispatch-v2 OFF (merge actually runs)

Run dir: `docs/evals/plan6/runs/20260813T125517Z/`
Git SHA: `1d32ac66dd6c707789db8b44574bd566af401952`
Harness: `python3 scripts/eval_plan6_vps_harness.py --arm A --environment-identity coe-vps-arm-c` (same 12-row corpus as Arm B; no paraphrases)
Harness exit 0.

## Flags during the run

| Flag | Arm C live |
|---|---|
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | **true** |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | **false** |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | unset → false |

This is the only VPS arm where Plan 5 `merge_schedule` can run on composed turns. It is **not** production go-live.

## Path classification

Vocabulary from B1 / `execution_path_map.md`. Rows that never reach `execute_plan_dispatch` are `merge_not_reachable`, not “activation equivalent.”

`executed_hooks` on `debug_summary` is the Resource Planner **graph node_trace** (session_context, routing, …), not the merge hook list. PhaseContract vs planned hooks is `phase_names` vs `dispatch_schedule`. `mitre_finalize` is PhaseRegistry `pipeline_inline` (Plan 5 / E0): it can appear in `phase_names` without appearing in `dispatch_schedule`.

| row_id | answer_mode | path | merge | phase_names (PhaseContract) | dispatch_schedule (hooks) |
|---|---|---|---|---|---|
| p6.t1.knowledge | rag_only | rag_only | **merge_not_reachable** | [] | [] |
| p6.t2.known_nontrivial | rag_only | rag_only | **merge_not_reachable** | [] | [] |
| p6.t4.out_of_registry | guided_investigation | guided | merge computed | prepare_rag_only, rag_early | prepare_rag_only, rag_early |
| p6.spl.draft | live_investigation | seam | merge | workflow_spl, spl_postprocessor, spl_source_resolve, execution | same |
| p6.spl.mcp | live_investigation | seam | merge | workflow_spl, spl_postprocessor, spl_source_resolve, **mitre_finalize**, execution | workflow_spl, spl_postprocessor, spl_source_resolve, execution (**no mitre_finalize**) |
| p6.multi.knowledge_spl_mcp | live_investigation | workflow_spl | **merge_not_reachable** (`no_schedulable_step`) | [] | workflow_spl, spl_source_resolve, execution |
| p6.clarify | clarification | non-planned | **merge_not_reachable** | [] | [] |
| p6.unsafe | clarification | non-planned | **merge_not_reachable** | [] | [] |
| p6.alert.summary | rag_only | rag_only | **merge_not_reachable** | [] | [] |
| p6.live_posture.d1_003 | live_investigation | workflow_spl | **merge_not_reachable** (`no_schedulable_step`) | [] | workflow_spl, spl_source_resolve, execution |
| p6.repeat.refinement | live_investigation | seam | merge | workflow_spl, spl_postprocessor, spl_source_resolve, execution | same. Corpus class is “repeated evidence”; this was a **fresh** `/chat` turn, not `session_spl_refine`. |
| p6.fail.degraded | live_investigation | seam | merge | workflow_spl, spl_postprocessor, spl_source_resolve, execution | same |

### Counts

- **merge ran** (`degrade_reason=merge`): 5 — t4 guided, spl.draft, spl.mcp, repeat, fail.degraded
- **merge_not_reachable**: 7 — 3 rag_only, 2 non-planned, 2 workflow_spl (`no_schedulable_step`)
- **Zero** `dispatch_v2_projected_schedule` (v2 was OFF)
- `execution_enabled` **false** on all 12

`no_schedulable_step` (`resource_plan_execution_scheduler.py`): compiler produced no schedulable hook list, so merge did not activate even with exec ON. Do not treat those rows as Plan-5 merge activation.

## Trace_ids (merge rows)

- `p6.t4.out_of_registry` `68ea4110-2519-4e9b-9262-d10c8cec8ada`
- `p6.spl.draft` `4ca341c1-a448-4320-b5af-39c030ca9297`
- `p6.spl.mcp` `a0a9fadf-9de8-4cbe-ad32-1c8c8a2dbbda`
- `p6.repeat.refinement` `becfe125-1402-4fe7-8ea4-e0248e02ab9b`
- `p6.fail.degraded` `39b085d8-66d7-44ce-8ee5-21d2ac005a2b`

## Restore Arm A

Required by B1 so D0 does not confound T4 with execution. After this file: exec OFF, v2 ON, T4 OFF; `flag_matrix.md` Live VPS column records the restore.
