---
name: ideal-langgraph-resource-planner
overview: "Hierarchical LangGraph under Resource Planner with domain specialists (Skill, MCP, Knowledge, SPL); governance/audit retained; LLM plans, code executes."
status: done
date: 2026-07-23
canonical_plan: plans/2026-07-23_1305_ideal-langgraph-resource-planner.md
---

# Ideal LangGraph — Resource Planner hierarchy

## Objective

Replace dual imperative/LangGraph runners with **one** LangGraph where **Resource Planner** (apex) delegates to **sequentially dispatched** domain specialists (Skill → Knowledge → MCP → SPL; disjoint ownership, LangGraph `Send` parallel fan-out deferred). Specialists propose; **code workers** execute MCP/RAG/registry/SPL; **governance nodes** veto unsafe actions. Every hop logs **DecisionRecord** with `decision_reason`. Unified catalogue (105 + use cases). Design doc + contracts first; graph migration in later items.

Implementation must **reuse and reconcile** the existing planner stack before adding new surfaces:

- `backend/app/planner/resource_plan.py` (`ResourcePlan`, `ResourcePlanV2`, `PlanStep*`)
- `backend/app/planner/composer.py`, `backend/app/planner/executor.py`
- `backend/app/graph/planner_led_shadow_graph.py`
- `backend/app/skills/catalog.json`, `backend/app/use_cases/catalog.json`, `backend/app/planner/resource_registry_v1.json`

## Governance invariants (never remove)

- LLM never calls MCP directly; `candidate_spl` never executes.
- `execution_eligible` / severity / MITRE status from `decide_facts`, not specialists.
- SPL validate + MCP gate + HIL before search.
- `spl_validate`, `mcp_execution_gate`, `context_sufficiency`, `decide_facts`, `answer_guard`, `validate_final_answer`, `human_review`, `policy_veto` stay in graph.
- Do not add a new env flag without an explicit decision gate. Prefer the existing `AI_SOC_LANGGRAPH_SHADOW_ENABLED` for shadow-only runs and `LANGGRAPH_ORCHESTRATION_ENABLED` for eventual cutover after parity.
- Any new top-level LangGraph state key, including `decision_log`, must be declared on `ChatPipelineState` and covered by state-channel parity tests.

## Architecture (summary)

```
bootstrap (code) → Resource Planner
  → specialists (sequential dispatch): Skill → Knowledge → MCP → SPL
  → RP merge → WorkBundle → code workers → gates → RP loop
  → decide_facts → compose → guard → policy_veto → finalize → validate_final_answer + trace
```

**Ownership (disjoint):** Skill = catalogue + skill. MCP = identify/search hops. Knowledge = ATLAS/CVE/MITRE/RAG. SPL = compose path. RP = delegate/merge/schedule only. **Execution model:** specialists run serially in v1; parallel `Send` fan-out is deferred (see follow-up gaps).

## Stop conditions

