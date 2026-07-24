---
name: resource-planner-north-star-cutover
overview: "Close the residual Resource Planner gaps: live catalogue routing, merged specialist proposals, parallel specialist fan-out, optional LLM-primary planning, and eventual single-runner cutover."
status: in_progress
date: 2026-07-23
canonical_plan: plans/2026-07-23_1315_resource-planner-north-star-cutover.md
---

# Resource Planner North-Star Cutover

## Objective

Complete the work intentionally deferred by `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md` while keeping that plan's done status intact. Done means `/chat` has one production orchestration spine under the Resource Planner graph, live routing consumes the unified catalogue tiers, specialist reports are merged into the authoritative `WorkBundle` without bypassing policy, specialist dispatch can fan out in parallel, and any LLM-primary planning is explicitly gated, advisory, audited, and unable to execute MCP/SPL directly.

Items 2-7 deliver the main analyst-visible behavior. The full objective is only complete after item 12 retires the independent imperative and linear LangGraph runners.

## Current Baseline

| Area | Current state to preserve or change |
|------|-------------------------------------|
| Default runtime | `LANGGRAPH_ORCHESTRATION_ENABLED=false` still uses imperative `build_live_chat_response()` |
| Opt-in RP graph | `LANGGRAPH_ORCHESTRATION_ENABLED=true` routes `/chat` and `/chat/stream` through `resource_planner_graph.py` |
| Linear LangGraph | `chat_workflow.py` still exists for parity/shadow comparisons |
| Catalogue adapter | `match_catalogue_tier()` + `live_router_bind.py` wired into `graph_node_query_to_intent` (fill-blanks) |
| Specialist merge | `rp_node_resource_planner_merge()` calls `build_planner_iteration()` → `apply_specialist_reports()` |
| Specialist dispatch | Parallel LangGraph `Send` fan-out; stable-order merge |
| LLM planning | Existing LLM surfaces remain advisory; deterministic authority still wins |

## Governance Invariants

- LLMs never call MCP directly.
- `candidate_spl` never executes.
- Only `spl_validation.approved=true` and non-null `normalized_spl` may reach the MCP execution gate.
- **SPL two-turn HIL contract (production `/chat`):** Turn 1 generates `candidate_spl`, runs deterministic validation, and surfaces `human_review.review_type=spl_execution_confirmation` with `proposed_normalized_spl` — `executed_spl` stays null. Turn 2 uses the same query plus `execution_review_action=confirm` (runs pending normalized SPL) or `update_spl` + `analyst_provided_spl` (re-validates through guardrails first; invalid SPL → `spl_revision`, no execution). The MCP gate never calls `call_tool` with raw `candidate_spl`; only gate-validated normalized SPL is executed. Session pins carry `pending_execution_confirmation` between turns when session context is enabled.
- MCP execution remains default-off globally and per server; real execution needs explicit operator configuration.
- COE/manual authority wins over catalogue, RAG, session, MCP, and LLM hints for security-sensitive slots.
- Specialists may propose and enrich owned fields only; Resource Planner policy and deterministic gates remain authoritative.
- New flags require an explicit decision item. Prefer existing `LANGGRAPH_ORCHESTRATION_ENABLED` for runtime cutover and existing shadow/lab flags for comparison.
- Do not commit eval baseline drift (`soc_clean_answer_eval_*`, `langgraph_dual_parity_*`, etc.) unless the task is explicitly to refresh baselines.

## Stop Conditions

- All checklist items are checked with recorded evidence, **or**
- The same verification gate fails twice on one item, **or**
- A decision gate requires user/COE approval before continuing, **or**
- Repo audit shows a plan premise is stale enough that the checklist must be revised before coding.

## Dependency Order

`0 -> 1 -> 2 -> 3 -> 4 -> (5 and 6 may run in either order) -> 7 -> 7b -> 7c -> 7d -> 7e -> 7f -> 7g -> 7h -> 8 -> 9 (optional) -> 10 -> 11 -> 12a -> 12b -> 12c -> 12d`

### Post-review hardening sequence (2026-07-23)

Priority: **7c (validated bundle)** → **7d (specialist boundary doc)** → **7e (catalogue agreement)** → **7f (fan-in test)** → **7g (single-runner invariant)**. Item 12 retirement must not land before **7g**.

## Decision Gates

| Gate | Required before |
|------|-----------------|
| Catalogue authority gate | Item 2 live-router wiring; approval must be recorded in item 2 Evidence before coding |
| Specialist proposal authority gate | Item 4 merged specialist output drives workers; approval must be recorded in item 4 Evidence before coding |
| Parallel topology gate | Item 6 `Send` fan-out; approval must be recorded in item 6 Evidence before coding |
| LLM-primary planning gate | Item 8 any specialist LLM proposal execution path |
| Runtime default gate | Item 10 proposal before item 11 makes RP graph default; requires item **8** resolved (approved or explicit deferral) |
| Imperative retirement gate | Items **12a–12d** removing independent imperative/linear runners (phased; highest blast-radius) |

## Operational Hooks

- Before executing any checklist item, follow `.claude/skills/execute-plan-item/SKILL.md` manually: reconcile repo state, verify anchors, implement only the item, run the item's Verify command verbatim, record Evidence, and re-run the plan audit.
- Before any commit touching pipeline/planner/SPL/MCP/LLM code, follow `.claude/skills/invariant-check/SKILL.md`; one FAIL blocks the commit.
- When items 2-6 land, update `docs/architecture/ideal_langgraph_resource_planner.md` to keep the architecture doc aligned with the actual topology and authority flow.

