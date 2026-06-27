---
name: Handoff T2 Completion
overview: "Single source of truth for closing the three June 26 handoff/T2 plans. Repo-verified inventory of shipped, branch-only, partial, and pending work. No feature implementation until Batch 0 completes."
status: active
date: 2026-06-27
baseline_commit: e5a4d40
supersedes:
  - plans/2026-06-26_canonical-handoff-discipline-completion.md
  - plans/2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md
  - plans/2026-06-26_t2-llm-intent-binding-final-plan.md
todos:
  - id: batch-0-merge-pr40
    content: "Batch 0: Merge PR #40 (fix/post-pr38-smoke-routing) to master first"
    status: completed
  - id: batch-0-merge-pr39
    content: "Batch 0: Merge PR #39 (feat/operator-reviewed-promotion-writes) after #40 rebase"
    status: completed
  - id: batch-a-t2
    content: "Batch A: T2 renderer + LLM matrix + /chat smoke (phases 9-12)"
    status: completed
  - id: batch-b-handoff
    content: "Batch B: Handoff E2E, real-bug negatives, route tests, WS1/WS2/WS4/WS8 (ph 2/5/6)"
    status: completed
  - id: batch-c-dispatch
    content: "Batch C: Step-walk dispatch parity-first (WS3, ph 4, legacy elif gating)"
    status: completed
  - id: batch-d-packs
    content: "Batch D: Answer packs + SPL trace projection + synthesis skip (WS6/7, ph 8-9)"
    status: completed
  - id: batch-e-polish
    content: "Batch E: Winevent scope framing + T1 SPL-native meta cleanliness"
    status: completed
  - id: batch-f-ui
    content: "Batch F: Frontend authority_tier rendering (WS5 UI)"
    status: completed
  - id: doc-operator-checklist
    content: "Doc batch: Operator-only checklist (COE promotion, prod flags, live MCP, eval refresh)"
    status: pending
  - id: doc-supersede-sources
    content: "Doc batch: Mark three source plans superseded; update plans/README.md + AI_SOC_MASTER_PLAN §M.1"
    status: pending
isProject: false
---

# Consolidated Closure Plan — Single Source of Truth

**Lock status:** ACTIVE — Batches A–F code complete on `master` @ `c6efc18`; doc batch pending.