- All checklist items checked with evidence, **or**
- Same Verify gate fails twice on one item, **or**
- Decision gate needs user (e.g. retire imperative before parity green)

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15`

## Review findings to fix before execution

| Severity | Finding | Plan correction |
|----------|---------|-----------------|
| High | Item 6 proposed `AI_SOC_RESOURCE_PLANNER_GRAPH_ENABLED`, but repo invariant-check blocks new flags unless explicitly approved. | Do not add that flag in this plan. Build the graph as a callable/test-only surface first; future route cutover uses a decision gate. |
| High | A `bootstrap -> RP stub -> finalize` graph can pass compile tests while bypassing `spl_validate`, `mcp_execution_gate`, `context_sufficiency`, `decide_facts`, `answer_guard`, `validate_final_answer`, `human_review`, and `policy_veto`. | Skeleton must encode these governance nodes as explicit nodes or documented adapters to current node functions before any route can call it. |
| High | New `planner_hierarchy.py`, `specialist_registry.json`, and `catalogue/entries.schema.json` can become parallel truth beside existing `ResourcePlan`, skill catalog, use-case catalog, and resource registry. | Contract/registry work must extend or adapt existing surfaces; tests must prove no duplicate/disconnected authority. |
| Medium | LangGraph silently drops undeclared state keys. `decision_log` is not currently on `ChatPipelineState`. | Item 4 must add the state channel and a graph-retention test. |
| Medium | Under the dry-run CP/sentinel harness, typo query `failed lgon spike top users last hour` routes to `spl_generation` with no live-router use-case bind and fallback/lab-only draft SPL. Plain local defaults can route differently. | Unified catalogue work must include fuzzy/alias tier tests if catalogue coverage is an objective, and live-router wiring must stay a separate follow-up. |
| Medium | Planner-led shadow and imperative paths differ on guided OT RAG step status (`skipped_unavailable` vs `not_run`) while core parity passes. | Add a step-status parity assertion before using shadow topology as migration evidence. |

## Checklist

- [x] **0** — Promote plan + index + discipline audit
  - **Do:** Save this file under `plans/`; add row to `plans/README.md`; run audit script
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-23_1305_ideal-langgraph-resource-planner.md` exits 0
  - **Depends on:** none
  - **Evidence:** initial audit script → `Summary: 0 checked, 8 unchecked, 0 gap(s)`; review re-audit after adding gates/tests → `Summary: 1 checked, 9 unchecked, 0 gap(s)`; plan at `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md`; README row added 2026-07-23

- [x] **1** — Hierarchy contract models (Pydantic, reconciled with existing planner contracts)
  - **Do:** Add hierarchy contracts only after mapping them to existing `ResourcePlan`/`ResourcePlanV2`/`PlanStep` semantics. Prefer `backend/app/planner/planner_hierarchy.py` unless a `chat/contracts` boundary is justified. Include `DecisionRecord`, specialist report models, `WorkTask`, `WorkBundle`, `PlannerIteration`, and `SpecialistDelegation`; add adapters/tests proving `WorkBundle` cannot bypass `ResourcePlan` policy checks.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_planner_hierarchy_contracts.py app/tests/test_planner_composer_parity.py app/tests/test_planner_executor.py -q`
  - **Depends on:** 0
  - **Evidence:** `pytest … -q → 66 passed`; added `backend/app/planner/planner_hierarchy.py` + `app/tests/test_planner_hierarchy_contracts.py` with `validate_bundle_policy_parity`, `work_bundle_from_resource_plan`, `materialize_resource_plan_from_bundle`, `apply_specialist_reports`

- [x] **2** — Architecture doc (canonical narrative + dry runs)
  - **Do:** Add `docs/architecture/ideal_langgraph_resource_planner.md` with hierarchy, ownership matrix, existing-surface reconciliation, state-channel policy, governance-node mapping, and dry-run walkthroughs. Include the actual baseline dry-run observations from this review and identify which ones are intended to change.
  - **Verify:** `test -f docs/architecture/ideal_langgraph_resource_planner.md && grep -c 'Resource Planner' docs/architecture/ideal_langgraph_resource_planner.md | awk '$1>=3' && grep -q 'Existing surfaces' docs/architecture/ideal_langgraph_resource_planner.md && grep -q 'State channels' docs/architecture/ideal_langgraph_resource_planner.md && grep -q 'Dry-run baseline' docs/architecture/ideal_langgraph_resource_planner.md`
  - **Depends on:** 1
  - **Evidence:** verify script → `VERIFY_OK`; `grep -c 'Resource Planner'` → 8; doc at `docs/architecture/ideal_langgraph_resource_planner.md`

- [x] **3** — Specialist registry (derived from existing registries, no parallel authority)
  - **Do:** Add a specialist registry/loader with ids `skill`, `mcp`, `knowledge`, `spl`, but derive or validate every referenced skill/resource id against `backend/app/skills/catalog.json` and `backend/app/planner/resource_registry_v1.json`. Ownership must be disjoint: Skill chooses route/catalogue tier; MCP plans discovery/search hops only; Knowledge owns ATLAS/CVE/MITRE/RAG; SPL owns candidate SPL composition/validation inputs only.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_specialist_registry.py app/tests/test_runtime_skill_catalog_stage3l_s1.py app/tests/test_planner_resource_registry.py -q`
  - **Depends on:** 1
  - **Evidence:** `pytest … -q → 21 passed`; added `specialist_registry.json`, `specialist_registry.py`, `test_specialist_registry.py` with disjoint ownership + catalog/registry crosswalk validation