## Code review verification (2026-07-23)

External review confirmed the following repo truths; hardening items **7c–7g** address the gaps:

| Finding | Status |
|---------|--------|
| Bootstrap composes `ResourcePlan` before delegate/specialists | Confirmed — specialists are post-plan enrichers (Option A) |
| `specialist_reports: Annotated[..., operator.add]`; `decision_log` patched post-fan-in | Confirmed — intentional (no reducer on `decision_log`) |
| `_apply_work_bundle_to_workers` read raw `work_bundle`; `any(source_specialist)` guard ineffective | **Fixed in 7c** — `validated_work_bundle` + `merge_decision_reason` gate |
| `validate_bundle_policy_parity` at merge; workers did not check merge reason | **Fixed in 7c** |
| `routes_chat` flag switch; RP fallback one-level (no recursion today) | **Hardened in 7g** — `entrypoint=rp_fallback` + re-entry guard |
| Catalogue bind can be trace-only across surfaces | **Guarded in 7e** — surface-agreement test |
| Parallel fan-in reducer done; missing reducer regression test | **Added in 7f** |

**Deferred (future north-star item):** Option B — merged bundle revises plan via second RP iteration / reconcile node.

## Bug fixes (review 2026-07-23, pre-item-8)

| ID | Issue | Fix |
|----|-------|-----|
| **B1** | `_RP_GRAPH_INVOKE_ACTIVE` module global not thread-safe; `assert` stripped under `python -O` | **Fixed** — `contextvars.ContextVar` depth + `guard_rp_imperative_fallback()` raises `RuntimeError` |
| **B2** | `/chat` RP path: exception → 500 (only `response is None` falls back); stream catches errors | **Resolved in item 10** — fail-loud/no exception-time imperative fallback; item 11 must add explicit regression coverage |
| **B3** | `_apply_work_bundle_to_workers` silent `except Exception: return state` | **Fixed** — log warning + `decision_log` record `work_bundle.apply` |

## Repo hygiene (pre-commit)

- Items **9** follow-ups plus item **10** plan/index updates are currently the pre-item-11 working stack. Commit them after `/invariant-check` before starting item **11** code changes.
- Eval drift remains a pre-commit blocker: do not commit `soc_clean_answer_eval_*`, `langgraph_dual_parity_*`, or other eval baseline churn unless the task explicitly refreshes baselines.

## Checklist

- [x] **0** — Promote plan + index + discipline audit
  - **Do:** Save this plan under `plans/`, list it in `plans/README.md`, and run the plan discipline audit before implementation.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-23_1315_resource-planner-north-star-cutover.md` exits 0
  - **Depends on:** none
  - **Evidence:** Plan created at `plans/2026-07-23_1315_resource-planner-north-star-cutover.md`; `plans/README.md` indexed it; re-audit after review fixes: `Summary: 1 checked, 12 unchecked, 0 gap(s)`.

- [x] **1** — Re-baseline repo state and parity surface
  - **Do:** Trace current `/chat`, `/chat/stream`, RP graph, linear LangGraph, catalogue adapter, and specialist merge seams. Record repo-vs-plan deltas in this plan before changing code, including any dirty eval baseline files that must not be committed accidentally.
  - **Verify:** `rg -n "LANGGRAPH_ORCHESTRATION_ENABLED|build_live_chat_response|run_chat_via_resource_planner_graph|match_catalogue_tier|apply_specialist_reports|specialist_skill|specialist_knowledge|specialist_mcp|specialist_spl" backend/app backend/app/tests plans docs` and update this plan's Drift Log with the confirmed paths
  - **Depends on:** 0
  - **Evidence:** `rg` confirmed seams: `routes_chat.py`/`routes_chat_stream.py` → `run_chat_via_resource_planner_graph`; imperative default `build_live_chat_response`; catalogue at `match_tiers.py` + new `live_router_bind.py`; RP merge/specialists in `resource_planner_graph.py`. Eval drift restored for `soc_clean_answer_*` and `langgraph_dual_parity_*` before commit.

- [x] **2** — Wire unified catalogue tiers into live routing
  - **Do:** Stop for explicit user/COE approval before coding because this changes the default imperative `/chat` routing surface, not only the RP graph toggle. After approval, feed `match_catalogue_tier()` into the live query path as an always-on adapter with strong regression gates; do not add a new flag unless that is separately approved. The match result must flow through `understand_query`, `build_query_to_intent`, `query_to_intent`, `intent_classification`, `plan_evidence` / `evidence_plan`, `candidate_mappings` / `routing_provenance`, and `route_adjudication` so analyst-visible route, `use_case_id`, `spl_template_id`, and evidence planning agree. Typo aliases such as `lgon` may fill missing catalogue fields but must not override COE/manual slots or non-SOC guards.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_catalogue_match_tiers.py app/tests/test_chat_routing.py app/tests/test_in_catalogue_contract_guard.py app/tests/test_105_path_honoring.py app/tests/test_resource_planner_dry_runs.py -q`
  - **Depends on:** 1
  - **Evidence:** User approval 2026-07-23: "you have all approval to wire the changes". Added `backend/app/catalogue/live_router_bind.py`; wired pre/post bind in `graph_node_query_to_intent`. `pytest … -q → 69 passed` (includes typo RP parity `use_case_id=auth_failed_login_spike`).

