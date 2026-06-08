# Planner-Led SOC Assistant — Plan Completion Review

**Reviewed plan:** `/root/.cursor/plans/planner-led_soc_assistant_91c3d272.plan.md`
**Date:** 2026-06-08
**Reviewer:** Claude (Opus 4.8)
**Repo state:** branch `master`, working tree clean except `.claude/settings.local.json`. Read as **complete through Phase 9** (Phases 0–9 committed). Phases 10–11 and the cross-phase Knowledge-surfaces-sync are **not** complete.

---

## 1. Verdict on the three claims

| Claim | Verdict | Basis |
|-------|---------|-------|
| "All the points are followed" | **No — through Phase 9 only.** | Phases 0–9 landed with tests. Phase 10 (SOC validation sheets, `docs/validation/`) and Phase 11 (consolidated regression additions, cutover flag matrix, demo doc) and the cross-phase Knowledge-surfaces-sync (Section M) are not done. One deviation in delivered work (graph topology — see §3). |
| "All bugs are now removed" | **Unprovable as stated; what is true is strong.** | Full backend suite **1258 passed, 1 skipped, 6 xfailed**. Canonical governance regression `run_stage3_governance_regression.sh` = **PASS** (harness green, 105-question shadow eval all buckets pass). Crosswalk Freeze-gate-2 invariants hold against the actual data (0 violations). "Green tests" ≠ "no bugs" — it means the asserted invariants hold. |
| "We will be using the architecture as defined" | **Not by default — by design.** | Every new capability is gated **off** (`control_plane_enabled`, `langgraph_orchestration_enabled`, `ai_soc_planner_mitre_branch_enabled`, `ai_soc_spl_template_governance_enabled`, `ai_soc_llm_final_synthesis_enabled`, `ai_soc_llm_live_synthesis_enabled`, `ai_soc_llm_intent_advisor_enabled` all default `False`). This matches the plan's L.10 rollout posture. The architecture is **implemented-and-shadowed, not adopted.** Going live requires Phase 10 → Phase 11 cutover → flag flips → SOC-approved `runtime_active` promotions. |

