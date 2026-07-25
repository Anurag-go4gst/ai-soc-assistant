---
name: Guided detail tools — canonical planning architecture
overview: "T0–T4 canonical planning is the sole runtime architecture. Phase 1 delivered contracts, lane routing, DetailTools, and always-on pipeline wiring. Phase 2 closes cutover gaps: typed planning outcomes, a deployed migration path, a canonical DB unit-of-work, DB-only handoffs, execution idempotency, durable telemetry with typed correlation and an audit-critical/diagnostic split, outcome-aware response validation, Experience Center purity, retention/purge, containerised live smoke, and full pytest/governance green — no feature flags, legacy fallbacks, runtime DDL, or live memory/file handoff stores."
status: active
date: 2026-07-25
canonical_plan: plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md
todos:
  - id: phase1-complete
    content: "Phase 1 items 1–9: contracts, lanes, DetailTools, pipeline wiring"
    status: completed
  - id: phase1-reaudit
    content: "Item 11 intermediate regression gate (after 14+17)"
    status: pending
  - id: outcome-sentinel
    content: "Items 12–14: CanonicalPlanningOutcome + orchestrator refactor + sentinel pass"
    status: pending
  - id: pytest-migration
    content: "Items 15–17: failure inventory, canonical test helper, 0 pytest failures"
    status: pending
  - id: db-foundation
    content: "Items 18a–19a: migration deployment/readiness + canonical DB unit-of-work and pool"
    status: pending
  - id: durable-handoff
    content: "Items 18–19: DB-only handoffs + transactional clarification resumption"
    status: pending
  - id: execution-idempotency
    content: "Items 21b, 20: persistence policy split + execution idempotency in executor and guided hybrid"
    status: pending
  - id: telemetry-validation
    content: "Items 10, 21a, 21–22: telemetry foundation, typed correlation, full catalog, outcome-aware response validation"
    status: pending
  - id: authority-integration
    content: "Items 23–24: ResourcePlan authority audit + Postgres integration suite"
    status: pending
  - id: cleanup-gates
    content: "Items 25, 26, 26a, 28: config/doc cleanup, compatibility code removal, EC purity, retention/purge"
    status: pending
  - id: live-smoke-gates
    content: "Items 29, 27: containerised /chat canonical smoke + all verification gates"
    status: pending
isProject: false
---

# Guided detail tools — canonical planning architecture (rev 9)

## Architecture objective

One consistent agentic flow — **always on**, no feature flags or legacy fallbacks:

- **T1–T3** — deterministic catalogue match → `processing_lane=known`
- **No T1–T3 match** → initial **T4** `processing_lane=guided`
- **T0** — resolved tier only after T4 qualification (`reference_knowledge` / `knowledge_only`)
- **`knowledge_recall`** — reusable read-only DetailTool
- **Gap-resolution planner** — `GapResolutionResult` only; never creates `ResourcePlan`
- **Final planner** — `plan_evidence_from_canonical` is the **sole** `ResourcePlan` creator/committer
- **Execution** — only from committed `ResourcePlan`; guided hybrid dispatch projects `InvestigationPlan`, never composes plans
- **Persistence** — PostgreSQL for handoffs, planning events, execution idempotency (`0004_canonical_handoffs.sql`)
- **Non-planned outcomes** — clarification, policy block, planning failure via typed `CanonicalPlanningOutcome`; downstream branches on `status`, not on partial `EvidencePlan` dicts

## Completion criteria (all must be true before marking Done)

- [ ] Canonical planning is always active; no flags or shadow paths remain
- [ ] No legacy planning path can execute on live `/chat`
- [ ] Runtime handoffs use PostgreSQL only (no live memory or file fallback)
- [ ] Migrations are applied by a deploy step (not by runtime DDL) and verified in `schema_migrations`
- [ ] Handoff/idempotency writes run inside one transaction on one connection (unit-of-work)
- [ ] All persisted planning events contain required correlation fields (`session_id`, `decision_id`, `handoff_id`, etc.) as typed columns — verified non-null
- [ ] Experience Center path emits zero canonical planning events, handoff rows, and plan commits
- [ ] Handoff + planning-event retention/purge is enforced (no unbounded SOC-content growth)
- [ ] Containerised live `/chat` smoke passes for all six canonical paths
- [ ] Response and terminal request events are complete (`response.validated`, `response.generated`, `request.completed` / `request.failed`)
- [ ] Guided dispatch cannot create or modify `ResourcePlan`
- [ ] Plan and execution idempotency are transactionally enforced
- [ ] Full backend pytest passes (0 failed)
- [ ] Stage 3 governance regression passes
- [ ] Sentinel clarification evaluation passes

## Stop conditions

- All checklist items checked with evidence, **or**
- Same Verify fails twice on one item, **or**
- Decision needed — stop and ask

## Dependency order

Phase 1: `1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9`

Phase 2 (execution order — rev 9; item numbers unchanged, new items suffixed):

`12 → 13 → 14 → 15 → 16 → 17 → 18a → 19a → 10 → 21a → 18 → 19 → 21b → 20 → 21 → 22 → 23 → 24 → 25 → 26 → 26a → 28 → 11 → 29 → 27`

**Gate rules:**
- Do not start item 15 until item 14 (sentinel) passes.
- **18a blocks 18, 19a, 24** — no fail-closed persistence before migrations have a deploy path.
- **19a blocks 19, 20, 24** — no multi-statement transaction work before the unit-of-work exists.
- **10 + 21a precede 18** — items 18/19/20 emit durable telemetry, so the telemetry foundation and typed correlation columns are prerequisites, not successors.
- **21b blocks 20 and final telemetry acceptance (21, 22)** — the audit-critical vs diagnostic split decides where execution fails closed.
- Item 20 uses repository/unit tests first; item 24 validates concurrency with real PostgreSQL.
- Item 11 is an intermediate regression gate (not an early implementation step).
- **29 runs after 24, 21, 22, 26a** — live smoke is the last functional gate before item 27.

## Target flow

```mermaid
flowchart TD
  q[User message] --> qu[understand_query]
  qu --> lane[lane_router initial_tier]
  lane -->|T1-T3 known| kdc[known_detail_completion]
  kdc -->|complete| stub[intent stub]
  kdc -->|gaps| gdr[guided detail resolution]
  lane -->|initial T4| intent[T4 intent + reference qualification]
  intent -->|pure knowledge| t0[resolved T0 builds CanonicalPlanningInput only]
  intent -->|status/investigation/composite| gdr
  stub --> cpi[CanonicalPlanningInput]
  t0 --> cpi
  gdr --> pgc[post_guided_completeness]
  pgc --> cpi
  pgc -->|clarify| hil[clarification outcome]
  cpi --> fep[plan_evidence_from_canonical]
  fep --> rp[ResourcePlan committed to DB]
  rp --> exec[execution with idempotency]
  hil --> resume[transactional handoff resume]
  resume --> merge[merge user answer]
  merge --> recheck[known_detail_completion or post_guided_completeness]
  recheck -->|complete| cpi
  recheck -->|still incomplete| hil
  recheck -->|failed or expired| fail[typed failure outcome]
```

## Tier and lane table (authority)

| `deterministic_match_path` | Initial tier | `processing_lane` (initial) | Intent hop |
|----------------------------|--------------|----------------------------|------------|
| `exact_105_question`, `exact_105_plus_use_case_catalog` | T1 | known | stub only if complete |
| `use_case_catalog` | T2 | known | stub only if complete |
| `near_105_question`, `semantic_105_question`, `fuzzy_alias_catalog` | T3 | known | stub only if complete |
| `out_of_registry`, `query_understanding_weak`, `qu_unavailable`, empty | T4 | guided | full classifier |
| **Resolved T0** (post-T4 only) | T0 | knowledge_short_circuit | classifier → qualification |

## Locked decisions (rev 8)

1. T0 is **resolved tier only** after T4 qualification — never from parser.
2. CVE/MITRE/ATLAS id alone does **not** assign T0; use `ReferenceQueryQualification`.
3. `processing_lane` and `answer_goal` are independent.
4. Single planner-facing contract: `CanonicalPlanningInput`.
5. Gap-resolution planner outputs `GapResolutionResult`; final planner is sole `ResourcePlan` creator.
6. `knowledge_recall` DetailTool is read-only with typed `KnowledgeRecallResult`.
7. **Dual-runtime parity:** imperative pipeline and RP graph are **entry points into the same canonical orchestration service**. They must not contain separate copies of routing, planning, or handoff logic.
8. **T0 knowledge execution:** T0 qualification does **not** execute `knowledge_recall` before the final planner. T0 creates `CanonicalPlanningInput`; the final planner places `knowledge_recall` into the committed `ResourcePlan`. For T4 guided resolution, `knowledge_recall` may run before final planning **only** when resolving a planning gap (not for T0 short-circuit).
9. **No feature flags** for canonical planning — `is_canonical_authoritative()` always true.
10. **No live memory/file handoff fallback** — DB unavailable → `persistence_failed` outcome.
11. **Non-planned outcomes:** downstream pipeline branches on `CanonicalPlanningOutcome.status` — never on a partially constructed `EvidencePlan`. Clarification and failure paths do **not** require `EvidencePlan`.
12. **Telemetry failure policy (refined rev 9 — see item 21b):** persistence classes are not uniform.
    - **State persistence** (handoff, `ResourcePlan` commit, execution idempotency) failure → **fail closed**, always.
    - **Audit-critical telemetry** (`handoff.persisted`, `resource_plan.created`, `execution.started`, `execution_step.started`, `execution_step.completed`, `request.failed`) failure **before side-effecting execution** → **fail closed**.
    - **Diagnostic telemetry** (the remaining events) failure → controlled degraded outcome: logged at WARNING with `error_category`, surfaced in the trace, **never silently dropped**, **never** blocking a read-only response.
    - This preserves the shipped COE invariant that diagnostic observability is best-effort and never breaks chat, while making the audit spine non-optional. Document the exact per-event class in `canonical_telemetry_coverage.md`.