- [x] **3** — Prove live catalogue wiring with novel probes
  - **Do:** Add out-of-set probes for typo failed-login, success-after-failure, SOP/playbook, MITRE-without-alert-context, HR/policy non-SOC, and guided out-of-registry SOC investigation. Assert no SPL for knowledge/non-SOC paths and no fake live rows. Prove pinned in-catalogue 105/50 behavior remains byte-identical or contract-identical per the existing guard; any eval baseline diff is a failure unless the user explicitly asked for a baseline refresh.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check` plus `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_out_of_catalogue_scorecard.py app/tests/test_soc_clean_answer_eval.py app/tests/test_105_path_honoring.py app/tests/test_in_catalogue_contract_guard.py -q`; `git status --short docs/evals backend/app/tests/fixtures/in_catalogue_contract` shows no accidental baseline drift unless explicitly approved
  - **Depends on:** 2
  - **Evidence:** Added `app/tests/test_live_catalogue_router_probes.py` (6 probes). `pytest … -q → 59 passed`. In-catalogue guard green. `eval_out_of_set_intent_probe.py --check` pre-existing FAIL on `probe.unsafe.block_and_run` only (9/11; not introduced by catalogue bind — same diff without `live_router_bind.py`). No eval fixture drift committed.

- [x] **4** — Merge specialist reports into the RP `WorkBundle`
  - **Do:** Stop for explicit user/COE approval before coding because specialist proposals will begin influencing worker inputs. After approval, update `rp_node_resource_planner_merge()` to validate and pass real specialist reports into `apply_specialist_reports()`. Preserve `validate_bundle_policy_parity()` guarantees: specialists cannot add unauthorized steps, remove policy checks, relax blocked statuses, set execution eligibility, or override deterministic facts. Record merge decisions in `decision_log` and `control_plane_trace`.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_dry_runs.py -q`
  - **Depends on:** 2
  - **Evidence:** User approval 2026-07-23 (blanket wire approval). `rp_node_resource_planner_merge()` uses `build_planner_iteration(reports=…)`; specialist decision records emitted in stable order at merge. `pytest … -q → 49 passed`.

- [x] **5** — Make code-worker nodes consume the merged bundle where it matters
  - **Do:** Ensure SPL, MCP, and knowledge/RAG worker adapters read the merged `work_bundle` for owned enrichments while the existing deterministic pipeline remains the executor. Worker behavior must change only when the merged bundle has a validated owned enrichment; otherwise current evidence-plan behavior is unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_planner_executor.py app/tests/test_mcp_tool_planner.py app/tests/test_evidence_planner.py -q`
  - **Depends on:** 4
  - **Evidence:** `_apply_work_bundle_to_workers()` syncs merged bundle → `evidence_plan.resource_plan` before `composed_dispatch` / `workflow_spl`. `pytest … -q → 57 passed`. **Review follow-up (7c):** workers now read `validated_work_bundle` only; ineffective `any(source_specialist)` guard removed.

- [x] **6** — Convert specialists to parallel LangGraph fan-out
  - **Do:** Stop for explicit user/COE approval before coding because this changes the graph topology. After approval, replace the sequential `specialist_skill -> specialist_knowledge -> specialist_mcp -> specialist_spl` chain with LangGraph `Send` fan-out/fan-in or the repo-approved equivalent. Keep output deterministic by sorting/normalizing reports before merge, and keep every specialist in its ownership lane.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_specialist_registry.py app/tests/test_decision_record.py -q`; topology assertion proves no sequential specialist edge remains and all specialist reports reach merge
  - **Depends on:** 4
  - **Evidence:** User approval 2026-07-23. `_fan_out_specialists()` + `Send`; `specialist_reports` uses `Annotated[..., operator.add]`; `test_resource_planner_specialists_fan_out_in_parallel` proves no sequential edges + ≥4 reports at merge. `pytest … -q → 43 passed`.

- [x] **7** — Parity and governance gate after catalogue + specialist changes
  - **Do:** Re-run targeted RP, router, catalogue, and governance suites after items 2-6. Record pass/fail counts and any intentional analyst-visible deltas. Confirm `docs/architecture/ideal_langgraph_resource_planner.md` reflects item 2-6 behavior before marking this gate done.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_langgraph_chat_parity_p1.py app/tests/test_langgraph_dual_parity_phase13.py app/tests/test_current_chat_runtime_baseline.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 5, 6
  - **Evidence:** Parity pytest `23 passed, 6 xfailed`. `./scripts/run_stage3_governance_regression.sh → stage3_governance_regression: PASS` (~338s). Architecture doc updated (parallel Send, live catalogue bind, specialist merge).

