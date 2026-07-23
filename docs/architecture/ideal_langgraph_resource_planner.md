# Ideal LangGraph — Resource Planner hierarchy

Canonical plan: `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md`.

This document is the architecture narrative for the hierarchical LangGraph under the
**Resource Planner** apex. Specialists propose; code workers execute; governance nodes
veto unsafe actions. `/chat` can run this topology when `LANGGRAPH_ORCHESTRATION_ENABLED=true`
(item 13); the imperative path remains default when the flag is false.

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
| RP hierarchy graph | `backend/app/graph/resource_planner_graph.py` | Callable always; `/chat` + `/chat/stream` when `LANGGRAPH_ORCHESTRATION_ENABLED=true` |
| Hierarchy contracts | `backend/app/planner/planner_hierarchy.py` | Specialist / bundle / iteration models |
| Catalogue adapter | `backend/app/catalogue/match_tiers.py` | T0–T4 tier tests only; live router unchanged |

**Cutover status (items 9–15, 2026-07-23):**

| Area | Status |
|------|--------|
| `/chat` route wiring | **Done** — toggle via `LANGGRAPH_ORCHESTRATION_ENABLED` (no new flag) |
| Imperative default | **Preserved** — flag off → `build_live_chat_response` |
| Imperative retirement | **Out of scope** — separate explicit gate |
| Live catalogue router swap | **Out of scope** — T0–T4 adapter is test/adapter only |
| New env flags | **Not added** — `AI_SOC_RESOURCE_PLANNER_GRAPH_ENABLED` rejected by design |

Shadow enrichment still uses `AI_SOC_LANGGRAPH_SHADOW_ENABLED` for planner-led shadow runs.

---

## 4. State channels

LangGraph silently drops undeclared keys. Any new top-level channel must be declared on
`ChatPipelineState` and covered by `app/tests/test_state_channel_parity.py`.

| Channel | Status | Notes |
|---------|--------|-------|
| `evidence_plan.resource_plan` | **exists** | Composed `ResourcePlan` wire contract |
| `planning_decision` | **exists** | CP-off planning path summary |
| `decision_log` | **exists (item 4)** | On `ChatPipelineState`; `emit_decision_record()`; synced to `control_plane_trace` |
| `planner_iteration` | **RP graph only** | `ResourcePlannerGraphState`; snapshot per RP loop |
| `work_bundle` | **RP graph only** | Scheduling view from `work_bundle_from_resource_plan()`; must not replace `resource_plan` |
| `specialist_reports` / `specialist_delegations` | **RP graph only** | Advisory fan-in envelope; not on base `ChatPipelineState` |
| `rp_graph_trace` | **RP graph only** | Visited-node audit for topology tests |

Policy: `decision_log` appends only via `backend/app/chat/decision_record.py`. Redact
secrets and raw prompts in `inputs_ref` / `outputs_ref`. Specialists write reports into
RP graph state; only code workers mutate execution envelopes. LangGraph retention for
`decision_log` is covered by `app/tests/test_state_channel_parity.py`.

---

## 5. Governance node mapping

The RP graph skeleton (item 6) must include explicit nodes or documented adapters to
current pipeline functions. These nodes are **never optional** on any route that could
reach `/chat`:

| Governance concern | Current node / function | RP graph role |
|--------------------|-------------------------|---------------|
| SPL validation | `spl_validate` / validator gate | Pre-MCP mandatory gate; enforces `execution_eligible=false` on unapproved SPL |
| MCP execution gate | `evaluate_mcp_execution` via `graph_node_execution` | Code worker + gate |
| Context sufficiency | context sufficiency gate (in `finalize`) | **Trace node** pre-finalize; response + `control_plane_trace.sufficiency` authority in `graph_node_context_finalize`; finalized value is synced back into graph state before return. |
| Decide facts | severity+MITRE policy (in `finalize`) | **Trace node**; response authority applied at `finalize` |
| Answer guard | `answer_guard` (lab; default off) | **Trace node**; response/prose guard when enabled |
| Human review | `human_review` / HIL | HIL surface before composition |
| Policy veto | `_apply_policy_veto` + evidence_plan blocks | Runs **before** `finalize`; blocks MCP/SPL when policy disallows |
| Finalize | `graph_node_context_finalize` | Real compose path; severity/MITRE/sufficiency land here |
| Final answer validation | `validate_final_answer` | Wired graph node **after** `finalize` (item 15) |

