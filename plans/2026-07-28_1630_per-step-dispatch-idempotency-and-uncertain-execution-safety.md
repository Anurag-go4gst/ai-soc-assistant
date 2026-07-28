---
name: per-step-dispatch-idempotency
overview: "Close the hook-level SPL/MCP idempotency gap left by cutover item 20: audit side effects, typed allowlisted replay payloads, leases, fingerprints, concurrent workers, and REQUIRES_RECONCILIATION when exactly-once cannot be proven."
status: proposed
date: 2026-07-28
canonical_plan: plans/2026-07-28_1630_per-step-dispatch-idempotency-and-uncertain-execution-safety.md
depends_on: plans/2026-07-28_1610_canonical-outcome-invariant-hardening.md
implementation_readiness: READY
---

# Per-Step Dispatch Idempotency and Uncertain-Execution Safety

## Objective

Extend execution safety from executor/guided-hybrid per-step idempotency (cutover item 20, **done**) to **hook-level** SPL/MCP pipeline dispatch so cross-process replay, concurrent workers, and side-effecting tool calls cannot double-execute or silently succeed after uncertainty.

**Not in scope of outcome-invariant hardening (workstream A).** Workstreams **A+B merged** @ `7ce1474`. **Next engineering priority** after closeout — **I0 complete** (2026-07-28).

## Stop conditions

- All checklist items checked with evidence, **or**
- Hook audit proves a hook is read-only with no persistence side effects and is explicitly excluded with COE sign-off, **or**
- Same gate fails twice, **or**
- COE decision on `REQUIRES_RECONCILIATION` analyst UX

## Locked decisions (draft)

| ID | Decision |
|----|----------|
| D1 | Replay uses **typed, allowlisted payloads** — never arbitrary state deltas |
| D2 | Reuse `canonical_execution_idempotency` table where possible; additive migration only if lease/fingerprint columns missing |
| D3 | Unknown side-effecting hooks default **fail-closed** (`REQUIRES_RECONCILIATION` / `execution_outcome_uncertain`) |
| D4 | Stable-idempotent side effects replay only when downstream idempotency key is propagated and verified |
| D5 | Concurrent workers: valid lease → no duplicate invoke; stale lease → documented recovery policy |

## Dependency order

`I0 → I1 → I2 → I3 → I4 → I5`

| Phase | Depends on |
|-------|------------|
| **A** Outcome invariant hardening | — |
| **B** Behavioural parity + doc correction | A |
| **C** Migration evidence closeout | A (parallel with B) |
| **D** This plan | A (B+C recommended) |
| **E** Live synthesis perf | independent of D |

## I0 deliverables (complete)

| Artifact | Location |
|----------|----------|
| Hook inventory (22 production-reachable hooks classified) | [`docs/architecture/per_step_hook_idempotency_audit.md`](../docs/architecture/per_step_hook_idempotency_audit.md) |
| P0 boundary | `graph_node_execution` / MCP gate / connector + guided `safe_catalog_query` execute |
| Typed replay schema | `HookReplayEnvelope` in audit doc §Typed replay schema proposal |
| Identity / fingerprint | `build_idempotency_key` + `input_fingerprint` (sha256 allowlisted fields) |
| Crash / timeout FSM | Audit doc §F — align gate + hook wrapper with `execution_uncertain` |
| Minimum tests | `test_per_step_hook_idempotency.py` (new) + extend `test_execution_idempotency.py` + integration postgres |
| Commit sequence | Audit doc §Estimated commit sequence (6 commits) |

**I0 verification:** `docs/architecture/per_step_hook_idempotency_audit.md` exists; inventory table lists hook name, file:line, side-effect class, idempotency coverage. Reachability spot-check: `pytest app/tests/test_resource_plan_authority.py::test_guided_hybrid_and_telemetry_never_mutate_committed_plan -q`.

## Checklist

- [x] **I0** — Hook side-effect audit (read-only deliverable)
  - **Do:** Inventory every SPL/MCP hook in `pipeline.py`, `resource_planner_graph.py`, `guided_hybrid_collection.py`, and MCP gate paths. Classify: read-only, side-effecting-stable-key, side-effecting-no-key. Document persistence writes, telemetry, and external I/O per hook.
  - **Verify:** `docs/architecture/per_step_hook_idempotency_audit.md` exists; table lists hook name, file:line, side-effect class, current idempotency coverage
  - **Depends on:** outcome-invariant hardening merged (A)
  - **Evidence:** Audit doc created 2026-07-28; P0=3, P1=6, P2=12; `pytest app/tests/test_resource_plan_authority.py::test_guided_hybrid_and_telemetry_never_mutate_committed_plan -q` → 1 passed