- [x] **7b** — Lock SPL two-turn HIL E2E contract on `/chat`
  - **Do:** Add end-to-end `/chat` tests proving the analyst-visible execution handshake: turn 1 surfaces normalized SPL for `spl_execution_confirmation` with `executed_spl=null`; turn 2 `confirm` executes the normalized SPL; turn 2 `update_spl` with invalid SPL is blocked by guardrails; turn 2 `update_spl` with valid analyst SPL executes after re-validation. Tests must override conftest's confirmation disable, enable mock MCP execution, disable catalogue auto-execute, and skip shadow precondition blocks for the probe query so the path reliably reaches the confirmation gate.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_hil_two_turn_chat.py -q`
  - **Depends on:** 7
  - **Evidence:** Added `backend/app/tests/test_spl_hil_two_turn_chat.py` (4 tests: turn-1 confirmation surface, turn-2 confirm executes normalized SPL, bad `update_spl` → `spl_revision`, good `update_spl` → gate-validated execute). `pytest app/tests/test_spl_hil_two_turn_chat.py -q → 4 passed`. Turn 2 must repeat the original query plus `execution_review_action` (a bare "confirm execution" message routes away from SPL). On `update_spl`, `execution.executed_spl` reflects gate-validated analyst SPL even when response `spl_validation` still shows the regenerated template from the pipeline re-run.

- [x] **7c** — Validated WorkBundle channel (review point 5)
  - **Do:** Add `validated_work_bundle` written only after `validate_bundle_policy_parity()` at merge; gate `_apply_work_bundle_to_workers()` on `merge_decision_reason=specialist_reports_merged`; set `source_specialist` only when a specialist proposal enriches a task. Tests: valid enrichment reaches workers; unvalidated bundle ignored; policy bypass fails closed at materialize.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_validated_work_bundle.py app/tests/test_planner_hierarchy_contracts.py -q`
  - **Depends on:** 5, 7b
  - **Evidence:** `validated_work_bundle` on `ResourcePlannerGraphState`; merge writes channel when `specialist_reports_merged`. `test_resource_planner_validated_work_bundle.py` → 5 passed.

- [x] **7d** — Specialist authority boundary Option A (review point 3)
  - **Do:** Document v1 boundary: bootstrap composes `ResourcePlan` before specialists; specialists enrich `WorkBundle.args_template` only; route/intent/evidence_plan stay deterministic. Defer Option B (second RP reconcile) to future item.
  - **Verify:** `rg -n "Option A|post-plan enrich" docs/architecture/ideal_langgraph_resource_planner.md`
  - **Depends on:** 7c
  - **Evidence:** Architecture doc §2 — Option A v1 boundary + Option B deferral.

- [x] **7e** — Catalogue surface-agreement gate (review point 6)
  - **Do:** Add `test_catalogue_bind_surface_agreement` — fails when catalogue `use_case_id` disagrees across `selected_use_case`, `evidence_plan`, `candidate_mappings`, or `control_plane_trace.routing_provenance`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_catalogue_bind_surface_agreement.py -q`
  - **Depends on:** 2, 7c
  - **Evidence:** `test_catalogue_bind_surface_agreement.py` → 1 passed (typo failed-login probe).

- [x] **7f** — Parallel fan-in reducer hardening (review point 4)
  - **Do:** Extend RP skeleton test: N specialists via `Send` → unique lanes merged; `validated_work_bundle.merge_decision_reason` set; `decision_log` reducer-free (patched post-fan-in at merge).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py -q`
  - **Depends on:** 6, 7c
  - **Evidence:** `test_resource_planner_specialists_fan_out_in_parallel` extended with unique specialist lanes + validated bundle marker.

- [x] **7g** — Single-runner invariant before item 12 (review point 7)
  - **Do:** `routes_chat` sole RP-vs-imperative selector. RP fallback passes `entrypoint=rp_fallback`; imperative path guards against RP re-entry when `entrypoint.startswith("rp_")`. Regression tests before item-12 refactor.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py -k "rp_fallback or invoke" -q`
  - **Depends on:** 7f
  - **Evidence:** `run_chat_via_resource_planner_graph` fallback → `entrypoint=rp_fallback`. **B1 fix:** `contextvars` invoke depth + `guard_rp_imperative_fallback()` (`RuntimeError`, not `assert`). `test_rp_fallback_*` + context-local guard tests green.

