# Ideal LangGraph — Resource Planner hierarchy

Canonical plan: `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md`.

This document is the architecture narrative for the hierarchical LangGraph under the
**Resource Planner** apex. Specialists propose; code workers execute; governance nodes
veto unsafe actions. The design replaces dual imperative/LangGraph runners with one
graph topology once parity gates pass (item 9 decision gate).

---

## 1. Topology

```
bootstrap (code)
  → Resource Planner (delegate / merge / schedule only)
      → specialists (sequential): Skill → Knowledge → MCP → SPL
      → RP merge → WorkBundle → code workers
      → governance gates (SPL validate, MCP gate, HIL, policy veto, …)
      → RP loop (optional iteration)
  → decide_facts → compose → answer_guard → policy_veto → finalize → validate_final_answer + trace
```

Specialists have **disjoint ownership** but v1 executes them **serially** in the compiled graph; LangGraph `Send` parallel fan-out is deferred.

The **Resource Planner** never owns catalogue matching, SPL composition, MCP hop
selection, or reference lookup. It delegates to specialists with disjoint ownership,
merges advisory reports into a `WorkBundle`, and schedules code-worker dispatch from
the authoritative `ResourcePlan`.

Contracts live in `backend/app/planner/planner_hierarchy.py`:

| Model | Role |
|-------|------|
| `SpecialistDelegation` | RP → specialist fan-out envelope |
| `SpecialistReport` (+ domain variants) | Advisory proposals per lane |
| `WorkTask` / `WorkBundle` | Scheduling view over `ResourcePlan` steps |
| `PlannerIteration` | One RP loop with delegations, reports, bundle |
| `DecisionRecord` | Per-hop audit (`decision_reason`, `authority`, refs) |

`validate_bundle_policy_parity()` enforces that `WorkBundle` cannot remove
`policy_checks`, relax `blocked_policy`, or add unauthorized steps relative to the
composed `ResourcePlan`.

---

## 2. Ownership matrix

| Lane | Specialist id | Owns | Must not own |
|------|---------------|------|--------------|
| Skill | `skill` | Route, catalogue tier, `skill_id`, `use_case_id` | SPL text, MCP tool args, reference facts |
| Knowledge | `knowledge` | ATLAS, CVE, MITRE, RAG, reference lookup | MCP search hops, SPL composition |
| MCP | `mcp` | Discovery/search hop planning, tool selection prefs | Route/skill, SPL candidate, severity/MITRE authority |
| SPL | `spl` | Candidate SPL composition inputs, validation inputs | MCP execution, final `execution_eligible` |
| Resource Planner | _(apex)_ | Delegate, merge, schedule, iterate | Any specialist-owned proposal authority |

Specialists are **advisory** (`authority: advisory | proposed_validated`). Deterministic
code and governance nodes remain authoritative for `execution_eligible`, severity, MITRE
status, and MCP gate outcomes.

---

## 3. Existing surfaces (reconciliation)

The hierarchy **extends** existing planner surfaces; it does not fork parallel truth.

| Surface | Path | Hierarchy relationship |
|---------|------|------------------------|
| `ResourcePlan` / `PlanStep` | `backend/app/planner/resource_plan.py` | Policy authority; `WorkBundle.source_plan` |
| `ResourcePlanV2` / `PlanStepV2` | same module | Future multi-call scheduler; not wired to RP graph yet |
| Composer | `backend/app/planner/composer.py` | EvidencePlan → `ResourcePlan`; feeds RP input |
| Executor | `backend/app/planner/executor.py` | Code-worker dispatch from composed steps |
| Resource registry | `backend/app/planner/resource_registry_v1.json` | Step `resource_id` binding (item 3 validates) |
| Skill catalog | `backend/app/skills/catalog.json` | Skill specialist lane (item 3) |
| Use-case catalog | `backend/app/use_cases/catalog.json` | Catalogue tier adapter (item 5) |
| Planner-led shadow | `backend/app/graph/planner_led_shadow_graph.py` | Parity reference topology pre-RP-graph |
| Hierarchy contracts | `backend/app/planner/planner_hierarchy.py` | Specialist / bundle / iteration models |

