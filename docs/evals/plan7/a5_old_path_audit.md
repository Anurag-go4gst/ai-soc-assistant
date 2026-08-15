# Plan 7 A5 — old-path audit on the target posture

Measured from the 12 A4 traces (`docs/evals/plan6/runs/20260814T134610Z/`), reading
`control_plane_trace.plan_dispatch.dispatch_source` and `execution_order`. **No seam was adopted
and none was retired** — this item classifies, it does not change authority.

## What actually dispatched

| `dispatch_source` | Rows | Merge active | Classification |
|---|---|---|---|
| `resource_plan_step_walk` | **8** | **yes** on all 8 | ResourcePlan + PhaseContract authoritative — the target architecture |
| `canonical_non_planned` | 2 | n/a | **legitimately separate** (KEEP_SEPARATE in the Plan 6 inventory) |
| none (`src=None`) | 2 | n/a | knowledge/rag-only lane — never reaches `execute_plan_dispatch` |
| `legacy_predicate` | **0** | — | — |
| `session_spl_refine` (`_run_legacy_dispatch_fallback`) | **0** | — | — |
| `guided_hybrid` | **0** | — | — |

**`_run_legacy_dispatch_fallback` did not execute once on the target posture.** Neither did the
guided-hybrid or session-SPL-refine branches. There is no row where an old engine ran alongside
the merge, so **merge + old-engine double-run = 0**.

## Classification

### Migration debt — 1 item

**`_run_legacy_dispatch_fallback` still exists and still skips `spl_postprocessor`.** A4 proved
that phase is contract-inserted on *every* SPL row, so any path that bypasses the merge loses
deterministic SPL validation. The fallback did not run in this corpus, but it remains reachable
via `session_spl_refine`. Retiring or fixing it is **not** part of A5 — it is exactly the kind of
question A6 exists to frame, and the safety net today is the MCP gate refusing unapproved/null
`normalized_spl`.

### Legitimately separate — 4 items

- `canonical_non_planned` (2 rows observed) — no composed plan exists; there is nothing for the
  merge to own.
- knowledge/rag-only lane (2 rows observed) — no `plan_dispatch` at all.
- `trace:v2_cursor_synthesis` and `fixture:ec_demo` — unobserved here, KEEP_SEPARATE by design
  (EC purity forbids the runtime path).

### Regressions — 0

No path executed work that ResourcePlan + PhaseContract should have owned. The one case that
would have qualified — SPL lifecycle running without contract authority — is precisely what A3
closed.

## Seam inventory — unchanged

Still **2 SEAM / 4 DECISION_REQUIRED / 4 KEEP_SEPARATE, 0 adopted**
(`test_execution_seam_coverage.py`, `test_plan6_c3_keep_zero_adopted.py` both green in the
997-test planner slice). A3 changed what the merge does *once reached*; it did not change which
paths reach it.

## Carried to A6

1. Can dispatch-v2 stay OFF as normal authority? On this corpus the target architecture carried
   every planned row with 0 missed mandatory work and 0 duplicates.
2. Residual: `_run_legacy_dispatch_fallback` remains reachable via `session_spl_refine` and skips
   `spl_postprocessor` — unexercised here, unmeasured elsewhere.
3. The 4 `DECISION_REQUIRED` seams remain unadopted; nothing in Plan 7 has changed their status.
