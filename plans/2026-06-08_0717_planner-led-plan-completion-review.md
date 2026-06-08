# Planner-Led SOC Assistant — Plan Completion Review

**Reviewed plan:** `/root/.cursor/plans/planner-led_soc_assistant_91c3d272.plan.md`
**Date:** 2026-06-08
**Reviewer:** Claude (Opus 4.8)
**Repo state:** branch `master`. **Phases 0–11 implementation complete** (see commit hashes below). LangGraph fan-out/fan-in topology is **not** implemented. Default production runtime remains legacy/parity; adopted test/demo path is the governed imperative `/chat` pipeline with explicit flags.

---

## 1. Verdict on the three claims

| Claim | Verdict | Basis |
|-------|---------|-------|
| "All the points are followed" | **Yes — through Phase 11, except graph topology.** | Phases 0–11 landed with tests and docs. Phase 10 (`124966a`) SOC validation package; Phase 11 demo readiness (Knowledge sync, regression, cutover matrix, demo scenarios). LangGraph fan-out/fan-in (L.6) remains deferred — see §3. |
| "All bugs are now removed" | **Unprovable as stated; what is true is strong.** | Full backend suite **1258 passed, 1 skipped, 6 xfailed**. Canonical governance regression `run_stage3_governance_regression.sh` = **PASS** (harness green, 105-question shadow eval all buckets pass). Crosswalk Freeze-gate-2 invariants hold against the actual data (0 violations). "Green tests" ≠ "no bugs" — it means the asserted invariants hold. |
| "We will be using the architecture as defined" | **Not by default — by design.** | Every new capability is gated **off** (`control_plane_enabled`, `langgraph_orchestration_enabled`, `ai_soc_planner_mitre_branch_enabled`, `ai_soc_spl_template_governance_enabled`, `ai_soc_llm_final_synthesis_enabled`, `ai_soc_llm_live_synthesis_enabled`, `ai_soc_llm_intent_advisor_enabled` all default `False`). This matches the plan's L.10 rollout posture. The architecture is **implemented-and-shadowed, not adopted.** Going live requires Phase 10 → Phase 11 cutover → flag flips → SOC-approved `runtime_active` promotions. |

**Bottom line:** Phases 0–11 are implemented, tested, and documented for SOC review and manual demo. You **still cannot** say "we are using this architecture in production" without flag flips and SOC crosswalk sign-off — defaults remain legacy/parity, and the planner-led *LangGraph* fan-out/fan-in was not built (see §3).

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
| 11 — Consolidated regression + demo + cutover | ✅ (this commit) | governance regression + validation `--check`; `docs/demo/flag_cutover_matrix.md`; `docs/demo/demo_scenarios_readiness.md`; Knowledge UI sync for all 10 validation exports; `test_soc_demo_readiness_phase11.py` |
| Cross-phase — Knowledge surfaces sync (Section M) | ✅ Phase 10/11 scope | All `soc_validation_*` exports + `KnowledgePage.tsx` cards; legacy mapping exports unchanged |

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
| 1 | Planner-led graph | **Gap/Partial** | Planner fn + imperative pipeline complete; LangGraph still linear parity wrapper, not L.6 fan-out/fan-in. **Not rebuilt in Phase 11** (documented). |
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
4. **Deviation — planner-led LangGraph fan-out/fan-in** (§3). Phase 11 explicitly did **not** rebuild L.6 graph. Imperative `pipeline.py` is the adopted test/demo path; LangGraph remains optional parity shadow only.
5. **Optional follow-up** — frontend `planning_decision`/trace fields in chat UI; Case A–H live spot-check automation beyond golden suite.

---

## 7. To actually "use the architecture as defined" — required sequence

1. SOC reviews validation sheets (`124966a` artifacts) and promotes crosswalk rows.
2. Use **Profile 2** in `docs/demo/flag_cutover_matrix.md` for manual demos; run checklists in `docs/demo/demo_scenarios_readiness.md`.
3. **Flip flags** per environment with `./scripts/run_stage3_governance_regression.sh` green after each step. `MCP_GLOBAL_EXECUTION_ENABLED` stays **false**.
4. Build L.6 LangGraph fan-out/fan-in only as a **future** phase if parity with imperative pipeline is required.

Current honest statement: **"Phases 0–11 are implemented and governance-green. Default runtime is legacy/parity. Governed imperative `/chat` with flags is the demo/test path. LangGraph fan-out/fan-in is not built. Production adoption requires SOC sign-off + flag cutover."**