- [x] **4** — DecisionRecord emission helper
  - **Do:** Add `backend/app/chat/decision_record.py` with `emit_decision_record(state, record)` appending to `decision_log`; declare `decision_log` on `ChatPipelineState`; redact unsafe payload fields; require `decision_reason`, `authority`, `node`, `inputs_ref`, and `outputs_ref`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_decision_record.py app/tests/test_state_channel_parity.py -q`
  - **Depends on:** 1
  - **Evidence:** `pytest … -q → 14 passed`; added `decision_record.py`, `decision_log` on `ChatPipelineState`, graph retention test in `test_state_channel_parity.py`

- [x] **5** — Unified catalogue schema stub (adapter over 105 + use cases)
  - **Do:** Add `backend/app/catalogue/entries.schema.json` + `match_tiers.py` documenting T0–T4 as an adapter layer over existing `use_cases/catalog.json`, `coverage/cisco_question_runtime_map_v1.json`, SPL templates, and runtime skill catalog. No live router swap yet. Include typo/alias/fuzzy tier cases, especially failed-login variants.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_catalogue_match_tiers.py app/tests/test_in_catalogue_contract_guard.py app/tests/test_out_of_catalogue_scorecard.py -q`
  - **Depends on:** 2
  - **Evidence:** `pytest … -q → 27 passed`; added `catalogue/entries.schema.json`, `catalogue/match_tiers.py`, T3 fuzzy alias binds typo failed-login probe

- [x] **6** — LangGraph RP topology skeleton (test-only, governance nodes explicit)
  - **Do:** Add or promote `backend/app/graph/resource_planner_graph.py` as a callable/test-only graph. Do not add a new env flag and do not wire `/chat` to it. The compiled topology must include RP, specialist delegation/fan-in, code-worker adapters, and explicit governance nodes/adapters for SPL validation, MCP execution gate, HIL/policy veto, context sufficiency, decide facts, answer guard, final-answer validation, and finalize.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_langgraph_shadow_phase12.py app/tests/test_state_channel_parity.py -q`
  - **Depends on:** 3, 4
  - **Evidence:** `pytest … -q → 26 passed`; added `resource_planner_graph.py` + skeleton tests; all 9 governance nodes in compiled topology; `finalize` is skeleton adapter (full compose deferred)

- [x] **7** — Dry-run scenario contract tests
  - **Do:** Add tests for the three design dry runs and one typo catalogue case. Assert route/resource decisions, no MCP for knowledge/guided OT, candidate-only SPL behavior, decision log presence, governance-node visitation, and imperative/shadow step-status parity where relevant.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_dry_runs.py app/tests/test_langgraph_shadow_phase12.py app/tests/test_langgraph_chat_parity_p1.py -q`
  - **Depends on:** 6
  - **Evidence:** `pytest … -q → 21 passed`; `test_resource_planner_dry_runs.py` covers AML/OT/typo probes + decision_log + RAG step parity; shadow fix routes guided `needs_rag` through rag pipeline + `annotate_step_statuses` in finalize

- [x] **8** — Parity + governance regression (pre-route-wiring gate)
  - **Do:** Document parity probe list; prove all existing flags default-off behavior unchanged; run governance regression unchanged.
  - **Verify:** `./scripts/run_stage3_governance_regression.sh` exits 0
  - **Depends on:** 7
  - **Evidence:** `./scripts/run_stage3_governance_regression.sh` exit 0 (~305s); parity probe table added to `docs/architecture/ideal_langgraph_resource_planner.md` §10; `test_resource_planner_graph_skeleton.py::test_resource_planner_graph_requires_no_new_env_flag` green

