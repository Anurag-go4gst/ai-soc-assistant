# Planner-Led SOC Assistant — Plan Completion Review

**Reviewed plan:** `/root/.cursor/plans/planner-led_soc_assistant_91c3d272.plan.md`
**Date:** 2026-06-08
**Reviewer:** Claude (Opus 4.8)
**Repo state:** branch `master`. **Phases 0–13 implementation complete** (see commit hashes below). **Phase 12** built the planner-led LangGraph fan-out/fan-in **shadow graph** (`planner_led_shadow_graph.py`); **Phase 13** dual-run parity eval reports **120/120 exact governance matches** (`39181c8`). Live `/chat` is **still** the imperative pipeline — `LANGGRAPH_ORCHESTRATION_ENABLED=false` by default; shadow graph is tests/CI only.

---

## 1. Verdict on the three claims

| Claim | Verdict | Basis |
|-------|---------|-------|
| "All the points are followed" | **Yes — through Phase 13 for graph topology (shadow + parity).** | Phases 0–11 landed with tests and docs. Phase 12 (`608a75a`) planner-led shadow fan-out/fan-in graph; Phase 13 (`39181c8`) dual-run parity harness + CI `--check`. L.6 topology exists as **shadow**; live runtime cutover still deferred — see §3. |
| "All bugs are now removed" | **Unprovable as stated; what is true is strong.** | Full backend suite **1258 passed, 1 skipped, 6 xfailed**. Canonical governance regression `run_stage3_governance_regression.sh` = **PASS** (harness green, 105-question shadow eval all buckets pass). Crosswalk Freeze-gate-2 invariants hold against the actual data (0 violations). "Green tests" ≠ "no bugs" — it means the asserted invariants hold. |
| "We will be using the architecture as defined" | **Not by default — by design.** | Every new capability is gated **off** (`control_plane_enabled`, `langgraph_orchestration_enabled`, `ai_soc_planner_mitre_branch_enabled`, `ai_soc_spl_template_governance_enabled`, `ai_soc_llm_final_synthesis_enabled`, `ai_soc_llm_live_synthesis_enabled`, `ai_soc_llm_intent_advisor_enabled` all default `False`). This matches the plan's L.10 rollout posture. The architecture is **implemented-and-shadowed, not adopted.** Going live requires Phase 10 → Phase 11 cutover → flag flips → SOC-approved `runtime_active` promotions. |

**Bottom line:** Phases 0–13 are implemented, tested, and documented. The planner-led LangGraph fan-out/fan-in **exists as a parity-validated shadow graph** (120/120 governance match). You **still cannot** say "we are using LangGraph in production" without explicit cutover — defaults remain legacy/parity imperative `/chat` (see §3).

---

## 2. Phase completion status (evidence-based)

