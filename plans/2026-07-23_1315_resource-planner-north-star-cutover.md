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
| **B2** | `/chat` RP path: exception → 500 (only `response is None` falls back); stream catches errors | **Documented in item 10** — cutover must choose fail-loud vs catch-and-fallback |
| **B3** | `_apply_work_bundle_to_workers` silent `except Exception: return state` | **Fixed** — log warning + `decision_log` record `work_bundle.apply` |

## Repo hygiene (pre-commit)

- Items **2–7g** (+ B1/B3 fixes) remain **uncommitted** on working tree — commit in item-batches after `/invariant-check` skill; do not proceed to item **8** on a dirty uncommitted stack.
- Eval drift: restore `docs/evals/langgraph_dual_parity_*` before any commit (item 1 covered `soc_clean_answer_*` only; dual-parity timestamp drift is separate).

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

- [ ] **7h** — Fix unsafe intent probe baseline (`probe.unsafe.block_and_run`)
  - **Do:** Unsafe "block and run" probe must route to `clarification_required` / human-review, not `spl_generation_and_run`. Pre-existing baseline drift (9/11 on `eval_out_of_set_intent_probe.py --check`); downstream HIL still blocks execution but unsafe-intent classification regressing silently is safety-relevant. Fix routing/intent guard and refresh `docs/evals/intent_out_of_set_probes_baseline.json` only (no unrelated eval drift).
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check` exits 0; targeted pytest on unsafe-block probe if added
  - **Depends on:** 7g
  - **Evidence:** _(fill when done)_

- [ ] **8** — Decision gate for LLM-primary specialist planning
  - **Do:** Write a short proposal in this plan describing which specialist(s) may call the governed LLM adapter, the exact existing flag/mode to use, fallback behavior, disagreement handling, and why deterministic policy still wins. Stop for user/COE approval before coding this item.
  - **Verify:** User/COE approval recorded in this plan; no code changes for LLM-primary planning before that approval
  - **Depends on:** 7h
  - **Evidence:** _(fill when done)_

- [ ] **9** — Implement approved LLM-primary specialist proposal path
  - **Do:** If item 8 is approved, let selected specialists emit real proposals through the governed LLM adapter. Proposals remain advisory until Resource Planner merge validation accepts owned enrichments; conflicts produce warnings/disagreements and deterministic outputs win. Add RP-specialist-specific LLM proposal tests if the existing broader LLM suites do not fail meaningfully on this new path. If item 8 is not approved, explicitly mark this item deferred with evidence and continue only to non-LLM cutover gates.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hybrid_role_graph.py app/tests/test_guided_investigation_llm_firewall.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_dry_runs.py -q`; RP-specialist LLM proposal tests exist and fail if specialist LLM output bypasses merge validation or deterministic authority
  - **Depends on:** 8
  - **Evidence:** _(fill when done)_

- [ ] **10** — Decision gate to make RP graph the default runtime
  - **Do:** Produce a cutover proposal with item 7 results, **item 8 resolution** (LLM-primary approved or explicit deferral recorded in item 8 Evidence), item 9 status if implemented (optional — deferral is valid), production rollback instructions, expected metric/trace changes, and a traffic-pattern parity matrix. **Rollback:** `LANGGRAPH_ORCHESTRATION_ENABLED=false` **plus process restart** (`settings` is a module singleton — flag flip alone does not affect already-running uvicorn workers). **Exception policy (B2):** document chosen posture for `/chat` when RP graph raises (today: fail-loud 500; stream already surfaces `reporter.failed`). Options: deliberate fail-loud vs catch-and-fallback-to-imperative — pick one before item 11. Stop for explicit user/COE approval before changing the default runtime.
  - **Verify:** User/COE approval recorded in this plan; proposal includes rollback flag + restart steps; documents B2 exception policy; item 8 Evidence shows approve-or-defer decision
  - **Depends on:** 7g, 8
  - **Evidence:** _(fill when done)_

- [ ] **11** — Make RP graph default; keep imperative rollback temporarily
  - **Do:** After item 10 approval, change runtime default so `/chat` and `/chat/stream` use Resource Planner graph unless explicitly rolled back. Keep `build_live_chat_response()` available only as the documented rollback path during this item; update settings/docs/tests to match the new default posture.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_chat_progress_stream.py app/tests/test_cisco_live_chat_contract.py app/tests/test_live_chat_linear_progress.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 10
  - **Evidence:** _(fill when done)_

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

No current verification gaps. Items **0–7g** are checked with evidence. Items **7h**, **8**, **10**, and **12** (12a–12d) remain open. Items **2**, **4**, and **6** were completed with approval evidence recorded. Item **9** is optional after **8** resolves. **B1/B3** fixed in code; **B2** decision deferred to item **10** proposal. Uncommitted working-tree work must be batched and committed before item **8**.

## Drift Log

| Date | Note |
|------|------|
| 2026-07-23 | Created as follow-on to the completed `ideal-langgraph-resource-planner` plan. It tracks residual gaps only: imperative retirement, live catalogue routing, specialist merge, parallel fan-out, optional LLM-primary planning, and single-runner consolidation. |
| 2026-07-23 | Items 2–7 implemented on `feat/resource-planner-north-star`: `live_router_bind.py`, parallel `Send` specialists, `apply_specialist_reports` at merge, worker bundle sync. Pre-existing `probe.unsafe.block_and_run` intent baseline drift noted (not catalogue-related). |
| 2026-07-23 | Item **7b**: SPL two-turn HIL E2E contract locked in `test_spl_hil_two_turn_chat.py`. |
| 2026-07-23 | Review hardening **7c–7g**: `validated_work_bundle` worker channel, Option A specialist boundary doc, catalogue surface-agreement test, fan-in reducer assertions, `rp_fallback` single-runner invariant. |
| 2026-07-23 | **B1/B3** code fixes: ContextVar invoke guard + validated-bundle decision_log on reject. **7h** added for `probe.unsafe.block_and_run`. Item **10** documents rollback restart + B2 exception policy. Item **12a** defines degraded-response fallback semantics. |

## Residual Risk To Watch

- Catalogue adapter wiring can produce cosmetic trace improvements unless `intent_classification`, `evidence_plan`, and `route_adjudication` all consume the same selected use-case/template result.
- Specialist report merging can become trace-only unless SPL/MCP/RAG worker nodes consume **`validated_work_bundle`** (not raw `work_bundle`).
- Parallel fan-out can make decision logs nondeterministic unless report ordering is normalized before merge.
- Imperative retirement (**12a–12d**) is highest blast-radius — do not start until **7g** is green; execute as phased sub-items, not one PR.
- Turn-2 SPL confirmation must use `execution_review_action` on the same session/query; free-text "confirm" messages can reroute away from SPL execution.
- Response `spl_validation` on an `update_spl` turn may reflect template regeneration while `execution.executed_spl` reflects the gate-validated analyst SPL — tests and UI should treat execution envelope as authoritative for what ran.
