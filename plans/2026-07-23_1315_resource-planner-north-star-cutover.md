---
name: resource-planner-north-star-cutover
overview: "Close the residual Resource Planner gaps: live catalogue routing, merged specialist proposals, parallel specialist fan-out, optional LLM-primary planning, and eventual single-runner cutover."
status: draft
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
| Catalogue adapter | `match_catalogue_tier()` exists and binds typo aliases in tests; live router does not consume it |
| Specialist merge | `apply_specialist_reports()` exists; `rp_node_resource_planner_merge()` currently builds from `ResourcePlan` only |
| Specialist dispatch | Skill -> Knowledge -> MCP -> SPL is sequential in `resource_planner_graph.py` |
| LLM planning | Existing LLM surfaces remain advisory; deterministic authority still wins |

## Governance Invariants

- LLMs never call MCP directly.
- `candidate_spl` never executes.
- Only `spl_validation.approved=true` and non-null `normalized_spl` may reach the MCP execution gate.
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

`0 -> 1 -> 2 -> 3 -> 4 -> (5 and 6 may run in either order) -> 7 -> 8 -> 9 or explicit deferral -> 10 -> 11 -> 12`

## Decision Gates

| Gate | Required before |
|------|-----------------|
| Catalogue authority gate | Item 2 live-router wiring; approval must be recorded in item 2 Evidence before coding |
| Specialist proposal authority gate | Item 4 merged specialist output drives workers; approval must be recorded in item 4 Evidence before coding |
| Parallel topology gate | Item 6 `Send` fan-out; approval must be recorded in item 6 Evidence before coding |
| LLM-primary planning gate | Item 8 any specialist LLM proposal execution path |
| Runtime default gate | Item 10 proposal before item 11 makes RP graph default |
| Imperative retirement gate | Item 12 removing independent imperative/linear runners |

## Operational Hooks

- Before executing any checklist item, follow `.claude/skills/execute-plan-item/SKILL.md` manually: reconcile repo state, verify anchors, implement only the item, run the item's Verify command verbatim, record Evidence, and re-run the plan audit.
- Before any commit touching pipeline/planner/SPL/MCP/LLM code, follow `.claude/skills/invariant-check/SKILL.md`; one FAIL blocks the commit.
- When items 2-6 land, update `docs/architecture/ideal_langgraph_resource_planner.md` to keep the architecture doc aligned with the actual topology and authority flow.

## Checklist

- [x] **0** — Promote plan + index + discipline audit
  - **Do:** Save this plan under `plans/`, list it in `plans/README.md`, and run the plan discipline audit before implementation.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-23_1315_resource-planner-north-star-cutover.md` exits 0
  - **Depends on:** none
  - **Evidence:** Plan created at `plans/2026-07-23_1315_resource-planner-north-star-cutover.md`; `plans/README.md` indexed it; re-audit after review fixes: `Summary: 1 checked, 12 unchecked, 0 gap(s)`.

- [ ] **1** — Re-baseline repo state and parity surface
  - **Do:** Trace current `/chat`, `/chat/stream`, RP graph, linear LangGraph, catalogue adapter, and specialist merge seams. Record repo-vs-plan deltas in this plan before changing code, including any dirty eval baseline files that must not be committed accidentally.
  - **Verify:** `rg -n "LANGGRAPH_ORCHESTRATION_ENABLED|build_live_chat_response|run_chat_via_resource_planner_graph|match_catalogue_tier|apply_specialist_reports|specialist_skill|specialist_knowledge|specialist_mcp|specialist_spl" backend/app backend/app/tests plans docs` and update this plan's Drift Log with the confirmed paths
  - **Depends on:** 0
  - **Evidence:** _(fill when done)_

- [ ] **2** — Wire unified catalogue tiers into live routing
  - **Do:** Stop for explicit user/COE approval before coding because this changes the default imperative `/chat` routing surface, not only the RP graph toggle. After approval, feed `match_catalogue_tier()` into the live query path as an always-on adapter with strong regression gates; do not add a new flag unless that is separately approved. The match result must flow through `understand_query`, `build_query_to_intent`, `query_to_intent`, `intent_classification`, `plan_evidence` / `evidence_plan`, `candidate_mappings` / `routing_provenance`, and `route_adjudication` so analyst-visible route, `use_case_id`, `spl_template_id`, and evidence planning agree. Typo aliases such as `lgon` may fill missing catalogue fields but must not override COE/manual slots or non-SOC guards.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_catalogue_match_tiers.py app/tests/test_chat_routing.py app/tests/test_in_catalogue_contract_guard.py app/tests/test_105_path_honoring.py app/tests/test_resource_planner_dry_runs.py -q`
  - **Depends on:** 1
  - **Evidence:** _(fill when done)_