| Phase | Status | Evidence |
|-------|--------|----------|
| 0 — Crosswalk spine | ✅ Done | `docs/evals/soc_capability_crosswalk.json` (105/49/7 rows), `scripts/build_soc_capability_crosswalk.py`, `test_soc_capability_crosswalk_baseline.py`, export wired in `mapping_exports.py` |
| 0B — Skill Expansion Factory | ✅ Done | `github_skill_discovery_index.json` (754 skills), `github_skill_triage_scores.json`, `proposed_use_cases_from_github.json`, `test_github_skill_expansion_factory_baseline.py` |
| 1 — Trace-only planner | ✅ Done | `planning_decision.py`, `test_planner_trace_phase1.py` |
| 2 — LLM intent advisor | ✅ Done | `llm_intent_advisor.py`, `contracts/llm_intent_advisory.py`, `test_llm_intent_advisor_phase2.py` |
| 3 — Path/tool selection | ✅ Done (planner fn) / ⚠️ graph not rebuilt (see §3) | `plan_path_and_tools()` wired in `pipeline.py`, `test_planner_path_selection_phase3.py` |
| 4 — Curated enrichment + activation gate | ✅ Done | `content_enrichment.py`, `test_curated_enrichment_activation_phase4.py` |
| 5 — Enrichment-aware evidence plan | ✅ Done | `test_enrichment_aware_evidence_plan_phase5.py` |
| 5B — MITRE evidence branch + `_status_for` reconcile | ✅ Done | `contracts/mitre_branch.py`, `mitre_branch.py`, `test_mitre_evidence_branch_phase5b.py`, `test_mitre_spl_governance_gate_closure.py` |
| 6 — SPL template governance | ✅ Done | `test_spl_template_governance_phase6.py` |
| 7 — RAG-only / generic SOC guidance | ✅ Done | `test_rag_generic_soc_guidance_phase7.py` |
| 8 — Answer contract V2 | ✅ Done | additive fields on `answer_contract.py`, `test_answer_contract_enrichment_phase8.py` |
| 9 — Governed LLM composer | ✅ `d6bbefc` | `governed_answer_composer.py`, `test_governed_llm_answer_composer_phase9.py` |
| 10 — SOC validation sheets | ✅ `124966a` | `scripts/build_soc_validation_sheets.py`, `docs/validation/*`, `test_soc_validation_package_phase10.py` |
| 11 — Consolidated regression + demo + cutover | ✅ `8c4198c` | governance regression + validation `--check`; `docs/demo/flag_cutover_matrix.md`; `docs/demo/demo_scenarios_readiness.md`; Knowledge UI sync for all 10 validation exports; `test_soc_demo_readiness_phase11.py` |
| 12 — Planner-led LangGraph shadow graph | ✅ `608a75a` | `planner_led_shadow_graph.py`; fan-out/fan-in from `PlanningDecision.branches[]`; `AI_SOC_LANGGRAPH_SHADOW_ENABLED`; `test_langgraph_shadow_phase12.py` |
| 13 — Dual-run parity evaluation | ✅ `39181c8` | `langgraph_dual_parity.py`; `run_langgraph_dual_parity_eval.py --check`; 120 rows (105+8+7); reports under `docs/evals/`; governance regression wired |
| Cross-phase — Knowledge surfaces sync (Section M) | ✅ Phase 10/11 scope | All `soc_validation_*` exports + `KnowledgePage.tsx` cards; legacy mapping exports unchanged |

---

## 3. LangGraph posture — shadow built (Phase 12), parity proven (Phase 13), live cutover deferred

The plan's thesis (Sections D, L.1, L.2, **L.6**) is a **planner-led LangGraph with conditional fan-out/fan-in**: `PlanningNode → ConditionalFanOut → {rag, spl, evidence, mitre, severity, hil, unsafe_blocked} → FanIn aggregator → contract`.

**Phase 12 (`608a75a`)** implemented this topology in `backend/app/graph/planner_led_shadow_graph.py`:

- Branch selection from `PlanningDecision.path_type` / `branches[]` (not `evidence_plan.answer_mode`).
- Eight branch nodes + `fan_in_aggregate` before shared RAG/investigation/finalize pipeline.
- Invoked only when `AI_SOC_LANGGRAPH_SHADOW_ENABLED=true` (tests / Phase 13 harness); **not** wired to `/chat`.

**Phase 13 (`39181c8`)** dual-runs imperative `build_live_chat_response()` vs `run_planner_led_shadow_graph()` on **120** questions (105-map + 8 demo + 7 manual). Baseline: **120 exact governance matches**, 0 critical mismatches; `--check` in governance regression.

**What remains legacy:** `backend/app/graph/chat_workflow.py` is still the **original linear 9-node wrapper** selected by `LANGGRAPH_ORCHESTRATION_ENABLED` (default `false`). It branches on `evidence_plan.answer_mode`, not planner branches. Live `/chat` uses imperative `pipeline.py` unless operators explicitly enable the legacy linear graph flag.

**Cutover gate:** Phase 13 proves shadow parity; **production LangGraph adoption** still requires SOC sign-off, flag cutover per `docs/demo/flag_cutover_matrix.md`, and an explicit decision to replace imperative `/chat` with the shadow runner (not done in Phase 12–13).

---

## 4. Mandatory-gate validation against the actual data (not test names)

Direct inspection of `soc_capability_crosswalk.json`:

- Rows: `question_rows`=105, `use_case_rows`=49, `github_skill_rows`=7 ✅ (Section B2 criteria 1–2)
- `use_case_rows` runtime status: 4 `runtime_active`, 42 `planned`, 3 `metadata_only`.
- **Freeze-gate-2 violations among `runtime_active`: 0** ✅ (each has `catalog_present=true`, `validation_status` ∈ {soc_approved, tests_added}, `live_execution_skill` ∈ 4-enum, `spl_template_status` ∈ {active, sop_only}).
- GitHub rows with `runtime_active`: **none** ✅ (criterion 7 / B3.10). All 7 GitHub rows = `metadata_only`.
- Enrichment-only rows (`catalog_present=false`): all `metadata_only`, none `runtime_active` ✅ (criterion 8).
- Discovery index: 754 skills (> 7) ✅; 754 triage scores; 3 proposed use cases (marked non-runtime).
- 104 `warnings[]` recorded — auditable gaps, as designed (not failures).

**MITRE separation:** `mitre_metadata_role` present at top level; MITRE branch (`mitre_branch.py`) is sole runtime authority and is flag-gated (`ai_soc_planner_mitre_branch_enabled`); legacy `_status_for()` retained as compatibility shim. Matches Section B4 / L.4. ✅

---

## 5. L.12 comparison checklist

| # | Element | Status | Note |
|---|---------|--------|------|
| 1 | Planner-led graph | **Match (shadow)** | L.6 fan-out/fan-in in `planner_led_shadow_graph.py`; Phase 13 dual-run 120/120; live runtime still imperative; legacy `chat_workflow.py` unchanged. |
| 2 | Crosswalk spine | **Match** | 105+49+7 connected; generator + export + baseline test. |
| 3 | `use_case_id` activation gate | **Match** | Phase 4; enrichment-only inactive. |
| 4 | LLM intent advisor early | **Match (off)** | Phase 2; advisory only, flag-gated. |
| 5 | EvidencePlanV2 | **Match (off)** | Phase 5; flag-gated. |
| 6 | MITRE branch | **Match (off)** | Phase 5B; no metadata-only `evidence_supported`. |
| 7 | `_status_for` shim | **Match** | Compatibility-only; parity tests. |
| 8 | AnswerContractV2 | **Match** | Additive V2 fields present. |
| 9 | LLM composer | **Match (off)** | Phase 9; contract-bounded; flag-gated. |
| 10 | Answer guard overclaim block | **Match** | Gate-closure tests pass. |
| 11 | SPL allowlist | **Match (off)** | Phase 6; flag-gated. |
| 12 | RAG-only path | **Match** | Phase 7. |
| 13 | Generic guidance | **Match** | Phase 7; no fake use case. |
| 14 | Skill Expansion Factory | **Match** | Discovery/triage/intake; Batch 1 validated. |
| 15 | Factory invariants (no graph change) | **Match** | Enrichment/crosswalk grow only. |
| 16 / 16b | Knowledge exports + UI | **Match** | All 10 `soc_validation_*` exports + Knowledge page cards (Phase 11). |
| 17 | MCP deferred | **Match** | Execution flags false. |
| 18 | Governance regression | **Match** | Script PASS. |
| 19 | Demo isolation | **Match** | EC fixture path isolated. |
| 20 | Response compat | **Match** | Additive fields only; suite green. |
| 21–25 | Knowledge API/UI/docs sync | **Match** | Phase 10/11 validation + demo docs delivered. |

---

## 6. Remaining gaps before production "adopted"

1. **SOC sign-off** — review `docs/validation/*`; set `validation_status=soc_approved` on intended `runtime_active` rows in the crosswalk (human process, not automated).
2. **Flag cutover** — follow `docs/demo/flag_cutover_matrix.md` incrementally per environment; keep `MCP_GLOBAL_EXECUTION_ENABLED=false` until COE real MCP contract.
3. **Deviation — missing `PLANNER_AUTHORITY_ENABLED` flag.** Planner authority is folded under `control_plane_enabled`. Cutover matrix documents consolidated flags.
4. **Live LangGraph cutover** (§3). Shadow graph + parity eval complete; `/chat` still imperative. `LANGGRAPH_ORCHESTRATION_ENABLED` and `AI_SOC_LANGGRAPH_SHADOW_ENABLED` stay **false** in production defaults until explicit cutover approval.
5. **Optional follow-up** — frontend `planning_decision`/trace fields in chat UI; Case A–H live spot-check automation beyond golden suite.

---

## 7. To actually "use the architecture as defined" — required sequence