- [x] **9** — Decision gate: cutover proposal (partial approval — route wire deferred to item 13)
  - **Do:** Only after item 8 is green, write a short cutover proposal with parity results, residual gaps, rollback plan, and whether to reuse `LANGGRAPH_ORCHESTRATION_ENABLED` or request an approved new flag.
  - **Verify:** User explicitly approves the cutover proposal before `/chat` route wiring or imperative retirement begins.
  - **Depends on:** 8
  - **Evidence:** Partial approval 2026-07-23 (loop-asap turn 2): reuse `LANGGRAPH_ORCHESTRATION_ENABLED`; no new flag; imperative default; no route wire until items 10–12 green. Full route-wiring approval + implementation completed in item 13.

- [x] **10** — Harden RP graph finalize + dispatch chain (prep, no route wire)
  - **Do:** Replace skeleton finalize with real `graph_node_context_finalize`; add route setup (`shadow_enrichment`), conditional dispatch (`rag_only` / `composed_dispatch` / `workflow_spl`), and full governance chain ordering through `policy_veto`; expose `resource_planner_graph_response()`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_dry_runs.py::test_resource_planner_graph_produces_response -q`
  - **Depends on:** 9
  - **Evidence:** `pytest … -q → 7 passed`; `resource_planner_graph.py` topology `resource_planner_hierarchy`; `rp_node_finalize` calls `graph_node_context_finalize`; `test_resource_planner_graph_produces_response` asserts `knowledge_recall` + `control_plane_trace.decision_log`

- [x] **11** — Wire `decision_log` through live LangGraph + trace surfaces
  - **Do:** Wrap core `chat_workflow` nodes with `wrap_graph_node`; package `decision_log` in `build_control_plane_trace` via `_decision_log_trace` (dict-wrap before `attach_authority_tier`).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_decision_record.py app/tests/test_control_plane_trace.py::test_control_plane_trace_includes_decision_log app/tests/test_control_plane_trace.py::test_langgraph_wrap_emits_decision_log_to_control_plane_trace app/tests/test_state_channel_parity.py -q`
  - **Depends on:** 10
  - **Evidence:** `pytest … -q → 20 passed`; `chat_workflow._core_nodes` wraps all core nodes; `test_langgraph_wrap_emits_decision_log_to_control_plane_trace` green

- [x] **12** — Parity + governance regression (post-prep gate)
  - **Do:** Re-run item 7–8 verify suites and governance regression after items 10–11; confirm default-off flags unchanged.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_dry_runs.py app/tests/test_langgraph_chat_parity_p1.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 11
  - **Evidence:** `pytest … -q → 9 passed`; `./scripts/run_stage3_governance_regression.sh` exit 0 (~316s); `stage3_governance_regression: PASS`

- [x] **13** — Narrow route-wiring proposal + `/chat` cutover (toggle-only)
  - **Do:** Document preconditions; wire `/chat` and `/chat/stream` to `run_chat_via_resource_planner_graph` when `LANGGRAPH_ORCHESTRATION_ENABLED=true`; keep imperative default when false; add parity tests; no new flag; no imperative retirement; no catalogue router swap.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_langgraph_chat_parity_p1.py -q && ./scripts/run_stage3_governance_regression.sh`; user approves route wiring.
  - **Depends on:** 12
  - **Evidence:** User approval 2026-07-23 (loop-asap turn 4): implement item 13 route wiring only. `pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_langgraph_chat_parity_p1.py -q → 7 passed`; `routes_chat.py` + `routes_chat_stream.py` dispatch to `run_chat_via_resource_planner_graph`; `./scripts/run_stage3_governance_regression.sh` exit 0 (~320s); `stage3_governance_regression: PASS`.

- [x] **14** — RP graph governance trace completeness + policy_veto ordering
  - **Do:** Reorder governance chain so `human_review` → `policy_veto` run before `finalize`; enforce `policy_veto` on `execution`/`human_review`/`spl_validation` pre-compose; emit `validate_final_answer` audit inside `finalize`; sync full `decision_log` into `response.control_plane_trace` via `patch_control_plane_trace_decision_log`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_resource_planner_dry_runs.py app/tests/test_resource_planner_graph_skeleton.py -q && ./scripts/run_stage3_governance_regression.sh`
  - **Depends on:** 13
  - **Evidence:** `pytest app/tests/test_resource_planner_route_wiring.py app/tests/test_resource_planner_dry_runs.py app/tests/test_resource_planner_graph_skeleton.py -q → 18 passed`; probe: 19/19 `decision_log` nodes match on state vs response; `policy_veto` precedes `finalize`; `./scripts/run_stage3_governance_regression.sh` exit 0 (~336s); `stage3_governance_regression: PASS`.