13. **Migration policy:** If `0004_canonical_handoffs.sql` is already applied in any environment, **do not edit it**. Add `0005_canonical_planning_cutover_constraints.sql` for any missing: unique ResourcePlan commit constraint, event deduplication key, execution-idempotency uniqueness, lease fields/indexes, clarification-resumption indexes.
14. **Migrations are a deploy step, never runtime DDL.** Runtime code must not execute `.sql` files. Schema readiness is verified by reading `schema_migrations`, and a missing migration is a startup/readiness failure, not a lazy `CREATE TABLE IF NOT EXISTS` on the request path.
15. **One canonical data layer.** Canonical persistence uses a single pooled connection source and a unit-of-work; repository methods accept a connection/transaction handle rather than opening their own. No new third data-access pattern beyond SQLAlchemy (`app/db/session.py`) and the telemetry asyncpg connector.
16. **Correlation fields are typed columns, not payload keys.** `minimize()` deletes any key containing `session_id` (it is in `_SECRET_KEY_PARTS`). Correlation values are read from the unminimized source and bound to columns; `minimize()` applies only to the free-form payload.
17. **Experience Center purity.** The EC fixture path (`routes_scenarios.py`) creates no handoff rows, commits no `ResourcePlan`, and emits no canonical planning events. Removing runtime trace fields must not silently invalidate `app/demo/captures/*.json` or golden fixtures — fixture migration is explicit work, not a side effect.
18. **Rollback posture.** No flags by design, so the only runtime mitigation is `git revert` of the cutover commit(s). Migrations `0004`/`0005` are additive and forward-compatible; a revert requires no down-migration. State this in the completion report.

---

## Phase 1 — Contracts and wiring (items 1–9) — DONE

- [x] **1** — Core contracts
  - **Do:** `canonical_planning_input.py`, `reference_qualification.py`, `gap_resolution.py`, `knowledge_recall.py`; extend `DecisionRecord.payload`
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py app/tests/test_decision_record.py -q`
  - **Depends on:** none
  - **Evidence:** 16 passed (contracts + DecisionRecord payload roundtrip)

- [x] **2** — Lane router + intent defaults
  - **Do:** `lane_router.py`, `intent_family_defaults.py`
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k lane -q`
  - **Depends on:** 1
  - **Evidence:** `test_lane_router_t1_t3_known`, `test_no_match_initial_t4`

- [x] **3** — Present-key projection
  - **Do:** Extend entity projection for bare user/host tokens
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k present_key -q`
  - **Depends on:** none
  - **Evidence:** `test_present_key_projection_bare_user_host` green

- [x] **4** — Known completeness gate
  - **Do:** `known_detail_completion.py`
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k known_incomplete -q`
  - **Depends on:** 2, 3
  - **Evidence:** divert + complete-path tests green

- [x] **5** — Reference qualification + T0 resolution
  - **Do:** `reference_qualification.py`; T4 → T0 when knowledge-only scopes
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k t0 -q`
  - **Depends on:** 1, 2
  - **Evidence:** `test_t0_only_after_qualification`, `test_cve_status_stays_t4`, `test_t4_resolves_to_t0_knowledge_plan`

- [x] **6** — DetailTools: knowledge_recall + select + merge
  - **Do:** `detail_tools/knowledge_recall_tool.py`, `select_detail_tools.py`, `detail_merge.py`
  - **Verify:** `pytest app/tests/test_canonical_handoff_invariants.py -k tool -q`
  - **Depends on:** 1, 5
  - **Evidence:** tool selection + failure tests green

- [x] **7** — Gap-resolution planner
  - **Do:** `guided_detail_resolution.py`, `post_guided_completeness.py`
  - **Verify:** `pytest app/tests/test_canonical_handoff_invariants.py -q`
  - **Depends on:** 4, 6
  - **Evidence:** gap planner + post-guided completeness tests green

- [x] **8** — Canonical handoff builder + final planner adapter
  - **Do:** `canonical_handoff_builder.py`, `plan_evidence_from_canonical.py`; `resource_plan_authority.py` guard
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k planner -q`
  - **Depends on:** 1, 7
  - **Evidence:** `test_final_planner_consumes_answer_goal`; authority guard in composer

- [x] **9** — Pipeline + RP graph wiring (always-on)
  - **Do:** Canonical nodes unconditional in `pipeline.py`; `guided_hybrid_dispatch.py` / `guided_hybrid_executor.py` execute from committed plan only; flags removed from `config.py`
  - **Verify:** `pytest app/tests/test_dual_runtime_lane_parity.py -q`; `grep -r 'plan_dispatch_fallback' backend/app/chat/pipeline.py` → no live fallback
  - **Depends on:** 8
  - **Evidence:** 3 parity cases; legacy `graph_node_evidence_planning` fallback removed from live path; migration `0004_canonical_handoffs.sql` added. Committed `ceb7b19`.
  - **Defect found and fixed at commit review (rev 9):** all 10 canonical state channels — `canonical_planning_input`, `canonical_planning_failure`, `gap_resolution`, `known_completeness`, `processing_lane`, `initial_tier`, `resolved_tier`, `handoff_resume`, `pending_handoff_id`, `pending_handoff_version` — were **undeclared** on `ChatPipelineState`. `ResourcePlannerGraphState` inherits that TypedDict, so LangGraph silently dropped every one of them on the live RP graph edge between `rp_node_bootstrap` and each later consumer: `guided_hybrid_dispatch.py:14,16`, `guided_hybrid_executor.py:32`, `session_context.py:276-277`, `planner/executor.py:363`. The existing guard `test_pipeline_state_writes_are_declared_channels` scans only `pipeline.py`, so writes issued from `canonical_planning_orchestrator.py` were invisible to it. Fixed by declaring the channels; guarded by `test_canonical_planning_channels_declared_on_chat_pipeline_state` (module-scan extension) and `test_resource_planner_final_state_retains_canonical_planning_input` (graph-level `.invoke()`, not a node-level call). **Negative control:** deleting the `canonical_planning_input` declaration fails both new tests — `2 failed, 6 passed`; restored → `11 passed`. This is the third instance of the undeclared-channel class in this repo; the class is now covered at the graph edge, not just the node.

---

## Phase 2 — Always-on cutover (items 10–27)

Maps 1:1 to user spec §1–§14, plus rev 9 architecture-review items (18a, 19a, 21a, 21b, 26a, 28, 29).

**Implementation status (rev 9, verified):** Phase 2 is not started **except** a partial item 10 — `durable_planning_telemetry.py`, `planning_telemetry.py`, and `response_validation.py` exist, and `validate_final_response` is already called on the live path at `pipeline.py:4253`. Rev 8's "nothing implemented" claim was wrong. Item 10 must be finished (unit-of-work, correlation, policy), not started from zero.

### Root cause — sentinel / clarification (Gate 1 blocker) — spec §1

```mermaid
flowchart LR
  orch[canonical_planning_orchestrator] -->|clarification| partial["evidence_plan dict forced into state"]
  partial --> downstream["EvidencePlan.model_validate"]
  downstream --> fail[ValidationError in sentinel /chat]
```

**Confirmed bugs (not fixed):**
- `canonical_planning_orchestrator.py` ~396–402 inserts partial `evidence_plan` dict on clarification
- `response_validation.py` always requires `resource_plan` — fails clarification paths
- Resume checks `status == "clarification_required"` but store saves `awaiting_clarification`
- `canonical_handoff_repository.py` falls back to `_TEST_STORE` when DB disabled or write fails

**Outcome rules (items 12–13) — branch on `CanonicalPlanningOutcome.status`, not on `EvidencePlan` presence:**

| `status` | `EvidencePlan` | `ResourcePlan` | Required |
|----------|----------------|----------------|----------|
| `planned` | **Required** (valid typed) | **Committed and required** | `canonical_input` |
| `clarification_required` | **Absent** | **Absent** | clarification + unresolved fields + persisted handoff |
| `policy_blocked` | Optional only for non-executing response | **Absent** | policy metadata |
| `resolution_failed` / `planning_failed` / `unsupported` / `execution_failed` / `persistence_failed` | **Absent** | **Absent** | typed `failure` |

Do **not** insert placeholder or structurally invalid `EvidencePlan` values. Do **not** require `EvidencePlan` for clarification — that recreates the sentinel failure.

---

- [x] **12** — `CanonicalPlanningOutcome` contract — spec §1
  - **Do:** Add `backend/app/chat/contracts/canonical_planning_outcome.py` with statuses: `planned`, `clarification_required`, `resolution_failed`, `planning_failed`, `policy_blocked`, `unsupported`, `execution_failed`, `persistence_failed`. Fields: `canonical_input`, `evidence_plan` (only when `planned` or optional `policy_blocked`), `resource_plan` (only when `planned`), `clarification`, `failure`. Factory helpers per outcome rules table above — **no `EvidencePlan` for clarification or failure statuses**.
  - **Do:** Add `backend/app/tests/test_canonical_planning_outcomes.py` with **one named test per status** (minimum 8): `test_outcome_planned`, `test_outcome_clarification_required`, `test_outcome_resolution_failed`, `test_outcome_planning_failed`, `test_outcome_policy_blocked`, `test_outcome_unsupported`, `test_outcome_execution_failed`, `test_outcome_persistence_failed`.
  - **Verify:** `pytest app/tests/test_canonical_planning_outcomes.py -q` → 8+ passed
  - **Depends on:** none
  - **Evidence:** `backend/app/chat/contracts/canonical_planning_outcome.py` — 8 statuses, `ClarificationRequest`, `PlanningFailure`, factories (`planned_outcome`, `clarification_outcome`, `policy_blocked_outcome`, `failure_outcome`), `outcome_from_state` for the state round-trip, plus `is_planned`/`is_executable`. Outcome-rules table enforced by a `model_validator`, not by convention: non-planned statuses reject a `resource_plan`, `clarification_required` rejects an `evidence_plan`, failures require typed `failure`. `pytest app/tests/test_canonical_planning_outcomes.py -q` → **19 passed** (one named test per status + invariant guards).