**Non-goals in this plan slice:** new env flags for RP graph cutover; `/chat` route
wiring; imperative retirement. Shadow uses `AI_SOC_LANGGRAPH_SHADOW_ENABLED`; eventual
cutover reuses `LANGGRAPH_ORCHESTRATION_ENABLED` after item 9 approval.

---

## 4. State channels

LangGraph silently drops undeclared keys. Any new top-level channel must be declared on
`ChatPipelineState` and covered by `app/tests/test_state_channel_parity.py`.

| Channel | Status | Notes |
|---------|--------|-------|
| `evidence_plan.resource_plan` | **exists** | Composed `ResourcePlan` wire contract |
| `planning_decision` | **exists** | CP-off planning path summary |
| `decision_log` | **planned (item 4)** | `DecisionRecord` list; `emit_decision_record()` |
| `planner_iteration` | **future** | Optional `PlannerIteration` snapshot per RP loop |
| `work_bundle` | **future** | Optional scheduling view; must not replace `resource_plan` |

Policy: `decision_log` appends only via `backend/app/chat/decision_record.py` (item 4).
Redact secrets and raw prompts in `inputs_ref` / `outputs_ref`. Specialists write
reports into iteration state; only code workers mutate execution envelopes.

---

## 5. Governance node mapping

The RP graph skeleton (item 6) must include explicit nodes or documented adapters to
current pipeline functions. These nodes are **never optional** on any route that could
reach `/chat`:

| Governance concern | Current node / function | RP graph role |
|--------------------|-------------------------|---------------|
| SPL validation | `spl_validate` / validator gate | Pre-MCP mandatory gate |
| MCP execution gate | `evaluate_mcp_execution` via `graph_node_execution` | Code worker + gate |
| Context sufficiency | context sufficiency gate | Pre-synthesis classify |
| Decide facts | `decide_facts` / severity+MITRE policy | Post-evidence authority |
| Answer guard | `answer_guard` (lab; default off) | Prose guard when enabled |
| Final answer validation | `validate_final_answer` | Pre-finalize |
| Human review | `human_review` / HIL | Per-call confirmation |
| Policy veto | skill contract + evidence_plan blocks | Composition-time + gate |

A stub graph that compiles but skips these nodes is **not** migration evidence.

---

## 6. Dry-run baseline

Design probes from plan review (imperative + planner-led shadow, 2026-07-23):

| Query | Observed behavior | Intended change |
|-------|-------------------|-----------------|
| `What is AML.T0043?` | `knowledge_recall`, `rag_only`, no SPL/MCP, execution skipped, HIL false | **Preserve** — Knowledge specialist + no MCP |
| OT outbound hunt | `guided_investigation`, no candidate SPL/MCP, execution skipped; shadow vs imperative differ on RAG step status (`not_run` vs `skipped_unavailable`) | **Fix parity** before shadow topology promotion (item 7) |
| `failed lgon spike top users last hour` | `spl_generation`, no use-case match, fallback candidate SPL, `spl_validation.approved=false`, MCP blocked by policy/HIL | **Decide fuzzy tier** — alias/typo should bind `auth_failed_login_spike` or document explicit non-bind (item 5) |

### 6.1 Walkthrough: `What is AML.T0043?`

1. **Bootstrap** — query understanding, intent → `knowledge_recall`.
2. **Resource Planner** — composer emits RAG-only `ResourcePlan` (no SPL/MCP steps).
3. **Skill specialist** — confirms route + catalogue tier T0 reference.
4. **Knowledge specialist** — proposes `knowledge_retrieval` + reference finalize inputs.
5. **MCP / SPL specialists** — idle (no proposals).
6. **RP merge** — `WorkBundle` mirrors plan; `validate_bundle_policy_parity` passes.
7. **Code workers** — RAG early, reference finalize; no execution stage.
8. **Governance** — context sufficiency → decide_facts → finalize.
9. **Decision log** — each hop records `decision_reason` (item 4).

### 6.2 Walkthrough: OT outbound hunt

1. **Skill specialist** — `guided_investigation`, hybrid evidence plan.
2. **Knowledge specialist** — grounding / evidence-summary floor proposals.
3. **MCP specialist** — idle (discovery allowed but execution off by policy).
4. **SPL specialist** — idle or review-only SPL inputs only.
5. **Gap** — RAG step status must match imperative vs shadow (`item 7` assertion).

