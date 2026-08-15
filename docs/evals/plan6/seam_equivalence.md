# Plan 6 C2 — seam / fallback equivalence (KEEP OFF refresh)

C0 recorded **KEEP OFF**. This item **refreshes reachability**; it does **not** retire `_run_legacy_dispatch_fallback`, adopt any `DECISION_REQUIRED` seam, or implement `CHANGE_LADDER`. Plan 5 proof remains authoritative: `docs/evals/plan5/c3_fallback_equivalence.md`. Do not overwrite `docs/evals/plan5/c2_phase_merge_probe.json`.

## Inventory (unchanged)

Pinned by `backend/app/tests/test_execution_seam_coverage.py` and `test_fallback_lifecycle_equivalence.py`.

| Class | Count | Paths |
|---|---|---|
| SEAM | 2 | `graph:composed_dispatch`, `imperative:composed_plan` |
| DECISION_REQUIRED | 4 | `graph:rag_only`, `graph:workflow_spl`, `imperative:guided_hybrid`, `imperative:session_spl_refine` |
| KEEP_SEPARATE | 4 | `graph:non_planned_finalize`, `imperative:non_planned`, `trace:v2_cursor_synthesis`, `fixture:ec_demo` |
| Adopted | **0** | — |

`execute_plan_dispatch` still has exactly two call sites. The fallback still has exactly one call site (`session_spl_refine`).

## Equivalence properties (no adoption)

| Property | Canonical seam + merge (exec ON, v2 OFF, composed) | Legacy fallback (session-SPL-refine) | VPS Arm C note |
|---|---|---|---|
| Mandatory hook phases | Merge re-inserts `spl_postprocessor` when a contract exists | Legacy branch **does not** run `spl_postprocessor` | Must not claim otherwise. Pin: `test_fallback_legacy_branch_runs_no_spl_postprocessor`. |
| SPL validation | `spl_validate` on RP-graph spine; MCP gate requires approved non-null `normalized_spl` | Same MCP gate fail-closed | Arm C: SPL `approved=false` except `p6.spl.mcp` (still HIL, MCP skipped). |
| MCP gate | `evaluate_mcp_execution` only from `graph_node_execution` | Same | MCP never executed on A/B/C. |
| HIL | Present when owed | Present when owed | No HIL drop A=B=C. |
| RBAC / `session_role` | Unchanged by merge | Unchanged | — |
| MITRE/CVE finalization | `pipeline_inline` inside `graph_node_context_finalize`, not the hook loop | Never in fallback hook list | `p6.spl.mcp` PhaseContract listed `mitre_finalize` not in `dispatch_schedule` — provenance/inline, not duplicate hook execution (E0). |
| Reference finalization | Contract-mandatory; merge may insert | Legacy **does not** run `reference_finalize` | Same Plan 5 gap. |
| Failure handling | Bounded degrade; no auto-retry of side-effecting steps | Same MCP fail-closed | `p6.fail.degraded` stayed gated. |
| Refinement | Fresh `/chat` in corpus; session refine is the fallback path | Sole fallback caller | `p6.repeat.refinement` was a **fresh** turn, not session refine. |
| Telemetry / provenance | `debug_summary.degrade_reason` (`merge` / `dispatch_v2_projected_schedule` / `no_schedulable_step` / none) | Fallback is a second engine | A/B/C: no `legacy` degrade on the 12-row corpus. |

**Not equivalent** on `spl_postprocessor` / `reference_finalize` for the legacy branch. That is still fail-closed via the MCP gate, not via running the owed lifecycle. C0 KEEP OFF does not paper over that gap.

## VPS missed work that blocks `V2_OFF_ON_VPS`

With exec ON and v2 OFF, merge does not run on `graph:workflow_spl` when the compiler emits `no_schedulable_step`. Those rows still change the projected hook list vs Arm A/B:

- `p6.multi.knowledge_spl_mcp`
- `p6.live_posture.d1_003`

Both **drop `spl_postprocessor`**. Merge did not run. HIL remained required; SPL stayed unapproved; MCP did not execute. This is known missed work, not a silent improvement. C0 therefore kept production on v2 ON + exec OFF.

## C3 recorded (2026-08-13)

**KEEP 0 ADOPTED.** Inventory stays 2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE / 0 adopted.

Do not retire `_run_legacy_dispatch_fallback`. Do not adopt any `DECISION_REQUIRED` seam. Do not implement `CHANGE_LADDER`.

This is a deferred architectural follow-up, not a Plan 6 production blocker (C0 KEEP OFF + dispatch-v2 ON). Future adoption requires measured equivalence or improvement, coverage of `p6.multi.knowledge_spl_mcp` / `p6.live_posture.d1_003`, and a separately approved execution-authority / change-ladder decision.

Artifact: `docs/evals/plan6/c3_stop_decision.md`.

## Pins re-run

`cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_fallback_lifecycle_equivalence.py app/tests/test_execution_seam_coverage.py -q`