1. SOC reviews validation sheets (`124966a` artifacts) and promotes crosswalk rows.
2. Use **Profile 2** in `docs/demo/flag_cutover_matrix.md` for manual demos; run checklists in `docs/demo/demo_scenarios_readiness.md`.
3. **Flip flags** per environment with `./scripts/run_stage3_governance_regression.sh` green after each step. `MCP_GLOBAL_EXECUTION_ENABLED` stays **false**.
4. Run `python3 scripts/run_langgraph_dual_parity_eval.py --check` green after any planner/graph change before considering LangGraph runtime cutover.

Current honest statement: **"Phases 0–13 are implemented and governance-green. Default runtime is legacy/parity imperative `/chat`. Planner-led LangGraph fan-out/fan-in exists as a shadow graph with 120/120 dual-run parity. Production LangGraph adoption requires SOC sign-off, zero critical parity mismatches, and explicit cutover — not yet done."**

---

## 8. Post-Phase 13 follow-up — SPL draft preview & narrative hardening (2026-06-08)

**Scope:** Lab-only draft SPL preview path when governed template SPL is blocked/unavailable (Phase 6 gate). Not a change to governed SPL approval, MCP execution, or LangGraph cutover.

**Commits (review later):**

| Commit | Summary |
|--------|---------|
| `6253dc2` | Universal SPL engineering standards (SOC-STD-SPL-001 U01–U03): shift-left `where`, native `_time`, stats inclusion in draft quality lint |
| `8577cfd` | ESP IT→OT zone matching: exact `IN()` placeholders instead of fuzzy `like("%it%")` / `like("%ot%")` wildcards |
| `38f6ad8` | ESP draft preview: `session_state_norm` filter, stats preservation, draft status messaging in pipeline/readability |
| `1bd114d` | ESP draft SPL performance: remove noisy zone wildcards, strict established-session filter, improved draft narrative constants |
| `4f095a8` | **Narrative fix:** Phase 9 governed LLM composer no longer overwrites `direct_answer_summary` when `draft_spl_code` is present; pipeline forces `analyst_summary` to draft-preview HIL-required message; frontend summary cards prefer draft messaging over stale lab narration |

**Problem observed:** With live synthesis enabled (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`), the top analyst paragraph could falsely state that SPL/HIL review was *not* required while the SPL metadata block correctly showed governed-SPL-not-ready + HIL required.

**Root cause:** `compose_governed_answer()` ran after `apply_final_answer_readability()` and replaced `direct_answer_summary` with LLM prose derived from the AnswerContract (`hil_status=not_required` on non-executable paths), contradicting the draft-preview overlay.

**Fixes (governance preserved):**

- `governed_answer_composer.py`: skip LLM narration when `draft_spl_code` is set; re-apply `apply_draft_preview_readability()`.
- `pipeline.py`: post-composer draft overlay; `analyst_summary` uses `DRAFT_PREVIEW_STATUS_MESSAGE` when `spl_draft_preview` is present.
- `final_answer_readability.py` / `draft_preview.py`: expanded forbidden phrase list; scrub contradictory `foundation_sec_analysis`.
- `AnalystResponseCard.tsx` / `AnalystSummaryCard.tsx`: prefer `direct_answer_summary` / draft message for summary header and HIL stat.
- Tests: `test_esp_draft_preview_review_wording_with_live_composer` asserts composer cannot leak forbidden HIL/SPL wording.

**Live flags (dev / COE lab):** `AI_SOC_LLM_SPL_FALLBACK_ENABLED=true` in `.env` (lab advisory SPL only; draft preview path does not call fallback). Draft preview remains `draft_preview_not_governed`, non-executable, HIL-required.

**Files to review:** `backend/app/spl/draft_preview.py`, `backend/app/spl/draft_quality.py`, `backend/app/chat/final_answer_readability.py`, `backend/app/synthesis/governed_answer_composer.py`, `backend/app/chat/pipeline.py`, `backend/app/tests/test_spl_draft_preview.py`, `frontend/src/components/AnalystResponseCard.tsx`, `frontend/src/components/AnalystSummaryCard.tsx`.

**Open for SOC review:** Whether Phase 9 composer prompt should always receive draft-preview + HIL-required facts from AnswerContract when template generation is blocked (vs. skipping composer entirely as implemented). Whether `AI_SOC_LLM_SPL_FALLBACK_ENABLED` should remain lab-only in production cutover matrix.