**Baseline:** `master` @ `e5a4d40` (PR #38 merged).

**Current worktree:** `fix/post-pr38-smoke-routing` @ `64a7fe0` (includes PR #40 commits; not on `master`).

---

## Source-of-truth graph (preserve — no parallel architecture)

```text
query
  -> query_to_intent
  -> route_adjudication
  -> route_contract
  -> evidence_planning (EvidencePlan + ResourcePlan projection)
  -> plan_dispatch / evidence_loop / SPL / execution
  -> context_finalize (FinalEvidenceGate -> RunContract)
  -> governed answer
```

### Non-negotiables

- No parallel weak-case architecture.
- ResourcePlan does **not** reclassify intent or replace route.
- Drift **narrows capabilities**; RouteContract remains canonical.
- Environment KB fills blanks only; it is **not** telemetry evidence.
- Answer packs enrich EvidencePlan only; never bypass graph.
- MCP execution remains **default-off**; no LLM-to-MCP; no candidate SPL execution.
- SPL artifact consolidation is a **control-plane trace/read-model projection only** — RunContract, FinalEvidenceGate, and `spl_validation` remain authority. **No new runtime SPL authority object** (do not introduce competing `SplArtifactAuthority` runtime types).

---

## Inventory: shipped on `master` (`e5a4d40`)

| ID | Item | Proof |
|----|------|-------|
| S1 | Row authority classifier + 105 report | `backend/app/coverage/row_authority.py`, `scripts/build_row_authority_report.py`, `backend/app/tests/test_row_authority_report.py` |
| S2 | Flag-gated exact-105 narrowing in route adjudication | `backend/app/routing/route_adjudication.py`, `route_authority_operation_authoritative_enabled` in `backend/app/config.py` |
| S3 | EvidencePlan enrichment (row authority, slots, source profile) | `backend/app/chat/evidence_planner.py`, `backend/app/chat/contracts/evidence_plan.py` |
| S4 | **WS2 wiring:** SlotConstraintProjection + `slot_constraint_projection_summary` on EvidencePlan | `backend/app/spl/slot_constraint_projection.py`, `evidence_planner.py` (~538), `pipeline.py` drift merge |
| S5 | ResourcePlan composer + `blocked_policy` MCP steps | `backend/app/planner/composer.py`, `backend/app/tests/test_planner_composer_parity.py` |
| S6 | ResourcePlan boolean parity (sentinel parametrized) | `backend/app/tests/test_planner_composer_parity.py` |
| S7 | `execute_plan_dispatch` + `annotate_step_statuses` (predicate-driven) | `backend/app/planner/executor.py`, `backend/app/tests/test_planner_executor.py` |
| S8 | MCP posture normalization + RunContract projection | `mcp_allowed_normalized` in `pipeline.py`, `project_mcp_posture` in `run_contract_builder.py`, `test_mcp_allowed_normalization.py` |
| S9 | MCP seam: same ResourcePlan step off/mock | `test_handoff_healthy_contradiction.py::test_mcp_off_and_mock_execution_use_same_resource_plan_step` |
| S10 | Runtime promotion lifecycle (read-only demotion) | `backend/app/coverage/promotion_lifecycle.py`, `test_promotion_lifecycle_phase9.py` |
| S11 | Answer-pack loader + seed (`q0.q046`) | `backend/app/use_cases/answer_packs.json`, `answer_packs.py`, `test_answer_packs_runtime.py`, `test_evidence_planner.py` |
| S12 | **WS5 backend:** `trace_authority_index` + `authority_tier` on control-plane trace | `backend/app/governance/trace_authority.py`, `control_plane_trace.py`, `test_control_plane_trace.py` |
| S13 | WS8 healthy-contradiction tests | `test_handoff_healthy_contradiction.py` (6 tests: CP-off/on narrowing, MCP step preserved, T0 skip gating) |
| S14 | Canonical handoff e2e probes | `backend/app/tests/test_canonical_handoff_e2e_probes.py` (10 tests) |
| S15 | Containment banner from canonical blocked state | `test_containment_banner_renders_from_canonical_blocked_action_state` |
| S16 | T2 binding phases 2–8 (SPL path) | `backend/app/tests/test_spl_query_fidelity.py` (`test_t2_*_probe_e2e_*`, alias/scope/multi-index tests) |
| S17 | Intent advisor scheduling for T2 | `backend/app/llm/intent_advisor_scheduler.py`, `test_intent_advisor_scheduling.py` |
| S18 | Route adjudication partial coverage | `test_route_adjudication_weak_exact_*`, `test_route_adjudication_exact_authority_ready_*`, `test_final_plan_drift_narrows_mcp_*` |
| S19 | WS2 drift unit tests (merge helper) | `backend/app/tests/test_evidence_plan_handoff_drift.py` |
| S20 | Governance regression baseline | `./scripts/run_stage3_governance_regression.sh` (last validated post-PR #38) |

---

## Inventory: branch-only (not on `master`)

| Branch | PR | Commits ahead of `master` | Artifacts |
|--------|-----|---------------------------|-----------|
| `fix/post-pr38-smoke-routing` | #40 | `fb84b9c`, `64a7fe0` | Near-105 route fix, unsafe containment, `scripts/ask_chat.sh`, `test_route_policy_smoke_fix.py` |
| `feat/operator-reviewed-promotion-writes` | #39 | 6 commits (includes #40 overlap + promotion/refresh/checklist) | `scripts/apply_promotion_status_review.py`, `docs/evals/ARTIFACT_REFRESH_POLICY.md`, MCP live-readiness checklist, shift-hour trace (`fixed_off_shift_hour_constraint_applied`) |

**Repo verification (2026-06-27):** `scripts/ask_chat.sh` and `scripts/apply_promotion_status_review.py` are **absent from `master`**.

---

## Inventory: partial (shipped core; closure work remains)

| ID | Item | Shipped part | Pending part | Batch |
|----|------|--------------|--------------|-------|
| P1 | **WS1** Row authority | Classifier + flag-gated adjudication + q046 tests | Broader CP-on/off `/chat` matrix beyond q046 | B |
| P2 | **WS2** SlotConstraintProjection | Wiring into EvidencePlan + SPL pipeline | **Drift E2E** through full `/chat` (not new wiring) | B |
| P3 | **WS4** MCP decision surface | Normalization + posture projection + unit/e2e tests | Explicit **parity checklist** across all consumers | B |
| P4 | **WS5** Debug authority tiers | Backend `trace_authority_index` | **Frontend** does not render `authority_tier` (grep: zero matches in `frontend/src`) | F |
| P5 | **WS6** LLM advisor hardening | `can_skip_llm_for_t0` on intent-advisor + composer | Extend skip to **final synthesis narration** when enabled | D |
| P6 | **WS7** Answer packs | Seed + loader guards | ≥5 weak-known reviewed packs beyond `q0.q046` | D |
| P7 | **WS8** Healthy vs bug tests | Healthy-contradiction suite (6 tests) | **Real-bug negative tests** (see below) | B |
| P8 | Phase 2 canonical binding | E2E probes for KB precedence | Plan-named unit tests (`test_canonical_binding_*`, `test_environment_kb_fills_source_profile_before_llm_slots`) | B |
| P9 | Phase 5 route adjudication | weak-exact, authority-ready, one drift test | Four missing route tests (see Batch B) | B |
| P10 | Phase 6 evidence loop | Unit tests + requirement projection | E2E loop + RunContract parity + `test_final_answer_no_live_language_without_collected_evidence` | B |
| P11 | Phase 4 dispatch | Composer + annotate_step_statuses | Step-walk dispatch; legacy `elif` gating when CP-on | C |
| P12 | Phase 8–9 promotion | Runtime read-only lifecycle + pack tests | Broader packs (D); promotion CLI merge (Batch 0 #39) | D + Batch 0 |
| P13 | T2 phases 9–12 | SPL-shape e2e via `build_draft_preview` (3 probes) | Renderer governance + LLM matrix + **`/chat` smoke** (RunContract/FinalEvidenceGate) | A |
| P14 | Post-PR40 answer quality | SPL correct for winevent off-shift | **Scope framing** may still say IT-to-OT boundary | E |
| P15 | T1 SPL-native meta | Safe lab-draft posture | Governed-template metadata not pristine in review card | E |
| P16 | SPL degrade chain | Multiple paths in `pipeline.py` | Single **trace projection** surface (not new authority) | D |

### WS8 — corrected status: **Partial**

Healthy-contradiction tests exist. **Real-bug negative tests are missing:**

1. Exact row bypasses missing bindings (should fail closed / degrade).
2. Live-result language appears without MCP evidence (should be blocked by FinalEvidenceGate/RunContract).
3. MCP step disappears when `needs_mcp=true` (composer must emit present-but-blocked step).

**Batch B** adds these as explicit failing-then-passing regression tests.

### WS2 — corrected status: **Shipped wiring / pending drift E2E**

`slot_constraint_projection_summary` is set in `evidence_planner.py` during planning. `merge_evidence_plan_spl_drift` exists in `pipeline.py`. Unit tests exist in `test_evidence_plan_handoff_drift.py`. **Remaining:** full `/chat` E2E proving planning snapshot vs final SPL drift is traced — **not** new wiring.

### WS5 — corrected status: **Complete (backend + frontend)**

Backend: `trace_authority_index`, per-section `authority_tier`. Frontend: `TraceAuthorityPanel` renders index + per-section tiers in `Stage3DTracePanel` (diagnostic wording; no execution authority).

---

## Inventory: pending (not started — assigned to batches)

All pending code work is captured in Batches A–F below. **No orphan items** from the three source plans remain outside this list.

---

## Operator-only deferrals (documented — not agent implementation)

| Item | Owner | Notes |
|------|-------|-------|
| Live Splunk MCP activation | COE | Checklist lands in PR #39; execution flags stay off |
| `route_authority_operation_authoritative_enabled=true` in production | COE | After Batch B matrix green |
| COE `apply_promotion_status_review.py --apply` | COE | Dry-run default; `--apply` after golden pass + sign-off |
| Eval baseline refresh | Eng | Only when explicitly requested; do not commit accidental drift |

**Doc batch** publishes operator checklist addendum. These items do **not** block "code complete" label.

---

## WS4 MCP parity checklist (Batch B verification — add tests only if drift found)

For a single live-evidence probe query, assert aligned values across:

1. `EvidencePlan.needs_mcp` / `mcp_allowed` / `mcp_allowed_normalized`
2. ResourcePlan MCP `PlanStep` (`step_id`, `status`, `status_reason`, `policy_checks`)
3. `execution` block + `annotate_step_statuses` outcome
4. `project_mcp_posture` → RunContract `mcp_posture`
5. API response `governance_trace` / `control_plane_trace` MCP sections

Fix only if inspection proves mismatch; do not rebuild MCP framework.

---

## Batch structure (execution order)

### Batch 0 — Merge open PRs (no feature code)

1. Merge **PR #40** (`fix/post-pr38-smoke-routing`) → `master` first.
2. Rebase **PR #39** (`feat/operator-reviewed-promotion-writes`) on `master`.
3. Merge **PR #39** → `master`.

**Delivers:** smoke routing, `ask_chat.sh`, promotion CLI, row-authority `--check`/`--refresh`, shift-hour trace, MCP checklist docs.

### Batch A — T2 closure (phases 9–12)

**Closes:** `plans/2026-06-26_t2-llm-intent-binding-final-plan.md`

1. Renderer governance on all 3 probe queries via `render_review_only_spl_answer()`: no execution, no live-backed wording, no severity, no confirmed MITRE.
2. LLM matrix 3 probes × 4 scenarios: disabled / mock advisory / alias slots / conflicting lower-precedence slot (extend firewall + threshold; winevent partially covered).
3. **`/chat` integration smoke (required):** CP-on harness asserts RunContract + FinalEvidenceGate review-only posture per probe class — draft-preview tests alone are insufficient.
4. Phase 1: document `normalized_slots["aggregation_subject"]` as canonical (accessor only if consumer requires).
5. Phase 12 gate: run targeted pytest list from T2 plan + governance regression; record pass in PR description.

**Eval if routing touched:** `PYTHONPATH=backend:. python3 scripts/eval_out_of_catalog_ot_probe.py --check`

### Batch B — Handoff E2E + real-bug negatives

**Closes:** Phases 2/5/6 gaps; WS1/WS2/WS4/WS8

**Phase 2 tests (add if absent):**

- `test_canonical_binding_preserves_question_ref_for_weak_exact`
- `test_environment_kb_fills_source_profile_before_llm_slots`
- `test_llm_slot_cannot_override_environment_kb_index`
- `test_normalized_slots_include_lookup_zone_and_time_window`

**Phase 5 tests (add — currently missing from repo):**

- `test_route_adjudication_rag_only_blocks_spl_and_mcp`
- `test_route_adjudication_policy_intent_overrides_exact_analytics`
- `test_route_adjudication_ignores_raw_llm_route_when_evidence_plan_blocks`
- `test_final_evidence_plan_route_drift_is_recorded`

**Phase 6 tests:**

- Missing lookup → structured missing evidence, no live language
- Missing source profile → clarification/degrade
- `test_run_contract_loop_decision_matches_evidence_loop_decision`
- `test_final_answer_no_live_language_without_collected_evidence`

**WS8 real-bug negatives (new):**

- `test_real_bug_exact_row_cannot_bypass_missing_bindings`
- `test_real_bug_no_live_language_without_mcp_evidence`
- `test_real_bug_mcp_step_not_omitted_when_needs_mcp`

**WS1:** Expand row-authority CP-on matrix beyond q046.

**WS2:** Full `/chat` drift E2E for `handoff_drift_from_final_spl`.

**WS4:** Run parity checklist; fix only on proven drift.

### Batch C — Step-walk dispatch (parity-first)

**Closes:** WS3, Phase 4

**Migration rules (architecture-safe):**

1. **Parity first:** Step-walk must match current legacy dispatch order for sentinel + tier probes before demoting predicates.
2. **Do not remove or bypass `DispatchHooks` predicates** until step-walk equivalence is proven.
3. During migration: derive `uses_rag_only_path` / `uses_pre_mcp_rag` from `project_booleans(ResourcePlan)` + step purposes.
4. ResourcePlan must **never** override EvidencePlan or RouteContract.
5. **Legacy fallback:** `pipeline.py` lines 379–387 (`elif` when `has_composed_plan` is false). Under `CONTROL_PLANE_ENABLED=true`, composition failure must emit trace `resource_plan_composition_failed` and must **not** silently fall through to legacy branch.
6. Same node callables via `DispatchHooks`; executor does not import MCP connectors.

**Tests:** tier probes in `test_planner_executor.py`; `test_resource_plan_does_not_change_intent_or_route`; parity byte-compare step-walk vs predicate dispatch.

### Batch D — Answer packs + SPL trace projection + synthesis skip

**Closes:** WS6, WS7, Phases 8–9 coverage, P16

1. Export ≥5 weak-known rows via `scripts/build_answer_packs.py` into `answer_packs.json`.
2. **SPL artifact consolidation:** add `build_spl_artifact_handoff_summary(state)` (or extend existing finalize helper) — **control-plane trace projection only** merging `candidate_provider_reason` + path labels. RunContract/`spl_validation` remain authority. **No new runtime SPL authority dataclass.**
3. Gate final synthesis narration with `can_skip_llm_for_t0` when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED`; deterministic fallback on skip.

### Batch E — Answer-quality partials

**Closes:** Post-PR40 secondary partials (full handoff plan)

1. **Winevent off-shift scope framing:** SPL correct; fix analyst headline/scope text that incorrectly says "IT-to-OT boundary" when query is wineventlog/auth scoped (`entity_headline_surfacing.py` / contract builder).
2. **T1 SPL-native meta cleanliness:** When governed template exists, review card shows pristine template metadata (no lab-draft placeholder leakage).

### Batch F — Frontend authority tiers

**Closes:** WS5 UI gap

Render `control_plane_trace.trace_authority_index` / per-section `authority_tier` in technical trace (`Stage3DTracePanel.tsx` or governance trace component). `npm run build` required.

### Doc batch — Operator checklist + supersede sources

1. Publish operator checklist addendum (COE promotion dry-run/`--apply`, prod row-authority flag, live MCP, eval refresh policy).
2. Mark three source plans `status: superseded` with pointer to this file.
3. Update `plans/README.md` and `plans/AI_SOC_MASTER_PLAN.md` §M.1.

---

## Verification gates

### Per-batch backend targeted

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_spl_query_fidelity.py \
  app/tests/test_handoff_healthy_contradiction.py \
  app/tests/test_planner_executor.py \
  app/tests/test_planner_composer_parity.py \
  app/tests/test_canonical_handoff_e2e_probes.py \
  app/tests/test_evidence_loop_requirement_projection.py \
  app/tests/test_route_adjudication.py \
  app/tests/test_route_adjudication_drift.py \
  app/tests/test_evidence_plan_handoff_drift.py \
  app/tests/test_evidence_planner.py \
  app/tests/test_control_plane_trace.py \
  -q
```

### CP-off targeted (required in final success gates)

```bash
CONTROL_PLANE_ENABLED=false PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_handoff_healthy_contradiction.py \
  app/tests/test_canonical_handoff_e2e_probes.py \
  app/tests/test_run_contract_builder.py \
  app/tests/test_final_evidence_gate_cross_stream.py \
  -q
```

### Intent / T2 routing (when Batch A or B touches adjudication)

```bash
PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check
PYTHONPATH=backend:. python3 scripts/eval_out_of_catalog_ot_probe.py --check
```

### Row authority artifact (after Batch 0 #39)

```bash
python3 scripts/build_row_authority_report.py --check
```

### Canonical gate (every batch)

```bash
./scripts/run_stage3_governance_regression.sh
```

### Frontend (Batch F)

```bash
cd frontend && npm run build
```

---

## Success criteria

### Plan lock (this document)

- [x] Shipped / branch-only / partial / pending inventories repo-verified
- [x] WS8 corrected to Partial (real-bug tests pending)
- [x] WS2 corrected to shipped wiring / pending drift E2E
- [x] WS5 corrected to backend done / frontend pending
- [x] WS5 frontend authority-tier rendering shipped (Batch F)
- [x] WS4 parity checklist added
- [x] Phase 5 missing route tests listed under Batch B
- [x] Batch C parity-first migration rules documented
- [x] SPL consolidation = trace projection only (no new runtime authority)
- [x] Legacy dispatch fallback listed under Batch C
- [x] Batch A requires `/chat` smoke
- [x] COE / live MCP / eval refresh = operator-only
- [x] CP-off verification command included
- [x] Recommended execution order: Batch 0 → A → B → C → D → E → F → Doc

### Code complete (after all batches)

- PRs #40 and #39 merged
- Every partial item (P1–P16) closed by its batch
- Governance regression PASS
- CP-off targeted suites PASS
- No parallel architecture introduced

### Documentation complete

- Source plans superseded
- Operator checklist published
- `plans/README.md` points here as single source of truth

### Production rollout (operator — separate milestone)

- COE promotion apply, prod flags, live MCP per operator checklist

---

## Completeness matrix (no orphan pending items)

| Source plan item | Disposition |
|------------------|-------------|
| Discipline WS1–WS8 | P1,P2,P3,P4,P5,P6,P7 + Batch B/F/D |
| Full handoff Phases 1–10 | S1–S20 shipped; P8–P16 in batches |
| Full handoff follow-ups (mcp_allowed, containment, smoke) | Shipped on branches #40/#39; Batch 0 |
| Full handoff secondary partials (winevent framing, T1 meta) | P14,P15 Batch E |
| T2 Phases 1–12 | S16–S17 shipped 2–8; P13 Batch A |
| PR #39 promotion CLI | Branch-only; Batch 0 |
| PR #40 smoke routing | Branch-only; Batch 0 |
| Operator deferrals | Documented only |

**After Batches 0–F + Doc:** zero code/test items remain from the three source plans.