Chain order in `resource_planner_graph.py`: `… → human_review → policy_veto → finalize → validate_final_answer → END`.

A graph that compiles but skips these nodes is **not** migration evidence. Trace-only
governance nodes still record `DecisionRecord` hops for observability even when authority
is deferred to `finalize`.

---

## 6. Dry-run baseline

Design probes (verified 2026-07-23; imperative + selected RP graph + shadow where noted):

| Query | Observed behavior | Status |
|-------|-------------------|--------|
| `What is AML.T0043?` | `knowledge_recall`, `rag_only`, no SPL/MCP, execution `skipped` | **Green** — imperative and RP graph match |
| OT outbound hunt | `guided_investigation`, no candidate SPL/MCP, execution `skipped`; imperative↔shadow RAG step status parity | **Green** — fixed item 7 |
| `failed lgon spike top users last hour` | Under the dry-run CP/sentinel harness: `spl_generation`, no live-router `use_case_id` / template id, fallback or lab-only draft SPL, `spl_validation.approved=false`, execution `requires_human_review`. Plain local defaults can route differently (for example `attack_discovery`), so this is a harness-scoped observation. | **Green** on guarded execution; adapter vs router gap below |

**Adapter vs live router (typo probe):** `match_catalogue_tier()` binds T3 →
`auth_failed_login_spike` with `alias_applied=true`, but the dry-run live router does not
yet consume that bind (`use_case_id` absent from `evidence_plan`, no template id on the
returned response). SPL output therefore comes from fallback / lab-only draft paths, not
from the adapter-selected catalogue row. Wiring the adapter into `understand_query`
remains a follow-up.