- [x] **7h** — Fix unsafe intent probe baseline (`probe.unsafe.block_and_run`)
  - **Do:** Unsafe "block and run" probe must route to `clarification_required` / human-review, not `spl_generation_and_run`. Pre-existing baseline drift (9/11 on `eval_out_of_set_intent_probe.py --check`); downstream HIL still blocks execution but unsafe-intent classification regressing silently is safety-relevant. Fix routing/intent guard and refresh `docs/evals/intent_out_of_set_probes_baseline.json` only (no unrelated eval drift).
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check` exits 0; targeted pytest on unsafe-block probe if added
  - **Depends on:** 7g
  - **Evidence:** Fixed intent precedence so `block_or_contain` + explicit SPL execution signals route to `clarification_required` / `human_review`; final chat unsafe response keeps `unsafe_action_blocked` over explicit-run labeling. `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check` → PASS (11/11). `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_routing.py -q` → 6 passed. Adjacent regression slice `test_query_to_intent.py test_route_policy_smoke_fix.py test_explicit_run_spl_routing.py test_explicit_run_spl_hil.py -q` → 56 passed. Baseline refresh not required.

- [x] **8** — Decision gate for LLM-primary specialist planning
  - **Do:** Write a short proposal in this plan describing which specialist(s) may call the governed LLM adapter, the exact existing flag/mode to use, fallback behavior, disagreement handling, and why deterministic policy still wins. Stop for user/COE approval before coding this item.
  - **Verify:** User/COE approval recorded in this plan; no code changes for LLM-primary planning before that approval
  - **Depends on:** 7h
  - **Evidence:** Proposal written 2026-07-23. **User decision 2026-07-24: LLM-primary deferred** ("we may add LLM later"); item **9** re-scoped to a deterministic knowledge synthesis specialist (no LLM adapter calls). Cutover gate **10** unblocked (approve-or-defer recorded). No LLM-primary code written.

#### Item 8 Proposal — LLM-Primary Specialist Planning

**Recommended decision:** defer item **9** until after the RP default-runtime cutover proposal (**10**) is approved. The current deterministic RP graph is now carrying the catalogue/specialist changes; adding a live specialist LLM hop before the runtime-default decision increases blast radius without being required for items **10–12**.

If COE approves item **9** before cutover, scope it to **Knowledge specialist only**:

- **Allowed specialist:** `specialist_knowledge` may call the governed LLM adapter to propose knowledge/evidence-domain enrichments only (`reference_domains`, evidence-gap labels, approved corpus ids). It may not propose SPL, MCP tools, route changes, severity/MITRE facts, source profiles, or execution actions.
- **Blocked specialists for item 9:** `specialist_skill`, `specialist_mcp`, and `specialist_spl` remain deterministic/advisory only. SPL generation continues through governed templates / existing SPL failover paths; MCP selection remains deterministic; skill routing remains catalogue + deterministic adjudication.
- **Existing flags/mode only:** no new flags. The hop may run only when `control_plane_enabled=true`, `ROUTING_MODE=llm_primary_lab`, `ROUTING_LAB_LLM_PRIMARY_ENABLED=true`, and existing governed LLM gates are on (`bridge_enabled()` / live LLM sidecar availability). Config already rejects `llm_primary_lab` in production.
- **Fallback:** flags off, timeout, budget exhaustion, missing client, invalid JSON, unknown resource/domain, or validation failure returns the current deterministic `KnowledgeSpecialistReport(decision_reason="knowledge_lane_idle_or_rag")`; record a skipped/rejected decision in `decision_log` and continue.
- **Disagreement handling:** LLM output is advisory data. It may fill blank knowledge-owned fields only. Conflicts with deterministic route, `intent_classification`, `evidence_plan`, selected use case, COE/manual slots, validated templates, or policy checks are dropped with `warnings` / `disagreements`.
- **Why deterministic still wins:** `rp_node_resource_planner_merge()` remains the only fan-in authority; workers read only `validated_work_bundle` after `validate_bundle_policy_parity()` and `merge_decision_reason=specialist_reports_merged`. The LLM never calls MCP, never emits executable SPL, never sets execution eligibility, and cannot authorize action tiers.

**Approval choices for COE/user:** approve the limited Knowledge-specialist LLM proposal path for item **9**, or explicitly defer **9** and proceed to the non-LLM cutover gate (**10**).

- [x] **9** — Deterministic knowledge synthesis specialist _(re-scoped 2026-07-24; LLM path deferred to a future north-star item)_
  - **Do:** Implement a deterministic (no-LLM) knowledge specialist that audits plan vs intent vs required evidence: compare intent-demanded knowledge domains (`intent_family`, `answer_goal`, `needs_rag`/`needs_mitre`, `required_evidence_keys`) against knowledge-owned `ResourcePlan` steps (`knowledge_retrieval`, `cve_lookup`, `mitre_mapping`). Emit `reference_domains`, gap warnings (`knowledge_gap:<domain>:no_plan_step`, surplus-step warnings), and fill-blank `SpecialistProposal`s on owned steps that lack `reference_domains` args (never override existing args; merge validation stays authoritative). Thin consumer: reference dispatch (`_resolve_reference_knowledge`) scopes keyword search to merged `reference_domains` when the validated bundle carries them; explicit-ID lookups stay unscoped; SOC-KB RAG unchanged; imperative path unchanged when no args exist. Sync validated bundle in `rp_node_prepare_rag_only` before `rag_early`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_knowledge_specialist_audit.py app/tests/test_hybrid_role_graph.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_dry_runs.py -q`; matrix tests cover "intent says X, plan has Y → report Z" including merge integration and dispatch scoping
  - **Depends on:** 8
  - **Evidence:** Added `backend/app/planner/knowledge_specialist.py` (`build_knowledge_audit_report`); `rp_node_specialist_knowledge` emits audit report; merge decision record reflects actual knowledge reason. Thin consumer: `_knowledge_reference_domains` + `_reference_dataset_allowed` scope reference-registry keyword search only (SOC-KB RAG collection selection unchanged — documented in `pipeline.py` + architecture §6.1). Follow-ups (2026-07-24): `required_evidence_keys` → domain map (`reference_dataset`→`reference_lookup`, `vulnerability_source`→`cve`); `rp_node_prepare_rag_only` syncs `validated_work_bundle` before `rag_early`; architecture doc updated; intent-map alignment comment in module. `test_knowledge_specialist_audit.py` → 17 passed. Item-9 verify slice → 51 passed.

#### Item 10 readiness (pre-proposal audit, 2026-07-24)

| Gate | Status |
|------|--------|
| Items 0–9 complete with evidence | **Yes** |
| Item 8 LLM deferral recorded | **Yes** |
| Intent probe 11/11 | **Yes** (item 7h) |
| Governance regression (last full run) | **Pending** — re-run before item 11; targeted slices green post-9 |
| RP graph parity (dry runs, route wiring, SPL HIL) | **Green** on targeted tests |
| Knowledge audit active | **RP graph only** until item 11 — document in parity matrix |
| B2 exception policy chosen | **Yes** — fail-loud on escaped `/chat` RP defects; `/chat/stream` emits terminal failed event; no catch-and-imperative fallback |
| COE/user approval for default flip | **Yes for planning gate** — user 2026-07-24: "assume that you have all approval from COE"; code flip still executes in item 11 with regression evidence |