- [x] **15** — Wire `validate_final_answer` graph node + reachability tests + doc honesty
  - **Do:** Wire `finalize → validate_final_answer → END` (remove manual trace stamping); add inbound-edge reachability tests; correct sequential-specialist narrative; refresh stale cutover residual gaps; commit deliverable.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_route_wiring.py -q`
  - **Depends on:** 14
  - **Evidence:** `pytest app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_route_wiring.py -q → 17 passed`; `validate_final_answer` inbound edge from `finalize`; validator invoked via wired node (monkeypatch test); docs/plan updated for sequential specialists + stale gaps removed; committed.

## Dry-run acceptance (design — verified in doc item 2)

| Query | Expected path |
|-------|----------------|
| `What is AML.T0043?` | Skill=knowledge_recall; Knowledge reference∥rag; no MCP |
| OT outbound hunt | Skill=guided_investigation; Knowledge grounding; MCP idle |
| Fuzzy failed-login catalogue | Skill=spl_generation; SPL+MCP specialists; gate may veto search |

## Dry-run baseline from review

Command:

```bash
cd backend && PYTHONPATH=../backend:.. python3 - <<'PY'
# ran build_live_chat_response + planner-led shadow graph for the three design probes
PY
```

Observed:

| Query | Current imperative/shadow behavior | Gap to close |
|-------|------------------------------------|--------------|
| `What is AML.T0043?` | `knowledge_recall`, `rag_only`, no SPL/MCP, execution skipped, HIL false | Good baseline; preserve. |
| OT outbound hunt | `guided_investigation`, no candidate SPL/MCP, execution skipped. ~~Shadow and imperative differ on RAG step status (`not_run` vs `skipped_unavailable`).~~ **Fixed 2026-07-23** — parity test green after shadow routes guided `needs_rag` through rag pipeline + `annotate_step_statuses`. | Closed in item 7. |
| `failed lgon spike top users last hour` | Under the dry-run CP/sentinel harness: `spl_generation`, no live-router use-case match or template id, fallback/lab-only draft SPL, `spl_validation.approved=false`, MCP blocked. Plain local defaults can route differently. Catalogue adapter (T3) binds typo via alias tier in tests only. | Live router swap deferred to post–item 9 work; RP graph typo parity covered in dry-run tests. |

## Drift log

| Date | Note |
|------|------|
| 2026-07-23 | Plan promoted from `/root/.cursor/plans/prod_readiness_gaps_e45fd6bb.plan.md`. Removed duplicate flat-orchestrator spine from canonical plan; Skill Specialist owns skill/catalogue (RP delegates only). |
| 2026-07-23 | Review hardening: added existing-surface reconciliation, no-new-flag constraint, governance-node topology requirement, DecisionRecord state-channel gate, dry-run scenario tests, fuzzy catalogue test, and explicit cutover decision gate. |
| 2026-07-23 | Item 14: fixed RP governance ordering (`policy_veto` before `finalize`), trace sync (`decision_log` parity on returned response), strengthened route-wiring tests. |

## User directives

- Hierarchical specialists under Resource Planner; no overlapping task ownership.
- Keep all governance and observability nodes; log `decision_reason` every hop.
- LLM plans; code executes; not fully deterministic routing.
- One LangGraph end-state; retire imperative only after parity and explicit cutover approval (item 9+ future work).

## Cutover proposal (item 9 — partial approval; route wire deferred)

**User approval (2026-07-23, partial):**

- Reuse existing `LANGGRAPH_ORCHESTRATION_ENABLED` for eventual `/chat` cutover to the RP hierarchy graph.
- Do **not** add `AI_SOC_RESOURCE_PLANNER_GRAPH_ENABLED` or any new env flag.
- Imperative path remains default (`LANGGRAPH_ORCHESTRATION_ENABLED=false`).
- Imperative retirement is **out of scope** until a later explicit gate.
- **No `/chat` route wiring** until items 10–12 are green (satisfied in item 13).

| Area | Status | Notes |
|------|--------|-------|
| Hierarchy contracts + WorkBundle policy | Green | `test_planner_hierarchy_contracts.py` |
| Specialist registry | Green | Derived from skill/resource catalogs |
| `decision_log` channel | Green | `emit_decision_record`; LangGraph retention + live `wrap_graph_node` on core nodes |
| Catalogue T0–T4 adapter | Green | Typo `lgon` → T3 fuzzy bind (adapter only; live router unchanged) |
| RP graph (test-only) | Green | Real finalize + governance chain; `resource_planner_graph_response()` |
| Dry-run probes | Green | AML / OT / typo contracts + RP typo parity + imperative↔shadow RAG step parity |
| Governance regression (item 8) | Green | `./scripts/run_stage3_governance_regression.sh` exit 0 |
| Post-prep regression (item 12) | Green | `./scripts/run_stage3_governance_regression.sh` exit 0 (~316s) |

**Residual gaps (post item 14):**

1. Specialist fan-out is sequential in RP graph; true parallel LangGraph `Send` API deferred.
2. Unified catalogue adapter not wired into `understand_query` / live router.
3. Specialist report proposals are not merged by `rp_node_resource_planner_merge` yet; `apply_specialist_reports()` is contract-only until wired.
4. Imperative path retirement remains a separate explicit decision gate.

**Rollback:** Keep imperative path as default (`LANGGRAPH_ORCHESTRATION_ENABLED=false`). Toggle off restores current behavior without code revert.

## Narrow route-wiring proposal (item 13 — approved + implemented)

**Status:** Implemented 2026-07-23. Toggle-only cutover active when `LANGGRAPH_ORCHESTRATION_ENABLED=true`.

**Scope:** Toggle-only cutover of `/chat` LangGraph runner from linear `chat_workflow` to `resource_planner_graph` when `LANGGRAPH_ORCHESTRATION_ENABLED=true`. No imperative retirement in this phase.

**Preconditions (all met):**

| Gate | Status |
|------|--------|
| Items 10–12 green | Yes |
| RP graph produces real `PlaceholderResponse` | Yes (`test_resource_planner_graph_produces_response`) |
| `decision_log` on live LangGraph + trace | Yes (`wrap_graph_node` + `control_plane_trace.decision_log`) |
| Governance regression | PASS (item 12) |
| P1 parity unchanged | Yes (`test_langgraph_chat_parity_p1.py` green) |
| No new env flag | Yes |

**Proposed implementation (after approval only):**

1. In `app/api/routes_chat.py` (or existing LangGraph dispatch seam), when `LANGGRAPH_ORCHESTRATION_ENABLED=true`, invoke `run_resource_planner_graph` + `resource_planner_graph_response` instead of `run_chat_via_langgraph`.
2. Keep imperative `build_live_chat_response` as default when flag is false (unchanged).
3. Add parity test: RP graph vs linear LangGraph on sentinel subset when flag on.
4. Re-run `./scripts/run_stage3_governance_regression.sh` before merge.

**Explicitly out of scope:**

- Imperative path removal
- New env flags
- Live catalogue router swap (T0–T4 adapter stays test-only)
- Parallel specialist `Send` API

**Rollback:** Set `LANGGRAPH_ORCHESTRATION_ENABLED=false` and restart backend — zero code revert required.

**Decision:** Approved loop-asap turn 4 — route wiring implemented; imperative retirement and catalogue router swap remain out of scope.