- [x] **13** — Refactor all canonical exit paths — spec §1
  - **Do:** Audit every orchestrator exit where no executable plan is produced. Set `canonical_planning_outcome` on state; **do not** set `evidence_plan` on clarification or failure paths.
  - **Do:** Fix resume status to `normalized_status() == "awaiting_clarification"`. On clarification answer: transactional resume → merge answer → re-run `known_detail_completion` or `post_guided_completeness` (user answer is **not** automatically sufficient for `CanonicalPlanningInput`).
  - **Do:** Update downstream nodes to branch on `canonical_planning_outcome.status` only — never `EvidencePlan.model_validate` on non-`planned` outcomes.
  - **Verify:** `pytest app/tests/test_canonical_planning_outcomes.py app/tests/test_canonical_architecture_complete.py -q`
  - **Depends on:** 12
  - **Evidence:** Four partial-`EvidencePlan` sources removed, not one:
    1. `canonical_planning_orchestrator.py` clarification exit — now emits `canonical_planning_outcome` and **pops** `evidence_plan`; the planned exit emits a `planned` outcome carrying the committed plan.
    2. `canonical_mode.build_canonical_failure_state` — synthesised `{reasons, canonical_failure}` when no plan existed (ten missing required fields). Now only annotates an already-valid plan; otherwise records the failure alone. Also fixed `answer_mode = outcome`, which wrote the non-literal values `"policy_blocked"` / `"clarification_required"` into a closed `AnswerMode` enum and corrupted otherwise-valid plans.
    3. `pipeline._graph_node_planning_decision_from_canonical` — required `evidence_plan` before computing `planning_decision`. On a non-planned outcome it now computes the decision with `evidence_plan=None`. **This one was a live safety regression:** without `planning_decision`, `path_type` was never `unsafe_blocked`, so blocked containment requests reported `human_review.reason="policy_checks_passed"` instead of `"unsafe_action_blocked"` — caught by 27 unsafe/containment tests before commit.
    4. `pipeline` dispatch branch — a missing plan was labelled `planning_failed`; non-planned outcomes now route to `build_non_planned_dispatch_state` (`dispatch_source="canonical_non_planned"`), so clarification is no longer misreported as a failure.
  - **Evidence (resume, spec §5):** the status comparison used the raw `"clarification_required"` while `save_clarification_handoff` persists `"awaiting_clarification"`, so **resume never matched and the analyst's answer was silently dropped**. Now compares `normalized_status()`. Fixing it exposed that the resume branch had never executed: its `intent_classification` stub omitted `query_type`/`confidence`/`confidence_band` (required by `IntentClassification`) and used the non-literal `query_type="ask_for_investigation"`. Both fixed. Live two-turn probe: turn 1 → `clarification_required` v1, no committed plan; turn 2 with `handoff_resume` → `planned` with a committed `ResourcePlan`, handoff v2 at `plan_committed`.
  - **Verified:** `pytest app/tests/test_canonical_planning_outcomes.py app/tests/test_canonical_clarification_contract.py app/tests/test_canonical_planning_architecture.py app/tests/test_canonical_handoff_invariants.py app/tests/test_canonical_architecture_complete.py app/tests/test_dual_runtime_lane_parity.py app/tests/test_resource_plan_authority.py app/tests/test_state_channel_parity.py -q` → **82 passed**.

- [x] **14** — Gate 1: clarification + sentinel — spec §1, §12
  - **Do:** Run targeted clarification tests + sentinel immediately after items 12–13; do not proceed to item 15 until pass.
  - **Do (rev 9a):** Second acceptance signal — re-run the clean-answer eval and confirm the 12 rows listed in item 15 return to pass (`total=120`, `critical=0` from the `EvidencePlan` class). Regenerate `docs/evals/soc_clean_answer_eval_*` and `langgraph_dual_parity_*` only after this passes; assert `base_105_loaded == 105` in the regenerated summary, since the `EXPECTED_105_COUNT` guard is conditional on `include_105` and will not catch a collapsed corpus on its own.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
      app/tests/test_canonical_planning_outcomes.py \
      app/tests/test_canonical_architecture_complete.py -k clarification -q
    PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check
    ```
  - **Depends on:** 13
  - **Stop:** Sentinel fails twice → stop and report
  - **Evidence (partial — clarification criteria met, sentinel blocked on a pre-existing baseline):**
    - **Clean-answer eval: PASS.** `total=120 pass=118 review=2 fail=0 critical=0`, `base_105_loaded=105`. All **12** rows listed in item 15 return to pass. The 2 REVIEW rows (`demo.sop-only_query`, `manual.brute_force_sop`, both `sop_incident_narrative`) are **not** from this batch — reproduced on the Phase 1 commit with this batch stashed.
    - **Clarification invariants: verified on a live turn.** No `evidence_plan` in state, `outcome.resource_plan is None`, `get_committed_resource_plan(...) is None`, question and `unresolved_fields` present, handoff persisted at `awaiting_clarification`.
    - **Full pytest: no regressions.** `190 failed, 4096 passed` vs the batch baseline `203 failed, 4051 passed` — **13 baseline failures fixed, 0 new** (set-diffed, not counted).
    - **Sentinel: PASS 17/17** (resolved in rev 9c — see below). At the time this batch landed it was FAIL, with drift inherited from the Phase 1 routing rewire rather than from clarification.
    - **Clean-answer eval: 120/120 PASS, 0 REVIEW, 0 FAIL, `base_105_loaded=105`** after rev 9c. The 2 `sop_incident_narrative` REVIEW rows were fixed by the same routing corrections.

- [ ] **15** — Pytest failure inventory — spec §2
  - **Do:** Run full pytest once; capture to `docs/evals/canonical_phase2_failure_inventory.md` with columns: test file, test name, failure category, old assumption, new canonical expectation, code fix or test fix.
  - **Do:** Categorize using **exact** spec labels:
    - **A** — tests assuming canonical planning can be disabled
    - **B** — tests expecting legacy `query_to_intent` or `evidence_planning`
    - **C** — tests expecting live `/chat` to attach `ResourcePlan` through old planner
    - **D** — tests expecting legacy dispatch fallback
    - **E** — clarification `EvidencePlan` contract failures
    - **F** — configuration tests referencing removed flags
    - **G** — genuine regressions unrelated to test assumptions
  - **Do:** Do not patch tests blindly; do not skip/xfail/weaken governance tests; do not add global compatibility shims.
  - **Pre-seeded rows (measured 2026-07-25 at commit `ceb7b19`: `4039 passed, 210 failed, 5 skipped, 6 xfailed`):**

    | Test | Category | Note |
    |------|----------|------|
    | ~~`test_t2_spl_native_live::test_t2_never_execution_eligible_or_mcp_allowed`~~ **RESOLVED 2026-07-25** — re-gated behind catalogue match; test passes untouched (9/9 in file). See rev 9b. | **G — governance posture regression** | With `control_plane_enabled` removed, the 2026-07 all-tier MCP grant (`evidence_planner.py:495`) became unconditional, so T2 out-of-catalogue turns now report `mcp_allowed=true` where the test requires `(False, None)`. **Not a test-assumption failure — a posture change on out-of-catalogue paths.** Executability itself is intact: `execution_eligible` stays false, `executed_spl` stays `None`, and the MCP gate plus per-call confirmation still apply, so this is a *grant-surface* regression, not an execution hole. **Do not resolve by editing the test.** Requires an explicit decision: re-gate the all-tier grant behind a canonical-planning condition, or accept the widened surface with COE sign-off (cf. `plans/2026-06-16_1258` §13.5). Record the decision in the completion report. |
    | Eval harnesses referencing `settings.control_plane_enabled` | **F** | Fixed ahead of item 15 — see the rev 9a drift-log entry; harnesses raised `AttributeError` on profile entry. |
    | Sentinel baseline drift (15/17 rows: `intent_family=None`, `match_path=None`, `draft_spl_present=False`, route/severity deltas) | **B/C** | Phase 1 routing rewire measured against a pre-canonical baseline. Blocks item 14 sign-off; not a clarification defect (confirmed by stashing the Gate 1 batch). Decide per row: canonical behaviour is correct → re-baseline; or canonical behaviour is wrong → fix routing. |
    | 12 clean-answer eval rows (`q0.q008`, `q0.q023`, `q0.q059`, `q0.q060`, `q0.q079`, `q0.q086`, `q0.q089`, `demo.successful_login_after_failures`, `demo.dns_beaconing_candidate`, `manual.alt0891_hybrid`, `manual.dns_beaconing`, `manual.mitre_no_context`) | **E** | Same defect as the sentinel: partial clarification dict from `canonical_planning_orchestrator.py:396-402` fails `EvidencePlan.model_validate` with 9 missing required fields. Use as a second acceptance signal for item 14 — all 12 must return to pass after items 12–13. |

  - **Verify:** Inventory row count matches pytest failure summary
  - **Depends on:** 14
  - **Evidence:** _(filled at check-off)_

- [ ] **16** — Canonical test helper — spec §2
  - **Do:** Add `backend/app/tests/support/canonical_flow.py`: `run_canonical_flow(query, *, handoff_resume=None, session_id=...)` through production flow:
    ```text
    understand_query → canonical orchestration → CanonicalPlanningInput
    → plan_evidence_from_canonical → committed ResourcePlan or typed non-executable outcome
    ```
    Must not bypass runtime contracts.
  - **Verify:** Helper used in ≥3 updated tests; `pytest app/tests/test_canonical_flow_helper.py -q`
  - **Depends on:** 12
  - **Evidence:** _(filled at check-off)_

- [ ] **17** — Eliminate all pytest failures — spec §2
  - **Do:** Fix per inventory order: **F** → **E** → **A/B/C/D** → **G**. Remove `_attach_resource_plan` from production runtime; isolate test composition in `backend/app/tests/support/compose_resource_plan_testutil.py` under explicit `TEST_AUTHORITY` only. Search all callers before removal. Do not make `_attach_resource_plan` silently restore old live behaviour.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` → **0 failed**
  - **Depends on:** 15, 16
  - **Evidence:** _(filled at check-off)_