### 6.3 Walkthrough: fuzzy failed-login catalogue

1. **Skill specialist** — `spl_generation`; catalogue tier T2/T3 fuzzy match TBD.
2. **SPL specialist** — template or fallback candidate; `execution_eligible_false` preserved.
3. **MCP specialist** — search hop planned but blocked when `mcp_allowed=false`.
4. **Gates** — SPL validator rejects or leaves `approved=false`; MCP gate + HIL block search.
5. **Gap** — typo `lgon` → `auth_failed_login_spike` binding is an open catalogue decision.

---

## 7. Resource Planner responsibilities (summary)

The **Resource Planner** is the apex orchestrator:

- Fan out `SpecialistDelegation` envelopes with lane-scoped `ownership_scope`.
- Fan in `SpecialistReport` proposals; merge via `apply_specialist_reports()` without
  policy mutation.
- Build `WorkBundle` from `work_bundle_from_resource_plan()`; never invent steps outside
  the composed plan.
- Schedule code-worker dispatch through the existing executor hooks.
- Loop while iteration budget allows; emit `DecisionRecord` each hop.
- Hand off to `decide_facts` — specialists do not set severity, MITRE status, or
  `execution_eligible`.

---

## 8. Migration sequence (plan items)

| Item | Deliverable |
|------|-------------|
| 1 | Hierarchy contracts (`planner_hierarchy.py`) |
| 2 | This architecture doc |
| 3 | Specialist registry derived from existing catalogs |
| 4 | `decision_log` state channel + `emit_decision_record()` |
| 5 | Unified catalogue adapter (T0–T4) |
| 6 | RP graph skeleton (test-only, governance nodes explicit) |
| 7 | Dry-run scenario contract tests |
| 8 | Parity + governance regression |
| 9 | Cutover proposal (user approval required) |

---

## 9. References

- Plan: `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md`
- Composer parity: `app/tests/test_planner_composer_parity.py`
- Hierarchy contracts: `app/tests/test_planner_hierarchy_contracts.py`
- Shadow graph: `app/graph/planner_led_shadow_graph.py`
- RP skeleton graph: `app/graph/resource_planner_graph.py`
- Pipeline state spec: `docs/architecture/chat_pipeline_state_v2_and_node_trace.md`

## 10. Parity probe list (item 8 gate)

Pre-route-wiring probes (all default-off flags unchanged unless noted):

| Probe | Command / test | Pass criteria |
|-------|----------------|---------------|
| Hierarchy contracts | `pytest app/tests/test_planner_hierarchy_contracts.py` | WorkBundle cannot bypass ResourcePlan policy |
| Specialist registry crosswalk | `pytest app/tests/test_specialist_registry.py` | Disjoint lanes; catalog/registry validation |
| Decision log channel | `pytest app/tests/test_decision_record.py app/tests/test_state_channel_parity.py` | `decision_log` declared + LangGraph retention |
| Catalogue T0–T4 adapter | `pytest app/tests/test_catalogue_match_tiers.py` | AML T0, typo T3 fuzzy bind |
| RP graph skeleton | `pytest app/tests/test_resource_planner_graph_skeleton.py` | Governance nodes explicit; no new env flag |
| Design dry runs | `pytest app/tests/test_resource_planner_dry_runs.py` | AML / OT / typo contracts + RAG step parity |
| Planner-led shadow | `pytest app/tests/test_langgraph_shadow_phase12.py` | Fan-out/fan-in parity unchanged |
| LangGraph P1 parity | `pytest app/tests/test_langgraph_chat_parity_p1.py` | `LANGGRAPH_ORCHESTRATION_ENABLED` off path unchanged |
| Governance regression | `./scripts/run_stage3_governance_regression.sh` | 0 pytest failures, harness 6/6 |

**Default-off invariants preserved:** no `AI_SOC_RESOURCE_PLANNER_GRAPH_ENABLED`; `/chat` imperative when `LANGGRAPH_ORCHESTRATION_ENABLED=false`; when true, `/chat` runs `run_chat_via_resource_planner_graph` (RP hierarchy).