**Bottom line:** Solid, governed, test-backed delivery of Phases 0–9. But you **cannot** yet say "all points followed" (10–11 + Section M remain) and you **cannot** say "we are using this architecture" (it's behind default-off flags and the planner-led *graph* itself was not built — see §3).

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
| 9 — Governed LLM composer | ✅ Done | `governed_answer_composer.py`, `test_governed_llm_answer_composer_phase9.py` |
| 10 — SOC validation sheets | ❌ Not done | `scripts/build_soc_validation_sheets.py` absent; `docs/validation/` absent |
| 11 — Consolidated regression + demo + cutover matrix | ❌ Not done | no cutover flag-matrix doc; Section M sync incomplete |
| Cross-phase — Knowledge surfaces sync (Section M) | ⚠️ Partial | backend crosswalk/discovery/proposed exports exist; frontend `KnowledgePage.tsx` cards, `KnowledgeExportArtifact` union, docs not verified complete |

---

## 3. The one deviation in delivered work — planner-led *graph* was not built

This is the most important technical finding and it downgrades L.12 row 1 from Match to **Partial/Gap**.

The plan's thesis (Sections D, L.1, L.2, **L.6**) is a **planner-led LangGraph with conditional fan-out/fan-in**: `PlanningNode → ConditionalFanOut → {rag, spl, evidence, mitre, severity, hil, unsafe_blocked} → FanIn aggregator → contract`.

**What was actually built:** `backend/app/graph/chat_workflow.py` is still the **original linear 9-node parity wrapper**:
`init_routing → query_to_intent → evidence_planning → shadow_enrichment → conditional(rag_only | workflow_spl) → execution → context_finalize → END`.

- The conditional edges branch on `evidence_plan.answer_mode == "rag_only"`, **not** on `PlanningDecision.path_type` / `branches[]`.
- There is **no** MITRE branch node, no severity branch node, no HIL branch node, no `unsafe_blocked` node, and **no fan-in aggregator node** in the graph.
- The planner (`plan_path_and_tools`) and all phase 5B/6/7/8/9 logic live in the **imperative `pipeline.py`**, gated by `control_plane_enabled` and the per-feature flags.
- `langgraph_orchestration_enabled = False`, so the LangGraph is not even the live execution path.

**Is this a bug?** No — it's consistent with the plan's own guardrails (Section D: "keep imperative `build_live_chat_response` behind flag until parity tests pass"; N.1: "Replacing `chat_workflow.py` directly risks drift… keep imperative path and graph path parity-tested until Phase 11 cutover"). The plan **defers** the graph rebuild to Phase 11 cutover. So the work matches the *sequencing*, but the **target architecture (the planner-led graph) does not yet exist** — it lives as imperative logic. When you say "we will use the architecture as defined," the literal LangGraph fan-out/fan-in in Section L.6 is still future work.

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
| 1 | Planner-led graph | **Gap/Partial** | Planner fn exists; LangGraph still linear parity wrapper, not L.6 fan-out/fan-in. Deferred to Phase 11. |
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
| 16 / 16b | Knowledge exports + UI | **Partial** | Backend exports exist; frontend cards/types/docs (Section M.3–M.4) unverified/incomplete. |
| 17 | MCP deferred | **Match** | Execution flags false. |
| 18 | Governance regression | **Match** | Script PASS. |
| 19 | Demo isolation | **Match** | EC fixture path isolated. |
| 20 | Response compat | **Match** | Additive fields only; suite green. |
| 21–25 | Knowledge API/UI/docs sync | **Partial/Gap** | Section M not fully delivered (Phase 10/11 work). |

---

## 6. Gaps and deviations to close before claiming "done" / "adopted"

1. **Phase 10 — SOC validation package** (not started): `scripts/build_soc_validation_sheets.py`, `docs/validation/*` sheets derived from the crosswalk. Required for any SOC sign-off and for promoting `runtime_active`.
2. **Phase 11 — consolidated regression + cutover** (not started): expand governance regression with planner/factory/MITRE-branch/Case A–H spot checks; **cutover flag matrix doc**; demo scenario doc; frontend optional `planning_decision`/trace fields.
3. **Section M — Knowledge surfaces sync** (partial): finish `KnowledgePage.tsx` export cards (crosswalk, discovery, proposed, triage), extend `KnowledgeExportArtifact` union, update `docs/evals/README.md` + `docs/skills/README.md`, run `npm run build`.
4. **Deviation — missing `PLANNER_AUTHORITY_ENABLED` flag.** L.10 specifies it as a new flag distinct from `control_plane_enabled`. It does not exist; planner authority is folded under `control_plane_enabled`. Either add the flag or update the L.10 cutover matrix to reflect the consolidated flag — otherwise the documented cutover sequence is wrong.
5. **Deviation — planner-led graph deferred** (§3). Either build the L.6 graph in Phase 11 or explicitly amend the plan to state the imperative pipeline is the permanent home and the LangGraph remains a parity shadow.
6. **Plan file is internally stale.** Frontmatter `todos` list phases 6–11 as `pending`, while the body marks Phases 6–8 "✅ Complete" and git shows 6–9 committed. Fix the tracking so the plan is trustworthy.

---

## 7. To actually "use the architecture as defined" — required sequence

1. Complete **Phase 10**: build SOC validation sheets from crosswalk; SOC reviews and sets `validation_status=soc_approved` on intended `runtime_active` rows.
2. Complete **Phase 11**: consolidated regression, cutover flag matrix, demo doc, Section M Knowledge sync, frontend build.
3. Resolve the **flag-matrix deviation** (`PLANNER_AUTHORITY_ENABLED`) and decide the **graph deviation** (build L.6 graph vs amend plan).
4. **Flip flags** per a documented cutover, with parity tests green at each step: `control_plane_enabled` → `ai_soc_planner_mitre_branch_enabled` → `ai_soc_spl_template_governance_enabled` → enrichment-aware plan → (optional) intent advisor / synthesis. `MCP_GLOBAL_EXECUTION_ENABLED` stays **false**.
5. Re-run `run_stage3_governance_regression.sh` + full suite after each flip.

Until steps 1–4 are done, the honest statement is: **"Phases 0–9 are implemented, tested, and governance-green, behind default-off flags. The system still runs the legacy backward-compatible path by default. Phases 10–11 and the cutover remain."**