- [ ] **3** — Prove live catalogue wiring with novel probes
  - **Do:** Add out-of-set probes for typo failed-login, success-after-failure, SOP/playbook, MITRE-without-alert-context, HR/policy non-SOC, and guided out-of-registry SOC investigation. Assert no SPL for knowledge/non-SOC paths and no fake live rows. Prove pinned in-catalogue 105/50 behavior remains byte-identical or contract-identical per the existing guard; any eval baseline diff is a failure unless the user explicitly asked for a baseline refresh.
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check` plus `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_out_of_catalogue_scorecard.py app/tests/test_soc_clean_answer_eval.py app/tests/test_105_path_honoring.py app/tests/test_in_catalogue_contract_guard.py -q`; `git status --short docs/evals backend/app/tests/fixtures/in_catalogue_contract` shows no accidental baseline drift unless explicitly approved
  - **Depends on:** 2
  - **Evidence:** _(fill when done)_

- [ ] **4** — Merge specialist reports into the RP `WorkBundle`
  - **Do:** Stop for explicit user/COE approval before coding because specialist proposals will begin influencing worker inputs. After approval, update `rp_node_resource_planner_merge()` to validate and pass real specialist reports into `apply_specialist_reports()`. Preserve `validate_bundle_policy_parity()` guarantees: specialists cannot add unauthorized steps, remove policy checks, relax blocked statuses, set execution eligibility, or override deterministic facts. Record merge decisions in `decision_log` and `control_plane_trace`.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_dry_runs.py -q`
  - **Depends on:** 2
  - **Evidence:** _(fill when done)_

- [ ] **5** — Make code-worker nodes consume the merged bundle where it matters
  - **Do:** Ensure SPL, MCP, and knowledge/RAG worker adapters read the merged `work_bundle` for owned enrichments while the existing deterministic pipeline remains the executor. Worker behavior must change only when the merged bundle has a validated owned enrichment; otherwise current evidence-plan behavior is unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_planner_executor.py app/tests/test_mcp_tool_planner.py app/tests/test_evidence_planner.py -q`
  - **Depends on:** 4
  - **Evidence:** _(fill when done)_

- [ ] **6** — Convert specialists to parallel LangGraph fan-out
  - **Do:** Stop for explicit user/COE approval before coding because this changes the graph topology. After approval, replace the sequential `specialist_skill -> specialist_knowledge -> specialist_mcp -> specialist_spl` chain with LangGraph `Send` fan-out/fan-in or the repo-approved equivalent. Keep output deterministic by sorting/normalizing reports before merge, and keep every specialist in its ownership lane.
  - **Verify:** User/COE approval recorded in Evidence before code changes; then `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_specialist_registry.py app/tests/test_decision_record.py -q`; topology assertion proves no sequential specialist edge remains and all specialist reports reach merge
  - **Depends on:** 4
  - **Evidence:** _(fill when done)_

- [ ] **7** — Parity and governance gate after catalogue + specialist changes
  - **Do:** Re-run targeted RP, router, catalogue, and governance suites after items 2-6. Record pass/fail counts and any intentional analyst-visible deltas. Confirm `docs/architecture/ideal_langgraph_resource_planner.md` reflects item 2-6 behavior before marking this gate done.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_langgraph_chat_parity_p1.py app/tests/test_langgraph_dual_parity_phase13.py app/tests/test_current_chat_runtime_baseline.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 5, 6
  - **Evidence:** _(fill when done)_

- [ ] **8** — Decision gate for LLM-primary specialist planning
  - **Do:** Write a short proposal in this plan describing which specialist(s) may call the governed LLM adapter, the exact existing flag/mode to use, fallback behavior, disagreement handling, and why deterministic policy still wins. Stop for user/COE approval before coding this item.
  - **Verify:** User/COE approval recorded in this plan; no code changes for LLM-primary planning before that approval
  - **Depends on:** 7
  - **Evidence:** _(fill when done)_

- [ ] **9** — Implement approved LLM-primary specialist proposal path
  - **Do:** If item 8 is approved, let selected specialists emit real proposals through the governed LLM adapter. Proposals remain advisory until Resource Planner merge validation accepts owned enrichments; conflicts produce warnings/disagreements and deterministic outputs win. Add RP-specialist-specific LLM proposal tests if the existing broader LLM suites do not fail meaningfully on this new path. If item 8 is not approved, explicitly mark this item deferred with evidence and continue only to non-LLM cutover gates.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hybrid_role_graph.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_dry_runs.py -q`; RP-specialist LLM proposal tests exist and fail if specialist LLM output bypasses merge validation or deterministic authority
  - **Depends on:** 8
  - **Evidence:** _(fill when done)_