**Conclusion:** Ready to execute item **11** after committing the item-9 stack and re-running governance regression. Item **10** approval + B2 decision are recorded below.

- [x] **10** — Decision gate to make RP graph the default runtime
  - **Do:** Produce a cutover proposal with item 7 results, **item 8 resolution** (LLM-primary approved or explicit deferral recorded in item 8 Evidence), item 9 status if implemented (optional — deferral is valid), production rollback instructions, expected metric/trace changes, and a traffic-pattern parity matrix. **Rollback:** `LANGGRAPH_ORCHESTRATION_ENABLED=false` **plus process restart** (`settings` is a module singleton — flag flip alone does not affect already-running uvicorn workers). **Exception policy (B2):** document chosen posture for `/chat` when RP graph raises (today: fail-loud 500; stream already surfaces `reporter.failed`). Options: deliberate fail-loud vs catch-and-fallback-to-imperative — pick one before item 11. Stop for explicit user/COE approval before changing the default runtime.
  - **Verify:** User/COE approval recorded in this plan; proposal includes rollback flag + restart steps; documents B2 exception policy; item 8 Evidence shows approve-or-defer decision
  - **Depends on:** 7g, 8
  - **Evidence:** User/COE approval recorded 2026-07-24 from prompt: "assume that you have all approval from COE." Proposal below chooses one production path: RP graph default, no exception-time fallback to the old imperative runner, rollback only by `LANGGRAPH_ORCHESTRATION_ENABLED=false` + process restart. Plan audit after item-10 update: `Summary: 18 checked, 6 unchecked, 0 gap(s)`.

#### Item 10 Cutover Proposal — One Production Spine

**Architectural decision:** make the Resource Planner graph the single production orchestration spine for `/chat` and `/chat/stream` in item **11**. The old imperative path remains only as a temporary rollback implementation behind `LANGGRAPH_ORCHESTRATION_ENABLED=false` until item **12a** turns it into a compatibility/degraded-response facade. Do not add a second runtime selector or a new cutover flag.

**Exception policy (B2):** keep escaped RP exceptions fail-loud for `/chat` and terminal-failed for `/chat/stream`; do **not** catch RP defects and silently fall back to the old imperative runner. Rationale: fallback-on-exception creates two production paths, can hide validated-bundle or specialist bugs, and can produce different analyst-visible routing after the same request. Ordinary producer/LLM/tool degradation still happens inside governed pipeline nodes and returns controlled deterministic responses; only unhandled defects escape.

**Rollback runbook:** set `LANGGRAPH_ORCHESTRATION_ENABLED=false`, restart every backend process/uvicorn worker, then run the rollback smoke set. Restart is mandatory because `settings` is a module singleton and an env flip alone does not change already-loaded workers. Rollback is operational, not automatic per request.