Reproduce:

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_dry_runs.py -q
```

### 6.1 Walkthrough: `What is AML.T0043?`

1. **Bootstrap** — query understanding, intent → `knowledge_recall`.
2. **Resource Planner** — composer emits RAG-only `ResourcePlan` (no SPL/MCP steps).
3. **Skill specialist** — logs advisory route; `catalogue_tier` is stubbed (`adapter`) until live tier bind.
4. **Knowledge specialist** — trace-only in v1 (RAG driven by composer + `graph_node_rag_early`).
5. **MCP / SPL specialists** — SPL logs `template_or_fallback`; MCP trace-only when idle.
6. **RP merge** — `WorkBundle` from `work_bundle_from_resource_plan()`; `apply_specialist_reports()` is implemented and unit-tested but not called by `rp_node_resource_planner_merge` yet.
7. **Code workers** — `prepare_rag_only` → `rag_early`; no execution stage.
8. **Governance** — full chain through `policy_veto` → `finalize` → `validate_final_answer`.
9. **Decision log** — 19 hops on this probe; synced to `control_plane_trace.decision_log`.

### 6.2 Walkthrough: OT outbound hunt

1. **Skill specialist** — `guided_investigation`, hybrid evidence plan.
2. **Knowledge specialist** — grounding / evidence-summary floor proposals.
3. **MCP specialist** — idle (discovery allowed but execution off by policy).
4. **SPL specialist** — idle or review-only SPL inputs only.
5. **Parity** — RAG step status matches imperative vs shadow (`test_imperative_shadow_rag_step_status_parity_for_ot_probe`).

### 6.3 Walkthrough: fuzzy failed-login catalogue

1. **Skill specialist** — under the dry-run harness, `spl_generation`; adapter separately binds T3 → `auth_failed_login_spike` (test/adapter only).
2. **SPL specialist** — fallback / lab-only draft candidate path; `execution_eligible=false` preserved.
3. **MCP specialist** — search hop in plan; blocked when SPL unapproved + HIL required.
4. **Gates** — `spl_validation.approved=false`; execution `requires_human_review`.
5. **Follow-up** — wire adapter bind into live router so `evidence_plan` carries `use_case_id`.

---

## 7. Resource Planner responsibilities (summary)

The **Resource Planner** is the apex orchestrator:

- Fan out `SpecialistDelegation` envelopes with lane-scoped `ownership_scope`.
- Fan in `SpecialistReport` proposals; **v1 merge** builds `WorkBundle` from
  `work_bundle_from_resource_plan()` only. `apply_specialist_reports()` is implemented
  and unit-tested but **not yet called** from `rp_node_resource_planner_merge` — specialist
  lanes are trace/audit scaffolding until a follow-up wires proposal merge.
- Treat finalized sufficiency/facts/guard outputs as response and control-plane-trace
  authority. The finalized `context_sufficiency` is synced back into graph state
  before return so graph consumers do not see the pre-finalize placeholder.
- Never invent steps outside the composed `ResourcePlan`.
- Schedule code-worker dispatch through the existing executor hooks.
- Loop while iteration budget allows; emit `DecisionRecord` each hop.
- Hand off to `decide_facts` — specialists do not set severity, MITRE status, or
  `execution_eligible`.

---

## 8. Migration sequence (plan items)

| Item | Deliverable | Status |
|------|-------------|--------|
| 1 | Hierarchy contracts (`planner_hierarchy.py`) | Done |
| 2 | This architecture doc | Done |
| 3 | Specialist registry derived from existing catalogs | Done |
| 4 | `decision_log` state channel + `emit_decision_record()` | Done |
| 5 | Unified catalogue adapter (T0–T4) | Done (adapter only) |
| 6 | RP graph skeleton (governance nodes explicit) | Done |
| 7 | Dry-run scenario contract tests | Done |
| 8 | Parity + governance regression | Done |
| 9 | Cutover proposal (user approval) | Done (partial → full in 13) |
| 10 | Harden finalize + dispatch chain | Done |
| 11 | `decision_log` through live LangGraph + trace | Done |
| 12 | Post-prep parity + governance regression | Done |
| 13 | `/chat` route wiring (`LANGGRAPH_ORCHESTRATION_ENABLED`) | Done |
| 14 | Governance trace completeness + `policy_veto` ordering | Done |
| 15 | `validate_final_answer` graph node + reachability | Done |

**Residual follow-ups (not in plan scope):** parallel specialist `Send` fan-out; wire
`apply_specialist_reports()` in merge; wire catalogue adapter into live router; imperative
retirement gate.

---

## 9. References

- Plan: `plans/2026-07-23_1305_ideal-langgraph-resource-planner.md`
- Composer parity: `app/tests/test_planner_composer_parity.py`
- Hierarchy contracts: `app/tests/test_planner_hierarchy_contracts.py`
- Shadow graph: `app/graph/planner_led_shadow_graph.py`
- RP skeleton graph: `app/graph/resource_planner_graph.py`
- Pipeline state spec: `docs/architecture/chat_pipeline_state_v2_and_node_trace.md`

## 10. Parity probe list (items 8 + 12 gate)

Probes for scaffold, post-prep, and route-wiring gates (default-off flags unchanged unless noted):

| Probe | Command / test | Pass criteria |
|-------|----------------|---------------|
| Hierarchy contracts | `pytest app/tests/test_planner_hierarchy_contracts.py` | WorkBundle cannot bypass ResourcePlan policy |
| Specialist registry crosswalk | `pytest app/tests/test_specialist_registry.py` | Disjoint lanes; catalog/registry validation |
| Decision log channel | `pytest app/tests/test_decision_record.py app/tests/test_state_channel_parity.py` | `decision_log` declared + LangGraph retention |
| Catalogue T0–T4 adapter | `pytest app/tests/test_catalogue_match_tiers.py` | AML T0, typo T3 fuzzy bind |
| RP graph skeleton | `pytest app/tests/test_resource_planner_graph_skeleton.py` | Governance nodes explicit; no new env flag |
| Design dry runs | `pytest app/tests/test_resource_planner_dry_runs.py` | AML / OT / typo contracts, RP typo parity, sufficiency state sync, and RAG step parity |
| Planner-led shadow | `pytest app/tests/test_langgraph_shadow_phase12.py` | Fan-out/fan-in parity unchanged |
| LangGraph P1 parity | `pytest app/tests/test_langgraph_chat_parity_p1.py` | `LANGGRAPH_ORCHESTRATION_ENABLED` off path unchanged |
| Governance regression | `./scripts/run_stage3_governance_regression.sh` | 0 pytest failures, harness 6/6 |

**Default-off invariants preserved:** no `AI_SOC_RESOURCE_PLANNER_GRAPH_ENABLED`; `/chat` imperative when `LANGGRAPH_ORCHESTRATION_ENABLED=false`; when true, `/chat` runs `run_chat_via_resource_planner_graph` (RP hierarchy).