- [ ] **18a** — Migration deployment and readiness — rev 9 (blocks 18, 19a, 24)
  - **Context:** `canonical_handoff_repository.py::_ensure_schema` executes `0004_canonical_handoffs.sql` from the live request path on first use, and `backend/scripts/migrate_ai_soc_db.py` currently has **zero callers** (not in `docker-compose.yml`, no entrypoint, not in CI). Schema exists today only as a side effect of runtime DDL. Fail-closed persistence (item 18) on top of that = live `/chat` hard-failure in any environment whose migrations were never run, and `0005` constraints (item 18) would never be applied because the runtime path is hardcoded to `0004`.
  - **Do:** Delete `_ensure_schema` / `_SCHEMA_READY` / `_MIGRATION_PATH` from `canonical_handoff_repository.py`. No runtime module may read or execute a `.sql` file (locked decision 14).
  - **Do:** Wire `backend/scripts/migrate_ai_soc_db.py` into the deploy path (backend container entrypoint or an explicit documented ops step in `docs/`), idempotent and safe to re-run. Preserve `schema_migrations` bookkeeping; the runner currently applies every file unconditionally — make it skip versions already recorded.
  - **Do:** Add a readiness check (startup log + `/health` detail or `readiness` field) asserting `schema_migrations` contains `0001`–`0005`. Missing migration = loud readiness failure with the exact remediation command, not a silent lazy create.
  - **Do:** Record in the completion report which environments (dev container, VPS prod) had migrations applied and when.
  - **Verify:** `rg -n '\.sql' backend/app --glob '!**/migrations/**'` → no runtime reads; `docker compose exec backend python scripts/migrate_ai_soc_db.py` twice → second run is a no-op; `pytest app/tests/test_migration_readiness.py -q`
  - **Depends on:** none
  - **Evidence:** _(filled at check-off)_

- [ ] **19a** — Canonical DB unit-of-work and pool — rev 9 (blocks 19, 20, 24)
  - **Context:** `canonical_handoff_repository.py` opens a fresh `asyncpg.connect()` inside its own `asyncio.run()` per method (`_run`, `_with_conn`), and `durable_planning_telemetry.py` does the same per event. Two consequences: (a) item 19's `load … FOR UPDATE` → merge → create version → supersede → commit **cannot** be one transaction, because each repository call is a different connection and the row lock is released before the merge; (b) ~35 fresh TCP+auth connections per turn, serially, inside the SSE executor thread (`routes_chat_stream.py::_sse_event_stream` runs the pipeline via `run_in_executor`, so `asyncio.run` is legal but each call pays full connect cost).
  - **Do:** Add `backend/app/chat/canonical_db.py`: a single lazily-created `asyncpg` pool + `canonical_unit_of_work()` context manager yielding one connection inside `async with conn.transaction()`. Bridge sync callers through one `asyncio.run` per unit-of-work, not per statement.
  - **Do:** Refactor repository + idempotency + telemetry writers to accept an injected connection/transaction handle. A caller composing several operations gets one transaction; a standalone call opens its own.
  - **Do:** Do not introduce a fourth data-access pattern (locked decision 15). Document the boundary vs SQLAlchemy `app/db/session.py` and `app/connectors/telemetry/db.py` in the completion report.
  - **Do:** Bound connection churn: per-turn planning events buffer and flush in one transaction (audit-critical events flush immediately per item 21b). Record measured connections-per-turn and added p50 latency.
  - **Verify:** `pytest app/tests/test_canonical_db_unit_of_work.py -q` (rollback discards all writes in the unit; two operations in one unit share one connection; pool reused across turns); connections-per-turn ≤ 5 measured on a live smoke turn
  - **Depends on:** 18a
  - **Evidence:** _(filled at check-off)_

- [ ] **10** — Durable telemetry foundation — *(moved ahead of 18/19/20 in rev 9)*
  - **Do:** `durable_planning_telemetry.py` persists to `canonical_planning_events` through the item-19a unit-of-work; `planning_telemetry.py` delegates; wire interim events until item 21 completes the full catalog. Apply the refined telemetry failure policy (locked decision 12 / item 21b).
  - **Do:** Remove the live-path memory leak: the `except` branch of `persist_planning_event` currently appends to the global `_TEST_EVENTS` list on production paths — unbounded growth plus prod code writing a test store. Test capture is fixture-injected only (`use_test_event_store()`), same rule as item 18 applies to handoffs.
  - **Do:** Reconcile with the existing sink config. `durable_planning_telemetry` ignores `ai_soc_telemetry_sink` / `telemetry_mode` and keys only off `database_url`. Define and implement the interaction explicitly: diagnostic events honour the sink; audit-critical events are not sink-optional (a configuration that would drop them is rejected at startup).
  - **Verify:** `pytest app/tests/test_canonical_planning_architecture.py -k t4_resolves -q`; `rg -n '_TEST_EVENTS' backend/app/chat/durable_planning_telemetry.py` → no writes outside fixture-injected capture
  - **Depends on:** 17, 19a
  - **Evidence:** _(foundation partial; full catalog = item 21)_ — rev 9a landed the `_TEST_EVENTS` live-path removal: a write failure now logs with `event`/`trace_id` context and does **not** fall back into the fixture store. Pinned by `test_persist_failure_does_not_populate_fixture_store`. Remaining: unit-of-work wiring (item 19a) and the sink reconciliation.

- [ ] **21a** — Typed telemetry correlation outside `minimize` — rev 9 (part of telemetry foundation)
  - **Context (verified):** `minimize()` **deletes** any key containing `session_id` — it is in `_SECRET_KEY_PARTS` in `app/connectors/telemetry/redaction.py`. Proven:
    ```text
    minimize({'session_id':'abc','trace_id':'t1','handoff_id':'h','user_query':'…'})
    → {'trace_id': 't1', 'handoff_id': 'h', 'user_query': '…'}
    ```
    `persist_planning_event` minimizes **first**, then reads `sanitized.get("session_id")` for the column — so `canonical_planning_events.session_id` is always NULL. That breaks the completion criterion "all persisted planning events contain required correlation fields" and item 21's multi-worker correlation. `_sanitize_payload` in `canonical_handoff_repository.py` has the same shape.
  - **Do:** Bind correlation columns (`trace_id`, `session_id`, `turn_id`, `decision_id`, `parent_decision_id`, `handoff_id`, `handoff_version`, `resource_plan_id`, `node_name`, `status`, `duration_ms`, `error_category`) from the **unminimized** source, mirroring the existing `app/connectors/telemetry/db.py` pattern. Apply `minimize()` only to the free-form `payload` jsonb.
  - **Do:** Confirm SOC content policy for the jsonb payload — `user_query` / `original_query` survive `minimize()` by design. Either keep them (documented, covered by item 28 retention) or truncate/hash; state the decision.
  - **Verify:** `pytest app/tests/test_canonical_telemetry_correlation.py -q` — asserts non-null `session_id` and `handoff_id` on a persisted event, and that a secret-bearing payload is still redacted
  - **Depends on:** 10
  - **Evidence:** _partially landed at rev 9a_ — `_CORRELATION_COLUMNS` + `_correlation()` in `durable_planning_telemetry.py` bind columns from the raw event; `test_canonical_telemetry_correlation.py` green (4 passed). Remaining for check-off: the same treatment for `canonical_handoff_repository._sanitize_payload`, the `user_query` / `original_query` retention decision, and the full column set once item 21's catalog lands.

- [ ] **18** — Remove live memory handoff fallback — spec §4
  - **Do:** Refactor `canonical_handoff_repository.py`: `_TEST_STORE` only via `use_in_memory_store_for_tests()` fixture injection; **never** on live path (including `_disabled()` and write-failure catch). On DB unavailable: `PersistenceError` → `persistence_failed` outcome → `request.failed` telemetry → no in-memory continuation.
  - **Do:** If `0004_canonical_handoffs.sql` already applied, add `backend/app/db/migrations/0005_canonical_planning_cutover_constraints.sql` (do **not** edit `0004`) for missing handoff/commit unique constraints and clarification-resumption indexes.
  - **Do:** Add `backend/app/tests/test_canonical_handoff_persistence_failclosed.py` covering: DB unavailable during clarification persistence; DB unavailable during handoff resumption; DB unavailable during ResourcePlan commit → no execution. (Process restart and second-worker cases validated in item 24.)
  - **Verify:** `pytest app/tests/test_canonical_handoff_persistence_failclosed.py -q`
  - **Depends on:** 12, 18a, 19a, 10, 21a
  - **Evidence:** _(filled at check-off)_

- [ ] **19** — Transactional clarification resumption — spec §5
  - **Do:** On clarification response: `load pending handoff WITH LOCK` → validate session ownership → validate handoff status → validate `handoff_version` → merge answer → create next version → mark prior superseded/resumed → commit transaction → continue from saved stage.
  - **Do:** Repository methods: `load_pending_for_update`, `supersede_version`, `merge_clarification_answer` (`SELECT … FOR UPDATE`, unique `(handoff_id, handoff_version)`). Controls: one answer advances version once; duplicate answers return existing next version; two workers cannot create two versions; completed/failed/expired cannot resume; wrong pending handoff rejected; multiple pending handoffs disambiguated deterministically; material goal change supersedes with linked new handoff.
  - **Do:** Preserve across versions: `original_skill`, `original_use_case_id`, `original_answer_goal`, `initial_tier`, `resolved_tier`, prior tool results, field provenance, conflicts, unresolved fields.
  - **Do:** All five steps run inside **one** `canonical_unit_of_work()` from item 19a — a lock acquired on one connection and released before the merge is not a control.
  - **Verify:** `pytest app/tests/test_canonical_handoff_clarification_integration.py -q` (Postgres — item 24)
  - **Depends on:** 18, 19a
  - **Evidence:** _(filled at check-off)_