- [ ] **10** — Decision gate to make RP graph the default runtime
  - **Do:** Produce a cutover proposal with item 7 results, item 9 status or explicit LLM-primary deferral, production rollback instructions, expected metric/trace changes, and a traffic-pattern parity matrix. Stop for explicit user/COE approval before changing the default runtime. If item 9 is deferred, record the deferral in Evidence and proceed with LLM-primary marked out of scope.
  - **Verify:** User/COE approval recorded in this plan; proposal includes rollback by setting `LANGGRAPH_ORCHESTRATION_ENABLED=false`
  - **Depends on:** 7
  - **Evidence:** _(fill when done)_

- [ ] **11** — Make RP graph default; keep imperative rollback temporarily
  - **Do:** After item 10 approval, change runtime default so `/chat` and `/chat/stream` use Resource Planner graph unless explicitly rolled back. Keep `build_live_chat_response()` available only as the documented rollback path during this item; update settings/docs/tests to match the new default posture.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_chat_progress_stream.py app/tests/test_cisco_live_chat_contract.py app/tests/test_live_chat_linear_progress.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 10
  - **Evidence:** _(fill when done)_

- [ ] **12** — Retire independent imperative and linear LangGraph runners
  - **Do:** After a successful default-runtime soak or explicit user/COE go-ahead, retire in phases because `build_live_chat_response()` is imported by many tests. First make `build_live_chat_response()` a thin RP graph wrapper or compatibility facade, then migrate tests in batches from imperative-vs-LangGraph parity to RP graph regression, then remove `chat_workflow.py` as a separate runner. If compatibility requires keeping a function with the same name for imports, it must not contain a second orchestration implementation.
  - **Verify:** User/COE retirement approval recorded in Evidence before code changes; `rg -n "run_chat_via_langgraph|_compiled_chat_graph|_compiled_chat_graph_cp|build_live_chat_response\\(" backend/app backend/app/tests` shows no independent production runner remains; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`; `./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 11
  - **Evidence:** _(fill when done)_

## Verification Gaps

None at authoring time. Items 2, 4, 6, 8, 10, and 12 intentionally contain decision gates before stage-boundary behavior changes; item 11 is gated by item 10 approval.

## Drift Log

| Date | Note |
|------|------|
| 2026-07-23 | Created as follow-on to the completed `ideal-langgraph-resource-planner` plan. It tracks residual gaps only: imperative retirement, live catalogue routing, specialist merge, parallel fan-out, optional LLM-primary planning, and single-runner consolidation. |

## Residual Risk To Watch

- Catalogue adapter wiring can produce cosmetic trace improvements unless `intent_classification`, `evidence_plan`, and `route_adjudication` all consume the same selected use-case/template result.
- Specialist report merging can become trace-only unless SPL/MCP/RAG worker nodes consume the validated merged `WorkBundle`.
- Parallel fan-out can make decision logs nondeterministic unless report ordering is normalized before merge.
- Imperative retirement is high blast-radius because many tests import `build_live_chat_response()` directly.