**Minimum rollback smoke set:**

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_current_chat_runtime_baseline.py -q
./scripts/run_stage3_governance_regression.sh
```

**Traffic-pattern parity matrix for item 11 implementation:**

| Pattern | Expected RP default behavior | Must prove before done |
|---------|------------------------------|------------------------|
| In-catalogue SPL hunt, clean query | Catalogue `use_case_id`, `spl_template_id`, evidence plan, candidate mapping, and route adjudication agree; candidate SPL remains non-executable until HIL/gate approval | Surface-agreement test + `test_105_path_honoring.py` / in-catalogue guard |
| In-catalogue SPL hunt, typo query (`lgon`) | Catalogue alias fills blanks only; COE/manual slots and non-SOC guards still win | Live catalogue typo probe + route wiring test |
| SPL two-turn execution | Turn 1 produces `spl_execution_confirmation`; turn 2 confirm/update executes only validated `normalized_spl`; raw `candidate_spl` never reaches MCP | `test_spl_hil_two_turn_chat.py` |
| Knowledge recall / SOP / playbook | Routes to `knowledge_recall`; no SPL draft, no MCP execution; reference-domain scoping can enrich RP graph path | `test_knowledge_specialist_audit.py` + SOP/playbook probe |
| MITRE without alert context | Human-review clarification, no SPL and no fabricated facts | Out-of-set intent probe |
| Guided out-of-registry SOC investigation | Guided investigation remains review-only with hypotheses/evidence guidance; no execution eligibility | Guided/firewall tests |
| Non-SOC HR/policy query | Early out-of-scope/non-SOC exit before explicit-search/SPL machinery | Out-of-set intent probe |
| EC/demo parity scenario | Demo path remains deterministic `coe_synthetic_fixture`; RP cutover must not call live LLM/MCP in EC | Existing EC/live contract tests |
| `/chat/stream` progress path | Same RP graph result as `/chat`; failures surface as `reporter.failed`, not hidden fallback | `test_chat_progress_stream.py` / live progress test |
| RP graph returns `response=None` | Temporary item-11 behavior may use documented `rp_fallback`; item **12a** replaces this with explicit degraded facade and no second full runner | Route wiring fallback tests; item 12a retirement gate |
| RP graph raises unhandled exception | `/chat` logs `chat_pipeline_failed` with trace id and returns sanitized HTTP 500; stream sends failed event; no imperative fallback | Add item-11 regressions `test_rp_default_unhandled_exception_fails_loud_without_imperative_fallback` and `test_rp_stream_unhandled_exception_emits_failed_event` |
| Rollback flag false + restart | `/chat` and `/chat/stream` use temporary imperative rollback path only while item 11 is active | Route selector tests |

**Metrics / trace contract after item 11:**

| Signal | Expected change |
|--------|-----------------|
| `response.note` | Includes `Orchestration: resource_planner_hierarchy` for live RP turns; item **11** drops the old `(parity mode)` wording when RP becomes default and updates assertions accordingly |
| `control_plane_trace.decision_log` | Includes RP decision records patched from graph state, including specialist merge / validated-bundle decisions where applicable |
| `control_plane_trace.routing_provenance` | Catalogue tier fields agree with selected use case and evidence plan for in-catalogue paths |
| `rp_graph_trace` / planner iteration | Records bootstrap, specialist fan-out/fan-in, merge reason, and worker handoff in stable order |
| Trace admission | `/chat` and `/chat/stream` persist admission before work and preserve `X-Trace-ID` correlation |
| Failure telemetry | Escaped `/chat` failure logs `chat_pipeline_failed trace_id=<id> exc_type=<type>`; stream emits failed SSE payload with stable code/message |
| Governance counters | No increase in MCP execution unless explicit execution flags + HIL/gate approval are present; LLM direct tool-calling remains false |
| Analyst-visible execution fields | `candidate_spl` may be present; `executed_spl` only appears from validated execution envelope; `execution_enabled` remains false unless already approved by existing gates |

**Item 11 acceptance gates:** item 11 must update settings/tests/docs for the default flip, add explicit exception-policy regression coverage, drop `(parity mode)` from the RP note, run the traffic matrix slices above, run governance regression, and record dated pass/fail counts as operational sign-off. If any matrix row fails twice, stop; do not ship a mixed fallback architecture.

- [x] **11** — Make RP graph default; keep imperative rollback temporarily
  - **Do:** After item 10 approval, change runtime default so `/chat` and `/chat/stream` use Resource Planner graph unless explicitly rolled back. Keep `build_live_chat_response()` available only as the documented rollback path during this item; update settings/docs/tests to match the new default posture. Add regression coverage for the item-10 exception policy: `test_rp_default_unhandled_exception_fails_loud_without_imperative_fallback` proves RP raises do not call imperative fallback and `/chat` returns the sanitized 500 envelope; `test_rp_stream_unhandled_exception_emits_failed_event` proves stream emits `reporter.failed`. Keep `response=None` distinct from exceptions: during item 11 it may still complete through `rp_fallback` and `reporter.final` intentionally; item **12a** retires that behavior into a degraded facade. Drop `(parity mode)` from the RP orchestration note because RP is no longer a parity runner once default.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_chat_progress_stream.py -k "exception_policy or unhandled_exception or rp_fallback" -q && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_chat_progress_stream.py app/tests/test_cisco_live_chat_contract.py app/tests/test_live_chat_linear_progress.py app/tests/test_catalogue_bind_surface_agreement.py app/tests/test_spl_hil_two_turn_chat.py app/tests/test_knowledge_specialist_audit.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_105_path_honoring.py app/tests/test_in_catalogue_contract_guard.py -q && cd .. && PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 10
  - **Evidence:** 2026-07-24 — exception-policy slice **4 passed** (`test_rp_default_unhandled_exception_fails_loud_without_imperative_fallback`, `test_rp_stream_unhandled_exception_emits_failed_event`, plus `rp_fallback` guards); traffic-matrix pytest bundle **94 passed**; intent probe **11/11 PASS**; `./scripts/run_stage3_governance_regression.sh` **PASS** (backend pytest **4208 passed**, harness 6/6, sentinel 17/17). Default flip: `langgraph_orchestration_enabled=True` in `config.py` + `.env.example`; RP note now `Orchestration: resource_planner_hierarchy.` (no `(parity mode)`). Parity fix: removed `policy_veto` `requires_hil`→`human_review.required` coercion so guided/out-of-catalog `out_of_catalog_notice` matches imperative finalize; imperative-path tests pin `langgraph_orchestration_enabled=False` where they mock legacy hooks.

- [ ] **12** — Retire independent imperative and linear LangGraph runners _(highest blast-radius — decompose into 12a–12d before coding; do not implement as a single PR)_

- [ ] **12a** — Imperative compatibility facade
  - **Do:** Make `build_live_chat_response()` a thin RP-graph wrapper or documented compatibility facade. Preserve `entrypoint=rp_fallback` one-level semantics and the **7g** re-entry guard (`guard_rp_imperative_fallback`). No second orchestration implementation in the facade body. **Post-retirement fallback semantics:** when RP graph returns `response=None` or pre-finalize failure, facade emits an explicit **degraded** `PlaceholderResponse` (honest note, no SPL/MCP execution) — it must **not** re-invoke RP graph or recurse through `rp_fallback` into a second full pipeline. Transitional period (items 11–12b): documented imperative shim may still exist for rollback only.
  - **Verify:** `rg -n "def build_live_chat_response|_run_live_chat_pipeline" backend/app/chat/pipeline.py backend/app/graph/resource_planner_graph.py`; targeted pytest on route wiring + RP fallback tests green
  - **Depends on:** 11, 7g
  - **Evidence:** _(fill when done)_

- [ ] **12b** — Migrate tests off imperative-vs-linear parity (batched)
  - **Do:** Migrate tests in batches from `build_live_chat_response` / `run_chat_via_langgraph` imperative-vs-linear parity to RP-graph regression. One batch per PR; record batch list and remaining imports in Drift Log after each batch.
  - **Verify:** Per batch: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest <batch-test-paths> -q`; `rg -c "run_chat_via_langgraph" backend/app/tests` count decreases or is justified
  - **Depends on:** 12a
  - **Evidence:** _(fill when done)_