- [ ] **21b** — Audit-critical vs diagnostic persistence policy — rev 9 (blocks 20 and final telemetry acceptance)
  - **Context:** Locked decision 12 (rev 8) said "telemetry persistence failure before side-effecting execution → fail closed" for **all** telemetry. That contradicts the shipped COE invariant recorded in `CLAUDE.md` — trace telemetry is "redacted, best-effort, **never breaks chat**" — and contradicts supported configurations `AI_SOC_TELEMETRY_SINK=db|file|none` and `TELEMETRY_MODE=none` (the governance regression harness runs with `TELEMETRY_MODE=none`). Left unresolved, item 21 would either break the regression harness or quietly abandon fail-closed.
  - **Do:** Classify all 28 events in `docs/architecture/canonical_telemetry_coverage.md` as **audit-critical** or **diagnostic**. Audit-critical (proposed, confirm at execution): `handoff.persisted`, `handoff.resumed`, `resource_plan.created`, `execution.started`, `execution_step.started`, `execution_step.completed`, `execution_step.failed`, `request.failed`. Everything else diagnostic.
  - **Do:** Implement the split: audit-critical write failure before a side-effecting step → `persistence_failed` outcome, no execution; diagnostic write failure → WARNING log with `error_category`, surfaced in the trace, chat proceeds. Never a silent drop in either class.
  - **Do:** Define sink interaction: diagnostic events honour `ai_soc_telemetry_sink`; a configuration that would discard audit-critical events (`sink=none` with execution enabled) is rejected at startup with an explicit message. Confirm the governance regression harness path stays green under `TELEMETRY_MODE=none`.
  - **Do:** Update the `CLAUDE.md` COE observability bullet so the "never breaks chat" statement is scoped to diagnostic telemetry.
  - **Verify:** `pytest app/tests/test_telemetry_persistence_policy.py -q` (audit-critical failure blocks execution; diagnostic failure does not block a read-only response; neither is silently dropped); `TELEMETRY_MODE=none PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json` → 6/6
  - **Depends on:** 10, 21a
  - **Evidence:** _(filled at check-off)_

- [ ] **20** — Execution idempotency implementation — spec §3
  - **Do:** Add `backend/app/chat/canonical_execution_idempotency.py` using `canonical_execution_idempotency` table. Add lease/index constraints via `0005` migration if not in `0004`. Integrate into `planner/executor.py` `execute_plan_dispatch` **and every execution path** including guided hybrid.
  - **Do:** Idempotency key = `resource_plan_id` + `handoff_id` + `handoff_version` + `step_id` + **operation identity**. Lifecycle: `pending` → `running` → `completed` | `failed_retryable` | `failed_terminal`.
  - **Do:** Per-step transaction flow: (1) start txn, (2) acquire/create record, (3) if `completed` return stored result, (4) if `running` under valid lease do not execute concurrently, (5) recover stale lease per documented policy, (6) mark `running` before tool invoke, (7) persist result + terminal status atomically. Separate read-only (retryable) vs side-effecting (no replay unless tool contract + stable key supports idempotency).
  - **Do:** Invariant: **a committed ResourcePlan step can produce at most one side effect.**
  - **Do:** Add `backend/app/tests/test_execution_idempotency.py` with **repository/unit tests first** (named tests): duplicate dispatch; concurrent dispatch two workers; worker crash after `running`; replay after completion; retryable read-only failure; side-effecting step timeout; same plan different step IDs; mismatched handoff version.
  - **Do:** Per-step transactions use `canonical_unit_of_work()` (item 19a) — acquire/lease/mark-running/persist-result must not span separate connections.
  - **Verify:** `pytest app/tests/test_execution_idempotency.py -q`
  - **Depends on:** 18, 19a, 21b
  - **Evidence:** _(filled at check-off)_

- [ ] **21** — Complete durable telemetry catalog — spec §6
  - **Do:** Wire **all 28 events** from real emitting nodes (not merely helpers):
    ```text
    query_understanding.completed, lane_router.decided, known_completeness.evaluated,
    guided_resolution.started, guided_intent.resolved, tier.resolved,
    detail_tool.selected, detail_tool.started, detail_tool.completed, detail_tool.failed,
    detail_merge.completed, post_guided_completeness.evaluated, clarification.requested,
    handoff.persisted, handoff.resumed, planner_handoff.created, planner_handoff.consumed,
    resource_plan.created, resource_plan.commit_reused,
    execution.started, execution_step.started, execution_step.completed, execution_step.failed,
    execution.completed, response.validated, response.generated,
    request.completed, request.failed
    ```
  - **Do:** Add `docs/architecture/canonical_telemetry_coverage.md`: per event — emitting node, success condition, failure condition, required payload, persistence confirmation.
  - **Do:** Persisted events carry where applicable: `trace_id`, `session_id`, `turn_id`, `decision_id`, `parent_decision_id`, `handoff_id`, `handoff_version`, `resource_plan_id`, `node_name`, `node_version`, `contract_version`, `initial_tier`, `resolved_tier`, `processing_lane`, `answer_goal`, `primary_skill`, `original_skill`, `status`, `duration_ms`, `error_category`. Redact secrets/raw SOC content.
  - **Do:** Terminal consistency: success → exactly one `request.completed`; terminal failure → exactly one `request.failed`; clarification → `clarification.requested` without false `request.completed`. Events survive restart; multi-worker correlation; ordering reconstructable; duplicate events have stable IDs or dedup keys.
  - **Do:** Correlation fields are bound as typed columns per item 21a — do **not** read them back out of a `minimize()`d dict.
  - **Do:** Telemetry failure policy per item 21b classification: audit-critical failure fails closed before side-effecting execution; diagnostic failure degrades loudly. Never silently drop either class.
  - **Verify:** `pytest app/tests/test_canonical_telemetry_coverage.py -q` (one test per canonical functional path)
  - **Depends on:** 10, 21a, 21b, 13, 20
  - **Evidence:** _(filled at check-off)_

- [ ] **22** — Response validation semantics — spec §7
  - **Do:** Rewrite `response_validation.py` outcome-aware. Before `response.validated`, check: canonical outcome status; `resource_plan_id` when executable; execution terminal state; required step completion; required evidence availability; explicit limitations; tool failures surfaced; `answer_goal` satisfied; citations retained; no claim of unexecuted action; policy restrictions respected.
  - **Do:** Rules: no `response.generated` on assembly failure; no `request.completed` before response generation succeeds; `clarification_required` validates unresolved fields/questions from `CanonicalPlanningOutcome.clarification` (no `EvidencePlan` required); failures identify typed failure without masquerading as success; no action-performed claims without completed execution step.
  - **Do:** Add `backend/app/tests/test_response_validation_canonical.py` negative tests: missing required evidence; failed execution step; unexecuted remediation claim; missing knowledge citation; wrong `answer_goal`; `resource_plan` mismatch; response assembly failure.
  - **Verify:** `pytest app/tests/test_response_validation_canonical.py -q`
  - **Depends on:** 13, 21
  - **Evidence:** _(filled at check-off)_

- [ ] **23** — ResourcePlan authority audit — spec §10
  - **Do:** Search `ResourcePlan(`, `compose_resource_plan`, `compose_guided_resource_plan`, `commit_resource_plan`, `resource_plan =`. Classify each: `approved_final_planner` | `deserialization` | `test_fixture` | `validation` | `execution_read` | `violation`.
  - **Do:** Approved runtime authority only: `plan_evidence_from_canonical` → `resource_plan_authority` → `compose_resource_plan` → `commit_resource_plan`. Guided hybrid, executor, response composer, telemetry must never create/modify committed plan.
  - **Do:** Strengthen `test_resource_plan_authority.py` as static guard against future violations.
  - **Verify:** `pytest app/tests/test_resource_plan_authority.py -q`; classification table in completion report §11
  - **Depends on:** 17
  - **Evidence:** _(filled at check-off)_

- [ ] **24** — Postgres integration tests — spec §11
  - **Do:** Add `backend/app/tests/integration/conftest.py` using project Postgres (`DATABASE_URL`). **Do not mock** transactional behaviour under test.
  - **Do:** Cover: handoff creation; unique handoff version; concurrent version creation; ResourcePlan commit race; execution-idempotency race; clarification resume race; telemetry persistence; process restart simulation; expired handoff; transaction rollback; database unavailable. Verify unique constraints and locking under concurrency.
  - **Do:** Clarification integration (item 19): cross-process restart; cross-worker resume; duplicate answer; concurrent duplicate answer; expired handoff; completed handoff; multiple pending handoffs; material goal change. Process restart and second-worker handoff cases from item 18.
  - **Do:** **Local skip policy:** tests may skip when Postgres is unavailable in an unsupported local environment. **Completion gate:** final CI verification job **must** provision PostgreSQL and pass the complete integration suite **without skips** — plan cannot be marked Done if integration tests were skipped in CI.
  - **Verify:** `pytest app/tests/integration/ -q` (0 skipped in CI completion job)
  - **Depends on:** 18, 19, 20, 21
  - **Evidence:** _(filled at check-off)_

