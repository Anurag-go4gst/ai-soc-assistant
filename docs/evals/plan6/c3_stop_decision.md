# Plan 6 C3 — `P6_EXECUTION_SEAM_ADOPTION`

Recorded 2026-08-13. **KEEP 0 ADOPTED.** This is a deferred architectural
follow-up, not a Plan 6 production blocker: the approved profile keeps
ResourcePlan execution OFF and dispatch-v2 ON.

## Decision

**KEEP 0 ADOPTED**

| Class | Count |
|---|---|
| SEAM | 2 |
| DECISION_REQUIRED | 4 |
| KEEP_SEPARATE | 4 |
| Adopted | **0** |

Do **not**:

- retire `_run_legacy_dispatch_fallback`
- adopt any `DECISION_REQUIRED` execution seam
- implement `CHANGE_LADDER`

Do not retire `_run_legacy_dispatch_fallback`.
Do not adopt any `DECISION_REQUIRED` execution seam.
Do not implement `CHANGE_LADDER`.

## Rationale

C0 selected **KEEP OFF** for ResourcePlan production execution authority.

Arm C proved `merge_schedule` is technically reachable, but also exposed known
missed work when dispatch-v2 is disabled:

- `p6.multi.knowledge_spl_mcp`
- `p6.live_posture.d1_003`

Both `workflow_spl` / `no_schedulable_step` cases lose `spl_postprocessor` when
v2 is OFF and merge does not take over.

C2 also reconfirmed that the legacy fallback skips `spl_postprocessor`. Its
current safety properties remain governed by the existing validation/execution
gates.

Plan 6 therefore has evidence to **retain** the present seams, but not evidence
to adopt, consolidate, or retire them.

## Future seam adoption / fallback retirement requires

1. measured equivalence or improvement,
2. explicit coverage of the known missed-work cases,
3. a separately approved execution-authority / change-ladder decision.

Sources: `docs/evals/plan6/seam_equivalence.md`,
`docs/evals/plan6/c0_d3_stop_decisions.md`,
`docs/evals/plan6/runs/arm_c_merge.md`.