- [ ] **I1** — Typed replay payload contract
  - **Do:** Define allowlisted replay envelope (`HookReplayEnvelope`: `resource_plan_id`, `handoff_id`, `handoff_version`, `step_id`, `operation_identity`, `input_fingerprint`, `downstream_idempotency_key`) — align with `canonical_execution_idempotency.py`; **no** arbitrary state patch replay
  - **Verify:** `pytest app/tests/test_per_step_hook_idempotency.py -q` rejects non-allowlisted payload shapes
  - **Depends on:** I0
  - **Evidence:** _(fill when done)_

- [ ] **I2** — Lease + input fingerprint integration at hooks
  - **Do:** Wrap P0 hooks: `graph_node_execution` → `evaluate_mcp_execution` → connector; guided `safe_catalog_query` execute. Input fingerprint = hash of normalized approved SPL + tool identity + time bounds.
  - **Verify:** `pytest app/tests/test_per_step_hook_idempotency.py -q`
  - **Depends on:** I1
  - **Evidence:** _(fill when done)_

- [ ] **I3** — Concurrent worker + stale-lease races
  - **Do:** Integration tests on disposable Postgres compose (unique port, not 5434): two workers, one step; crash after `running`; replay after `completed`
  - **Verify:** integration module `0 failed 0 skipped`
  - **Depends on:** I2
  - **Evidence:** _(fill when done)_

- [ ] **I4** — `REQUIRES_RECONCILIATION` surfacing
  - **Do:** When exactly-once cannot be proven for side-effecting hooks, return honest uncertain outcome; zero false success claims
  - **Verify:** Named regression tests; governance regression PASS
  - **Depends on:** I3
  - **Evidence:** _(fill when done)_

- [ ] **I5** — Documentation + completion note
  - **Do:** Update cutover gap reconciliation matrix row 1 → **resolved**; addendum to item 20 scope note in completion report (pointer only)
  - **Verify:** `rg "hook-level SPL/MCP" docs/` shows closed status
  - **Depends on:** I4
  - **Evidence:** _(fill when done)_

## Implementation verdict

| Gate | Status |
|------|--------|
| I0 hook audit | **DONE** |
| Workstream C operator attestation | **PENDING** (name/role only — does not block I1 coding) |
| SOP routing investigation | **Fixture mismatch** — does not block D (see closeout note below) |
| **READY FOR IMPLEMENTATION** | **YES** — proceed with I1 |

## SOP routing closeout note (bounded investigation)

Query: `What is the SOP for ransomware response?`
Three invocations (MCP off, identical session): canonical seam → RP final state → public projection.

**Classification: 4 — Fixture mismatch.** Probe context without canonical Postgres / audit-critical telemetry persistence yields `persistence_failed` → `non_planned_finalize`, not `planned`/`rag_only`. Behavioural parity (`sop_playbook`) matches this fail-closed path (both runtimes `persistence_failed`). Public `execution_approval` + `policy_checks_passed` with `required=false` is `no_human_review()` finalize filler — not execution mis-routing.

**Field transitions:**

| Field | After seam | RP final | Public response |
|-------|------------|----------|-----------------|
| `outcome_read_kind` | `valid` | `valid` | _(not projected)_ |
| `outcome.status` | `persistence_failed` | `persistence_failed` | absent from CPT |
| `evidence_plan` | absent (stripped) | absent | absent |
| `human_review` | null | `execution_approval` / `policy_checks_passed` / `required=false` | same |
| `execution.status` | null | `skipped` | `skipped` |

**Action:** Correct smoke/probe fixture to use canonical DB (or in-memory test store) when asserting `planned`/`rag_only`; do not change API contract in this task. Secondary observability: `canonical_planning_outcome` is never included in `build_control_plane_trace` — document for future CPT extension (no GitHub issue opened in this closeout).

## Out of scope

- Outcome-invariant gate or `CanonicalPlanningOutcome` changes (workstream A)
- New SLO targets for live synthesis (workstream E)
- Reopening cutover checklist items

## Drift log

| Date | Note |
|------|------|
| 2026-07-28 | Skeleton created from gap reconciliation disposition #1 |
| 2026-07-28 | I0 audit complete; READY FOR IMPLEMENTATION; SOP investigation recorded §SOP routing closeout note |