- [ ] **25** — Remove obsolete configuration — spec §8
  - **Scope split (rev 9):** this item removes the **environment/config keys only**. The runtime *trace field* `control_plane_enabled` (`pipeline.py:4190`, `synthesis/governed_answer_composer.py:189`, four eval harnesses, 11 `app/demo/captures/*.json`) is a response-contract change and is handled in items 26 + 26a. Removing the env var and removing the trace field are not the same change; do not conflate them.
  - **Do:** Rewrite the `CLAUDE.md` statement "Chat control plane … is implemented, gated by `CONTROL_PLANE_ENABLED` (default `false`)" — canonical planning is unconditional, so that sentence becomes false at cutover. Also reconcile `plans/2026-06-02_chat-control-plane-master.md` (runtime references only; do not rewrite its history).
  - **Do:** Note that `AI_SOC_CANONICAL_PLANNING_ENABLED`, `AI_SOC_HANDOFF_STORE_BACKEND`, `AI_SOC_HANDOFF_STORE_FILE_DIR` are already retired-with-warning at `config.py:522-531`; this item removes the warning shim, not just the keys.
  - **Do:** Remove `CONTROL_PLANE_ENABLED`, `AI_SOC_CANONICAL_PLANNING_ENABLED`, `AI_SOC_HANDOFF_STORE_BACKEND`, `AI_SOC_HANDOFF_STORE_FILE_DIR` from: `.env`, `.env.example`, `.env.*.example`, `env/profiles/*`, `docker-compose.yml`, K8s manifests (if any), CI configuration, `CLAUDE.md`, architecture docs, plan docs (runtime refs), README files, test fixtures, deployment scripts, startup output, eval harness defaults.
  - **Do:** After cleanup: remove retired-env warnings from `config.py`; remove tests expecting warnings; update `test_coe_rollout_config_sanity.py`. Do **not** rely on `extra="ignore"` as final solution for these four keys.
  - **Do:** If hook blocks `.env.example`, follow repo-approved edit workflow — do not leave stale.
  - **Verify:** `rg 'CONTROL_PLANE_ENABLED|AI_SOC_CANONICAL_PLANNING|HANDOFF_STORE' --glob '!**/migrations/**' --glob '!docs/evals/**'` → only historical notes marked non-runtime; `pytest app/tests/test_coe_rollout_config_sanity.py -q`
  - **Depends on:** 17
  - **Evidence:** _(filled at check-off)_

- [ ] **26** — Remove obsolete live-path compatibility code — spec §9
  - **Do:** Remove: `True` literals pretending to be `control_plane_enabled`; legacy trace fields implying optional canonical mode; test-only live composition branches in production modules; canonical-off route labels; unused `plan_dispatch_fallback` helpers; obsolete comments/dead branches. Update eval harnesses (`soc_clean_answer_eval`, `golden_answer_runner`, `langgraph_dual_parity`, etc.).
  - **Do:** `_attach_resource_plan` must be isolated test utility outside production runtime or removed entirely (search all callers first).
  - **Do:** Trace-field removal is a response-contract change — pair every removal with the fixture migration in item 26a. Do not delete a field that a capture or golden fixture still asserts without migrating it in the same commit.
  - **Verify:** `rg 'canonical.off|plan_dispatch_fallback|control_plane_enabled' backend/app/` → no runtime branches; only test fixtures or historical comments
  - **Depends on:** 17, 25
  - **Evidence:** _(filled at check-off)_

- [ ] **26a** — Experience Center purity and fixture migration — rev 9
  - **Context:** The plan (rev 8) never mentions the Experience Center. EC purity is a standing repo invariant — the EC path is deterministic fixture playback, emits no traces, and never runs live planning. Two exposures: (a) canonical nodes are now unconditional in the pipeline, so EC must be proven not to touch canonical persistence; (b) item 26 removes the `control_plane_enabled` trace field, which appears in 11 `backend/app/demo/captures/*.json` and in eval-harness expectations — a blind removal breaks EC replay and golden comparisons.
  - **Do:** Add `backend/app/tests/test_experience_center_canonical_purity.py`: running every scenario through `routes_scenarios.py::run_demo_scenario_fixture` produces **zero** `canonical_handoffs` rows, **zero** `canonical_planning_events`, **zero** `ResourcePlan` commits, and no `request.completed` / `request.failed` canonical terminal events. Assert against the injected test stores, not by mocking the assertion away.
  - **Do:** Migrate `app/demo/captures/*.json` and eval fixtures for any trace field removed in item 26. Decide and record one policy: field dropped from captures, or retained as a frozen historical key excluded from live-vs-capture diffing. EC governance panels (LLM sidecar, lineage, `live_llm_called=false`) must render unchanged after migration.
  - **Do:** Confirm EC answers stay byte-identical where no field was intentionally removed.
  - **Verify:** `pytest app/tests/test_experience_center_canonical_purity.py -q`; EC scenario replay diff shows only intentionally-removed keys
  - **Depends on:** 26
  - **Evidence:** _(filled at check-off)_

- [ ] **28** — Retention and purge — rev 9
  - **Context:** `canonical_handoffs.original_query` stores the raw analyst query (SOC content) and `canonical_planning_events.payload` retains `user_query` — `minimize()` masks secrets but does not remove query text. `canonical_handoffs` has `expires_at` with **no purge job**; `canonical_planning_events` has **no TTL at all** and grows unbounded per turn. Privacy/data-protection applies to SOC content the same way it applies to CRM records.
  - **Do:** Define retention windows for `canonical_handoffs` (expired + terminal rows) and `canonical_planning_events`. Align with whatever `ai_trace_runs` already does rather than inventing a second policy — reuse its purge mechanism if one exists.
  - **Do:** Implement purge (scheduled job or startup sweep), idempotent, bounded batch size, logged counts. Add the retention indexes to `0005` if not already present.
  - **Do:** Document retention + what SOC content each table holds in `docs/architecture/canonical_telemetry_coverage.md`.
  - **Verify:** `pytest app/tests/test_canonical_retention_purge.py -q` (expired rows removed; live rows untouched; purge is idempotent and bounded)
  - **Depends on:** 18a, 21a
  - **Evidence:** _(filled at check-off)_

- [ ] **11** — Intermediate canonical regression gate
  - **Do:** Re-run canonical architecture + invariant suites and sentinel after pytest migration (items 14–17) and before final cleanup gates. This is a **verification gate**, not an early implementation step.
  - **Verify:** `pytest app/tests/test_canonical_handoff_invariants.py app/tests/test_dual_runtime_lane_parity.py app/tests/test_canonical_planning_architecture.py -q`; `PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check`
  - **Depends on:** 14, 17
  - **Evidence:** _(filled at check-off)_

- [ ] **29** — Containerised `/chat` canonical smoke — rev 9
  - **Context:** Every gate in rev 8 is pytest-level, and item 24 is Postgres-but-in-process. Repo history says in-process green ≠ live green: LangGraph silently drops undeclared state channels, and `.env` drift has broken live paths while evals stayed green. A flagless cutover with no live probe has no safety net.
  - **Do:** Run through the running stack (`docker compose up -d`, real Postgres, real Nginx-fronted backend), one probe per canonical path: (1) T1 known-complete → plan committed + executed; (2) T1 with gap → clarification → answer → transactional resume → plan committed; (3) T3 near/semantic match; (4) T4 guided resolution; (5) T0 reference/knowledge-only; (6) policy-blocked outcome.
  - **Do:** For each probe assert from the **database**, not just the HTTP body: expected `canonical_planning_events` rows present with non-null `session_id` (item 21a), one terminal `request.completed`/`request.failed`, handoff row at the expected status/version, at most one side effect per committed step.
  - **Do:** Confirm migrations were applied by the deploy step (item 18a) in this environment — not by runtime DDL.
  - **Do:** Record per-probe latency and connections-per-turn; compare against the item-19a budget.
  - **Verify:** `scripts/smoke_canonical_paths.sh` (new) → 6/6 probes pass; DB assertions captured in the evidence
  - **Depends on:** 24, 21, 22, 26a
  - **Evidence:** _(filled at check-off)_