- [ ] **12c** — Remove linear LangGraph production runner
  - **Do:** Remove `chat_workflow.py` as a separate `/chat` runner after 12b batches pass. Retain shadow/parity helpers only if still required; production path must be RP graph + documented rollback facade.
  - **Verify:** `rg -n "run_chat_via_langgraph|_compiled_chat_graph" backend/app/api backend/app/graph` shows no production `/chat` entry; parity tests updated or retired with evidence
  - **Depends on:** 12b
  - **Evidence:** _(fill when done)_

- [ ] **12d** — Full regression and single-runner sign-off
  - **Do:** User/COE retirement approval recorded. Re-run full backend pytest + governance regression. Confirm `routes_chat` is the sole orchestration selector and no independent imperative runner remains in production code paths.
  - **Verify:** User/COE retirement approval in Evidence; `rg -n "run_chat_via_langgraph|_compiled_chat_graph|_compiled_chat_graph_cp" backend/app/api backend/app/graph`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`; `./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 12c
  - **Evidence:** _(fill when done)_

## Verification Gaps

No current plan-structure gaps. Items **0–11** are checked with evidence (item **8** LLM-primary deferral; item **9** deterministic knowledge specialist; item **10** COE-approved RP cutover proposal; item **11** RP default flip + exception-policy regressions). Remaining: **12** retirement (12a–12d). **B1/B3** fixed in code; **B2** resolved in item **10** as fail-loud/no hidden imperative fallback.

## Drift Log

| Date | Note |
|------|------|
| 2026-07-23 | Created as follow-on to the completed `ideal-langgraph-resource-planner` plan. It tracks residual gaps only: imperative retirement, live catalogue routing, specialist merge, parallel fan-out, optional LLM-primary planning, and single-runner consolidation. |
| 2026-07-23 | Items 2–7 implemented on `feat/resource-planner-north-star`: `live_router_bind.py`, parallel `Send` specialists, `apply_specialist_reports` at merge, worker bundle sync. Pre-existing `probe.unsafe.block_and_run` intent baseline drift noted (not catalogue-related). |
| 2026-07-23 | Item **7b**: SPL two-turn HIL E2E contract locked in `test_spl_hil_two_turn_chat.py`. |
| 2026-07-23 | Review hardening **7c–7g**: `validated_work_bundle` worker channel, Option A specialist boundary doc, catalogue surface-agreement test, fan-in reducer assertions, `rp_fallback` single-runner invariant. |
| 2026-07-24 | Item **9** follow-ups: `required_evidence_keys` domain map, `rp_node_prepare_rag_only` bundle sync, RAG-vs-reference consumer boundary documented, architecture §6.1 updated; 17 audit tests + item-10 readiness table in plan. |
| 2026-07-23 | **B1/B3** code fixes: ContextVar invoke guard + validated-bundle decision_log on reject. **7h** added for `probe.unsafe.block_and_run`. Item **12a** defines degraded-response fallback semantics. |
| 2026-07-24 | Item **10** completed as COE-approved cutover proposal: RP graph is the one production spine, B2 policy is fail-loud/no hidden imperative fallback, rollback is `LANGGRAPH_ORCHESTRATION_ENABLED=false` + process restart, and item **11** must satisfy the traffic-pattern matrix plus metrics/trace contract. |
| 2026-07-24 | Item **11** shipped: `langgraph_orchestration_enabled` default **true**; RP orchestration note drops `(parity mode)`; exception-policy tests `test_rp_default_unhandled_exception_fails_loud_without_imperative_fallback` + `test_rp_stream_unhandled_exception_emits_failed_event`; `policy_veto` no longer forces `human_review.required` from `requires_hil` (guided notice parity); governance regression PASS 4208 pytest + 11/11 intent + 94 matrix slice. |

## Residual Risk To Watch

- Catalogue adapter wiring can produce cosmetic trace improvements unless `intent_classification`, `evidence_plan`, and `route_adjudication` all consume the same selected use-case/template result.
- Specialist report merging can become trace-only unless SPL/MCP/RAG worker nodes consume **`validated_work_bundle`** (not raw `work_bundle`).
- Parallel fan-out can make decision logs nondeterministic unless report ordering is normalized before merge.
- Imperative retirement (**12a–12d**) is highest blast-radius — do not start until **7g** is green; execute as phased sub-items, not one PR.
- Turn-2 SPL confirmation must use `execution_review_action` on the same session/query; free-text "confirm" messages can reroute away from SPL execution.
- Response `spl_validation` on an `update_spl` turn may reflect template regeneration while `execution.executed_spl` reflects the gate-validated analyst SPL — tests and UI should treat execution envelope as authoritative for what ran.
- Item **11** must not add a catch-and-fallback-to-imperative handler around RP graph exceptions; that would reintroduce two production paths and invalidate item **10**.