- [ ] **27** — Final verification gates + completion report — spec §12, §14
  - **Do:** Run gates in order; capture command output; produce 15-section completion report:
    1. Root cause + fix for clarification/sentinel failure
    2. Breakdown/disposition of all prior pytest failures
    3. Final full pytest result
    4. Final governance regression result
    5. Execution idempotency implementation
    6. Database transaction + locking strategy
    7. Clarification cross-worker/resumption results
    8. Complete telemetry event coverage table
    9. Response validation tests + results
    10. Files + configuration references removed
    11. ResourcePlan authority search results
    12. Postgres integration test results
    13. Dead legacy/compatibility code removed
    14. Final runtime diagram
    15. Any remaining gap
    16. **(rev 9)** Migration deployment: which environments were migrated, by which step, verified in `schema_migrations`
    17. **(rev 9)** Data-layer boundary: canonical unit-of-work vs SQLAlchemy vs telemetry connector; measured connections-per-turn
    18. **(rev 9)** Audit-critical vs diagnostic telemetry classification table + sink-config interaction
    19. **(rev 9)** Experience Center purity result + fixture keys migrated
    20. **(rev 9)** Retention/purge policy and measured table growth per turn
    21. **(rev 9)** Rollback posture: revert target commits, confirmation that `0004`/`0005` need no down-migration
  - **Verify:**
    1. **Gate 1:** item 14 commands (clarification tests + `eval_sentinel.py --check`)
    2. **Gate 2:** `pytest app/tests/test_canonical_* app/tests/test_resource_plan_authority.py app/tests/test_dual_runtime_lane_parity.py -q`
    3. **Gate 3:** `pytest app/tests/integration/ app/tests/test_execution_idempotency.py app/tests/test_canonical_telemetry_coverage.py -q` — **PostgreSQL required; 0 skipped**
    4. **Gate 3.5 (rev 9):** `scripts/smoke_canonical_paths.sh` against the running container stack → 6/6, DB assertions included
    5. **Gate 4:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` → 0 failed
    6. **Gate 5:** `./scripts/run_stage3_governance_regression.sh` → PASS
    7. **Gate 6:** repo search — no runtime-relevant removed variables or legacy planner/fallback terms
    8. **Gate 7 (rev 9):** `rg -n '\.sql' backend/app --glob '!**/migrations/**'` → no runtime DDL; EC purity + retention suites green
  - **Depends on:** 11, 14–26, 26a, 28, 29
  - **Evidence:** _(filled at check-off)_

---

## Prohibited shortcuts — spec §13

Do **not**:

- Reintroduce feature flags or shadow behaviour
- Restore legacy planner fallback
- Add memory fallback for DB failure on live path
- Skip failing E2E tests
- Broadly loosen `EvidencePlan` validation
- Add placeholder `ResourcePlan`s to clarification paths
- Mark failures xfail solely because expectations changed
- Weaken governance sentinel assertions
- Create another compatibility planner
- Claim completion while full pytest or governance regression fails
- **(rev 9)** Execute `.sql` files from runtime code, or rely on lazy `CREATE TABLE IF NOT EXISTS` instead of a deploy step
- **(rev 9)** Open a fresh connection per repository call and call it a transaction
- **(rev 9)** Read correlation fields back out of a `minimize()`d payload
- **(rev 9)** Append to a test store from a production code path on write failure
- **(rev 9)** Fail closed on diagnostic telemetry, or silently drop any telemetry class
- **(rev 9)** Delete a trace field without migrating the EC captures and golden fixtures that assert it
- **(rev 9)** Mark the plan Done on in-process green alone — Gate 3.5 live smoke is mandatory

---

## Execution discipline

```bash
.cursor/hooks/audit-plan-discipline.sh plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md
# then:
# loop-asap — execute plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md
```

**Stop conditions (Phase 2):** sentinel fails twice on item 14; full pytest fails twice on item 17 without inventory update; CI completion job runs integration suite without Postgres or with skips.

## Drift log

- 2026-07-24–25: Original plan (parser T0, dual handoffs, answer_mode lane lock).
- 2026-07-25 rev 5: Partial cutover — DB migration, authority guard, always-on `is_canonical_authoritative()`, legacy fallback removed from live pipeline. Drift log claimed governance PASS; **re-audited false** — sentinel + ~211 pytest failures remain.
- 2026-07-25 rev 7: Full alignment with user 14-section cutover spec.
- **2026-07-25 rev 8:** Fixed item 20↔24 dependency cycle; moved item 11 to intermediate gate (depends 14+17); clarification outcomes **without** `EvidencePlan`; corrected resume diagram; T0 knowledge execution rule; telemetry fail-closed policy; mandatory CI Postgres for item 24; positive completion criteria; dual-runtime single orchestration service; `0005` migration policy (do not edit `0004`).
- **2026-07-25 rev 9 (architecture review):** Seven items added after a repo-verified review. Corrections to rev 8:
  - **Status claim corrected.** Rev 8 said "Nothing in Phase 2 is implemented yet" — **false**. `durable_planning_telemetry.py`, `planning_telemetry.py`, and `response_validation.py` exist, and `validate_final_response` is already wired on the live path at `pipeline.py:4253`. Item 10 is partially built, not unstarted. (Rev 5 was already corrected once for a false PASS claim; do not repeat the pattern.)
  - **Item 19 was not implementable as written** — per-call `asyncpg.connect()` inside per-method `asyncio.run()` cannot hold `SELECT … FOR UPDATE` across a merge. → item **19a** (unit-of-work + pool), blocks 19, 20, 24.
  - **Migrations had no deploy path** — `_ensure_schema` executes `0004` from the live request path, and `scripts/migrate_ai_soc_db.py` has zero callers, so item 18's fail-closed posture would hard-fail unmigrated environments and `0005` would never be applied. → item **18a**, blocks 18, 19a, 24.
  - **Telemetry correlation was broken at the source** — `minimize()` deletes any key containing `session_id` (it is in `_SECRET_KEY_PARTS`), and `persist_planning_event` minimizes before reading the column value, so `canonical_planning_events.session_id` is always NULL. → item **21a**.
  - **Blanket fail-closed telemetry contradicted the shipped COE invariant** ("best-effort, never breaks chat") and the supported `TELEMETRY_MODE=none` harness path. → item **21b** splits audit-critical from diagnostic; locked decision 12 rewritten.
  - **Experience Center was absent from the plan** while item 26 would delete a trace field asserted by 11 `app/demo/captures/*.json`. → item **26a**.
  - **No retention** for handoff/event tables holding raw SOC query text. → item **28**.
  - **All gates were in-process.** → item **29** containerised live smoke, Gate 3.5.
  - Item 10 moved ahead of 18/19/20 (telemetry is a prerequisite of the items that emit it). Item 25 scope split: env keys here, trace-field contract change in 26/26a. Locked decisions 14–18 added.
  - **Implementation status: Phase 2 not started, except a partial item 10 (durable telemetry + response validation) already on the live path.**
- **2026-07-25 rev 9a (Phase 1 commit review):** Phase 1 committed as `ceb7b19`; plan rev 9 as `2870ade`. Four findings from the pre-commit invariant check, three fixed immediately:
  - **State channels dropped on the RP graph edge (FIXED, `ceb7b19`).** 10 undeclared canonical keys on `ChatPipelineState`; see item 9 evidence for the full list, consumers, and the negative control. Third occurrence of this class in the repo — now guarded at the graph edge.
  - **Eval harnesses broken by the flag removal (FIXED).** `settings.control_plane_enabled` no longer exists, but five harnesses still read it. `soc_clean_answer_eval.clean_answer_profile` (`:781`), `langgraph_dual_parity` (`:426`), and `spl_draft_preview_eval` (`:100`) call bare `getattr(settings, name)` and raised `AttributeError` on profile entry; `golden_answer_runner` (`:480`) and `powergrid_soc_question_eval` (`:240`) guard with `hasattr`/default and instead recorded a **silently wrong** `control_plane_enabled: false` in their flag snapshots. Flag removed from `_PROFILE_FLAGS`, `_PROFILE_FLAGS_ON/OFF`, `SAFE_SETTING_DEFAULTS`, `_PROFILE_FLAG_NAMES`, the `CONTROL_PLANE_ENABLED` env override, and the golden-runner constraints block. The `powergrid` reads at `:342/:344/:1197` are payload-side (`composer.get(...)`) and still valid while `governed_answer_composer.py:189` emits the field — item 26 owns their removal.
  - **Eval report artifacts overwritten by a partial run (RESOLVED by restore; regeneration still pending Gate 1).** The working-tree `docs/evals/soc_clean_answer_eval_*` and `langgraph_dual_parity_*` reports had been regenerated on 2026-07-25T06:29-06:30Z from a run with `include_105=False`: **105-question rows loaded dropped 105 → 0, total evaluated 120 → 8**, while the summaries still read `Verdict PASS 8/0/0` and the parity report lowered its own `expected minimum` from 120 to 8. The `EXPECTED_105_COUNT` guard at `soc_clean_answer_eval.py:815` did not fire because it is conditional on `include_105`. A green-looking report over a collapsed corpus. Those uncommitted artifacts were **discarded** (`git checkout -- docs/evals/`), restoring the last full-run baseline (120 evaluated / 105 loaded, 2026-07-24T05:50Z). Do **not** regenerate them until Gate 1 passes — see the next bullet for why a regeneration today would bake in 12 criticals. Item 27 must assert `base_105_loaded == 105` rather than trusting the verdict line.
  - **Clean-answer eval reproduces the Gate 1 blocker on 12 rows (OPEN — items 12/13).** With the harness flag breakage fixed, the corpus loads again (`total=120 pass=106 review=2 fail=12 critical=12`). All 12 criticals are the same defect, category **E**: `ValidationError: 9 validation errors for EvidencePlan — rag_phase / needs_rag / needs_spl / needs_mcp / needs_mitre / spl_allowed / mcp_allowed / policy_context_required / policy_context_recommended Field required`, from `input_value={'answer_mode': 'clarification', …, 'resource_plan': None}` — i.e. the partial dict written at `canonical_planning_orchestrator.py:396-402` hitting `EvidencePlan.model_validate` downstream. Affected rows: `q0.q008`, `q0.q023`, `q0.q059`, `q0.q060`, `q0.q079`, `q0.q086`, `q0.q089`, `demo.successful_login_after_failures`, `demo.dns_beaconing_candidate`, `manual.alt0891_hybrid`, `manual.dns_beaconing`, `manual.mitre_no_context`. This is independent live-corpus confirmation of the rev 8 root-cause analysis, and it gives item 14 a second acceptance signal beyond the sentinel: after items 12–13, these 12 rows must return to pass.
  - **Offline eval runs attempt live DB connections (NOTED — item 18a/19a).** `DATABASE_URL` points at the Docker service host `postgres`, which does not resolve from the VPS host, so every planning event and handoff write raises `socket.gaierror` and logs a full traceback. Currently swallowed (`planning_event_persist_failed`, `canonical_handoff_save_failed`, `canonical_handoff_load_failed`), so it is log noise rather than failure — but it means offline harnesses attempt real connections per event, and `_disabled()`'s heuristic (empty URL or the `change-me@postgres` sentinel) does not cover an unreachable host. Item 18a's readiness check and item 19a's pool must define offline-harness behaviour explicitly rather than relying on exception swallowing, which item 18 removes.
  - **`mcp_allowed=true` on T2 (OPEN — classified G).** See the item 15 pre-seeded inventory table. Decision required; not resolvable by editing the test.
  - Also fixed ahead of their items: correlation fields now bound from the raw event rather than the `minimize()`d copy (item 21a), and the live-path `_TEST_EVENTS` fallback on write failure removed (item 10). Both pinned by `test_canonical_telemetry_correlation.py` (5 tests, including a `minimize()`-still-drops-`session_id` pin so the workaround cannot rot silently).
- **2026-07-25 rev 9b (Gate 1 batch — items 12, 13 + MCP re-gate):** Typed outcome contract, all non-planned exit paths, resume-status fix, and least-privilege MCP restored. Items 12 and 13 checked off with evidence; item 14 deliberately left unchecked (sentinel).
  - **Four** partial-`EvidencePlan` sources existed, not the one the root-cause diagram showed — orchestrator clarification exit, `build_canonical_failure_state`, `_graph_node_planning_decision_from_canonical`, and the dispatch branch. See item 13 evidence.
  - **A live safety regression was introduced mid-batch and caught before commit.** Removing the clarification `evidence_plan` starved `_graph_node_planning_decision_from_canonical`, so `path_type` was never `unsafe_blocked` and blocked containment requests reported `human_review.reason="policy_checks_passed"` instead of `"unsafe_action_blocked"`. 27 unsafe/containment tests failed; fixed by branching on outcome status before requiring an EvidencePlan. **Lesson for the remaining items: removing a state key that downstream nodes silently depend on is the dominant risk of this cutover — set-diff the full suite against a stashed baseline on every batch, never a pass/fail count.**
  - **`answer_mode = outcome` bug** in `build_canonical_failure_state` wrote non-literal values into a closed `AnswerMode` enum, corrupting otherwise-valid plans. Found by a new test, not by the failing suite.
  - **MCP re-gate (G resolution).** `mcp_allowed` for the `spl_artifact` branch is now `live_data_request and is_known_catalogue_match(match_path)`. The first attempt re-gated **every** tier, which broke in-catalogue T1 turns — the spec's "T2/out-of-catalogue" uses the *LLM-utilization* sense of T2 (out-of-catalogue), not the tier-table T2 (`use_case_catalog`, a known lane). **Two different meanings of "T2" exist in this repo; the tier table in this plan is the authority for lanes, the LLM-utilization sense for producer tiers.** Final shape: `needs_mcp` stays descriptive, `mcp_available` discloses capability, `mcp_allowed` is the sole authorisation. `test_t2_never_execution_eligible_or_mcp_allowed` passes **untouched**.
  - **Three tests re-pinned to the new policy** (disclosed, not quietly edited): `test_evidence_planner_all_tier_grants::test_control_plane_on_grants_search_eligibility` (renamed to `test_out_of_catalogue_live_data_ask_is_not_granted_mcp`, plus a new catalogue-matched counterpart), `test_run_contract_bundle::test_bundle_a_substation_live_data` (one assertion; every execution-safety assertion in it untouched and still passing), and `test_pipeline_dispatch_phase2a::test_pipeline_dispatch_not_attached_when_v2_flag_off` (asserted the presence of the partial `EvidencePlan` this batch removes).
  - **Reverted mid-batch:** a change making `splunk_mcp_readiness` block on `mcp_allowed` instead of `not needs_mcp and not mcp_allowed`. Correct direction (authorisation should gate, not need) but outside this batch, and it flipped a pinned `planned_tool_call` to `blocked_tool_call`. No execution hole: the pipeline already refuses at `mcp_allowed` before `evaluate_mcp_execution`. **Candidate for a later least-privilege batch.**
  - Not started, per instruction: persistence, migration, idempotency, telemetry catalog, documentation.
- **2026-07-25 rev 9c (sentinel drift resolved — Gate 1 closed):** Sentinel **PASS 17/17**, clean-answer eval **120/120 PASS**. Six defects fixed and only three baseline values re-frozen; the drift was overwhelmingly canonical behaving wrongly, not the baseline being stale.
  - **The sentinel's own pass/fail counter was broken.** `scripts/eval_sentinel.py` computed `failed_keys` as `diff.split(".")[0]`, but row keys are themselves dotted (`q0.q045`, `pg.dns.001`), so every row collapsed into its prefix (`q0`, `pg`) and the summary printed a near-constant "15/17" regardless of how many rows differed. The true starting state was **2/17**. Fixed to attribute diffs to real row keys. *A governance gate that cannot count its own failures hid the size of this regression for the whole cutover.*
  - **`query_to_intent` was a stub on the known lane.** The orchestrator emitted `{"query_signals": ...}`, dropping `candidate_mappings` and `intent_classification` — so every sentinel row reported `match_path`, `mapped_question_ref`, `intent_family`, `requires_clarification` as `None`. Now builds the full deterministic `build_query_to_intent` (no model hop; the LLM advisory is an injected argument).
  - **Intent family came from the routed skill.** `build_known_path_intent_stub` maps skill → family through a lookup table; SPL-authoring questions routed to `alert_summary`/`attack_discovery` were relabelled `hybrid_alert_review` and lost `spl_generation_only` — and with it their governed SPL. The deterministic classifier now supplies the family, with `llm_intent_status="skipped"` recording that no model hop occurred and `primary_intent` pinned to the routed skill so **routing keeps authority over which skill runs**.
  - **The completeness gate treated SPL outputs as analyst inputs.** `evidence_requirements` (`fail_count`, `first_failure`, `command_line`, …) are what the *answer presents*; the gate demanded them as inputs and diverted governed catalogue questions into guided resolution, replacing an approved template SPL with an ungoverned lab draft (`draft_preview_not_governed`) and moving the route off its catalogue skill. They are now advisory when the analyst supplied **no concrete scope**, detected via entities rather than `relevant_present` (which also counts intent-inferred keys). Generic quantifiers (`host=['multiple']`) are explicitly not a scope, so `test_known_incomplete_wrong_entity_divert` still diverts on `host:WRONG-99`.
  - **Canonical answer-mode override had a catch-all.** `_answer_mode_from_canonical` returned `"live_investigation"` for every family it had no rule for, overriding `plan_evidence` and rewriting knowledge families (`mitre_explanation`, `sop_or_playbook`) from `rag_only` — attaching a lab SPL draft and a MITRE assertion to policy/procedure answers. It now returns `None` to defer to the planner.
  - **`use_case_catalog` was in no match-path set in route adjudication**, so catalogue questions fell through to a skill re-derived from `intent_family`. Harmless while the intent stub echoed the routed skill; once the real classifier supplied the family, catalogue questions silently re-routed (`attack_discovery` → `spl_generation`), which 5 tests caught — one literally named `..._without_changing_selected_skill`. Catalogue matches now use the registry-skill-preserving branch with their own `catalogue_registry_skill` provenance (reusing the near-105 label would have mislabelled the audit surface).
  - **Clarification lost its analyst-facing label.** With no `EvidencePlan`, `answer_contract.answer_mode` went `None` and the card rendered as an ordinary low-evidence answer. `build_answer_contract` now takes `canonical_status` and injects `answer_mode="clarification"` into its local `plan` — at the source, because the function builds the contract on several branches that each read `plan` directly.
  - **Re-frozen: 3 values, all `answer_mode: "clarification"` → `null`** on `pg.clar.001`, `pg.unsafe.001`, `q0.q045`. Correct by the Gate 1 contract (clarification carries no `EvidencePlan`) and **not** a weakened assertion: `contract_answer_mode="clarification"` and `requires_clarification=True` still pin those turns, and `contract_answer_mode` is the analyst-facing surface. The baseline diff is exactly 3 lines — everything else was restored by fixing code.
  - **Full pytest: `112 failed / 4177 passed` vs the batch baseline `203 / 4051` — 91 baseline failures fixed, 0 new** (set-diffed). One test re-pinned, disclosed: `test_route_adjudication::test_hybrid_failed_login_action_preserves_live_investigation_skill` accepts the new `catalogue_registry_skill` provenance; its asserted route is unchanged.
  - **Known-good but still open:** `langgraph_dual_parity` reports `total=120 match=0 acceptable=107 mismatch=13`. Measured at the pre-rev-9c commit it was `match=0 acceptable=85 mismatch=35`, so this work **improved** it (35 → 13 mismatches) but did not create it — the imperative path and the planner-led shadow graph have diverged since the Phase 1 rewire, and 0 exact matches predates this session. Belongs with items 15/17.

## Key files

| Area | Files |
|------|-------|
| Contracts | `backend/app/chat/contracts/canonical_planning_input.py`, `canonical_planning_outcome.py` (item 12) |
| Orchestration | `canonical_planning_orchestrator.py`, `plan_evidence_from_canonical.py`, `pipeline.py` |
| Authority | `backend/app/planner/resource_plan_authority.py`, `composer.py` |
| Handoff DB | `canonical_handoff_repository.py`, `canonical_handoff_store.py`, `canonical_handoff_models.py`, `db/migrations/0004_canonical_handoffs.sql`, `db/migrations/0005_canonical_planning_cutover_constraints.sql` (item 18) |
| Data layer (rev 9) | `backend/app/chat/canonical_db.py` (item 19a), `backend/scripts/migrate_ai_soc_db.py` (item 18a), `app/db/session.py`, `app/connectors/telemetry/db.py` |
| Execution | `guided_hybrid_executor.py`, `planner/executor.py`, `canonical_execution_idempotency.py` (item 20) |
| Telemetry | `planning_telemetry.py`, `durable_planning_telemetry.py`, `response_validation.py`, `app/connectors/telemetry/redaction.py` (item 21a) |
| EC purity (rev 9) | `app/api/routes_scenarios.py`, `app/demo/captures/*.json`, `app/demo/scenarios.py` (item 26a) |
| Docs to update | `CLAUDE.md` (control-plane gating sentence, COE telemetry invariant), `docs/architecture/canonical_telemetry_coverage.md`, `plans/2026-06-02_chat-control-plane-master.md` (runtime refs) |
| Tests | `test_canonical_planning_architecture.py`, `test_canonical_handoff_invariants.py`, `tests/support/canonical_flow.py`, `tests/integration/*`, `test_migration_readiness.py`, `test_canonical_db_unit_of_work.py`, `test_canonical_telemetry_correlation.py`, `test_telemetry_persistence_policy.py`, `test_experience_center_canonical_purity.py`, `test_canonical_retention_purge.py`, `scripts/smoke_canonical_paths.sh` |
