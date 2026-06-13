# Plan — Query→Answer Readiness for Live MCP + LLM

**Status:** Implementation-ready for bounded multi-call orchestration; live activation remains COE-gated
**Date:** 2026-05-30 (audited 2026-06-13; updated 2026-06-13)  
**Commits:** `567fe62`, `ae88760`, orchestration Phase 1 composer
**Author:** COE review (Anurag + Claude)  
**Related:** [`contracts/splunk_mcp_connection_contract.md`](../contracts/splunk_mcp_connection_contract.md), [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md), [`/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md`](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) (Phase G/H)
**External sources reconciled (A.17):** Splunk Lantern — [LLM reasoning + ML for Jira alert investigations](https://lantern.splunk.com/Security_Use_Cases/Automation_and_Orchestration/Leveraging_LLM_reasoning_and_ML_capabilities_for_Jira_alert_investigations), [Automating alert investigations with LLMs + Splunk + Confluence](https://lantern.splunk.com/Observability_Use_Cases/Troubleshoot/Automating_alert_investigations_by_integrating_LLMs_with_the_Splunk_platform_and_Confluence)

> **Plan management:** MCP orchestration rules live in **Appendix A** below (formerly a separate `2026-06-13_mcp-execution-orchestration-plan.md`). One file for COE tracking; architecture deep-dives remain in `docs/architecture/spl_mcp_execution_controls.md`.

---

## Audit summary (2026-06-13)

Honest read against current `master` — several plan claims were **stale** when written; some work landed under WS-PRE / Stage 3M / P6 without updating this doc.

| Claim in original plan | Actual state | Verdict |
|------------------------|--------------|---------|
| `routes_chat.py:114` hard-disables synthesis | Live path is `build_live_chat_response()` → `app/chat/pipeline.py`; synthesis runs via `run_governed_synthesis_lab()` when flagged | **Outdated** |
| "No answer sentence is ever composed" | Deterministic analyst draft always built when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true`; optional live narration when `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` | **Outdated** (default flags still off) |
| Phase A1 empty-result bug | Rule 3b in `context_sufficiency.py`; `test_negative_result_sufficiency.py` (T4.1) green | **Done** |
| Phase A2 injection defense | `splunk_result_adapter.sanitize_result_envelope` + `mcp_result_safeguard.scan_mcp_preview_rows` → `prompt_injection_filter`; `test_mcp_result_injection_defense.py` (T4.2) green | **Done** |
| Phase A3 lineage placeholders | `lineage/builder.py` has `llm_raw_output_placeholder`, `adapter_overrides_placeholder`, `guard_overrides_placeholder` | **Done** (placeholders only; not populated on live narration yet) |
| Phase C scaffold "never called" | `build_governed_synthesis_package` + `run_answer_guard_lab` wired in `pipeline.py` | **Done** behind flags |
| `mcp_execution_gate.py:164` blocks real mode | Real block is `_gate_review` at **`:276`** (`registry.mode != "mock"`); `NotImplementedError` catch at **`:155`** if gate is bypassed | **Stale line refs** (updated 2026-06-13) |
| Gate passes only `{"query": normalized_spl}` | **Fixed** — gate uses `splunk_search_tool_arguments()` (`ae88760`) | **Done — B2 scaffold** |
| Phase D route shadow | `_route_plan_shadow_candidate()` in `pipeline.py` still returns `None`; inject via test monkeypatch or `generate_llm_route_plan_candidate` | **Still valid** |

### Implementation-readiness decision (2026-06-13)

The single-call live adapter work is ready to implement after COE confirms the connection contract. The former orchestration design was **not** ready for investigations that require more than one MCP call. Code review confirms five structural gaps:

| Severity | Finding | Code evidence |
|----------|---------|---------------|
| **High** | `PlanStep` has no `depends_on`, call budget, or per-call outcome fields — only one generic `mcp_execution` step is composed | [`resource_plan.py:36`](backend/app/planner/resource_plan.py) `PlanStep`; [`composer.py:313`](backend/app/planner/composer.py) `_mcp_step()` |
| **High** | `execute_plan_dispatch()` is a one-pass parity dispatcher (spl → optional rag → spl_source_resolve → execution); it annotates step status from a singular `execution` and must not own replanning | [`executor.py:62`](backend/app/planner/executor.py), [`executor.py:145`](backend/app/planner/executor.py) `_resolve_status` reads `state["execution"]` |
| **High** | `evaluate_mcp_execution()` performs exactly one `call_tool` and returns one execution dict | [`mcp_execution_gate.py:149`](backend/app/orchestration/mcp_execution_gate.py) |
| **High** | LangGraph omits `graph_node_spl_source_resolve` **and** never uses `execute_plan_dispatch()` — imperative path runs resolve before execution (or via dispatch hooks when a composed plan exists) | [`chat_workflow.py:49`](backend/app/graph/chat_workflow.py) edges; contrast [`pipeline.py:215`](backend/app/chat/pipeline.py) |
| **Medium** | Pipeline state exposes singular `execution`; lineage/evidence aggregation cannot represent multi-call turns without `mcp_orchestration` envelope | [`pipeline.py:521`](backend/app/chat/pipeline.py) `graph_node_execution` |

This revision makes the target explicit:

- `graph_node_evidence_planning` / `compose_resource_plan()` decide that MCP evidence is needed and may select a governed investigation recipe. They do **not** invoke MCP.
- A new deterministic `graph_node_resource_scheduler` selects the next ready plan step from explicit dependencies. An MCP step may therefore run before SPL generation, between searches, or after another evidence step.
- `graph_node_mcp_call_planning` materializes the selected MCP step into a concrete call. Search calls require resolved, approved SPL; metadata/discovery calls use their own deterministic argument validators and may unlock source resolution or another later step.
- `graph_node_mcp_execute_one` executes exactly one approved call through the existing gate.
- `graph_node_mcp_result_assess` records the envelope and produced evidence keys; `graph_node_plan_reconcile` then unlocks the next dependent resource step, selects a declared fallback, requests HIL, or stops.
- The LLM may narrate results or provide a shadow recommendation, but it cannot add a call, choose a tool, write executable SPL, increase a budget, or bypass validation/HIL.

**Plan-ready does not mean production-ready.** Real transport, live schema confirmation, identity/auth, async lifecycle, allowlists, and activation flags remain COE gates.

### Missed cases (add to scope)

1. **`CONTROL_PLANE_ENABLED` vs live narration.** `lab_runner.py` skips live model narration when `control_plane_enabled` is true — even if both synthesis flags are on. `.env.example` defaults `CONTROL_PLANE_ENABLED=true`. COE must define which composer owns narration before enabling live LLM in production posture.
2. **LangGraph path.** `routes_chat.py` can delegate to `run_chat_via_langgraph()` when `langgraph_orchestration_enabled`; parity gap is **confirmed today** — LangGraph skips `spl_source_resolve` and does not use `execute_plan_dispatch`. Multi-call nodes must be added to both runtimes.
3. **Two answer validators.** `run_answer_guard_lab` (flag-gated, runs on synthesis draft) vs `final_answer_validator` (deterministic contract validator on composed card). Plan C3 must not conflate them.
4. **Mock execution HIL.** Successful mock runs can still require analyst review (`ai_soc_require_hil_for_mock_execution`); empty-result and synthesis readiness do not bypass HIL.
5. **Hybrid / partial MCP evidence.** Empty search is handled (A1); **timeout**, **failed job**, **envelope schema mismatch**, and mixed outcomes across multiple calls — see Appendix A §execution outcomes.
6. **Contract vs code tool names.** Contract draft uses `splunk.search` / `search_splunk`; gate and registry use `splunk_run_query` alias — B2 must map aliases before COE sign-off.
7. **Lineage population on live narration.** Placeholders exist but `llm_raw_output_placeholder` stays `None` when narration runs; audit reproducibility gap for Phase C production enablement.

---

## Context

COE review of the live `/chat` pipeline (not the Experience Center / demo early-return path). Goal: make the system produce a **grounded final answer** when MCP (Splunk) and the LLM go live — safely, auditable, reviewable.

Today the pipeline is **evidence-rich; answer completeness depends on flags**:

- `routes_chat.py` → `build_live_chat_response()` in `app/chat/pipeline.py` routes → plans → generates+validates candidate SPL → `evaluate_mcp_execution` → `_context_stage` (RAG → SourceEvidence → StructuredContext → sufficiency) → severity/MITRE/lineage → **governed synthesis lab** → answer guard → response.
- `mcp_execution_gate.py` **already calls** `get_mcp_connector().call_tool()` in mock mode. Real execution is blocked at `_gate_review` when `registry.mode != "mock"` (`:276`) and by `NotImplementedError` in the connector (`:155`).
- **Synthesis defaults off** (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false`). When enabled, a deterministic draft is composed; live narration is a second flag (`AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`) and is **suppressed when `CONTROL_PLANE_ENABLED=true`**.

Remaining walls for production query→answer:

| Wall | Blocker | Status |
|------|---------|--------|
| **1 — Real MCP** | COE contract + real `call_tool` + gate arg mapping | Blocked |
| **2 — Production synthesis** | COE sign-off on flags, narration path vs control plane, lineage population | Partially implemented |
| **3 — Security / audit** | A1/A2 done; lineage fill + multi-path parity pending | Mostly done |

This crosses the CLAUDE.md stage boundary for live synthesis — each enabling phase stays behind explicit flags and needs sign-off before production merge.

---

## Phase completion tracker

| Phase | Item | Status | Evidence |
|-------|------|--------|----------|
| **A** | A1 empty-result correctness | ✅ Done | `context_sufficiency.py` Rule 3b; `test_negative_result_sufficiency.py` |
| **A** | A2 results→evidence injection defense | ✅ Done | `splunk_result_adapter.py`, `mcp_result_safeguard.py`; `test_mcp_result_injection_defense.py` |
| **A** | A3 audit lineage hooks | ✅ Placeholders | `lineage/builder.py` synthesis/answer_guard stages |
| **B** | B1 COE connection contract | 🟡 Draft | `contracts/splunk_mcp_connection_contract.md` (`schema_confirmed=false`) |
| **B** | B2 real `call_tool` + arg schema | 🟡 Mock complete / live COE | Contract args + confirmation gate (`ae88760`); `splunk_mcp.py` transport still `NotImplementedError` |
| **B** | B2b SPL source resolution | ✅ Done | Settings UI, MCP discovery resolve, orchestration order (`567fe62`) |
| **B** | B3 cost + allowlist safety | 🟡 Partial | Validator + bounded args at gate; production allowlist = COE env |
| **B** | B4 per-run approval workflow | ✅ Done (mock path) | `spl_execution_confirmation` HIL + chat confirm/update/reject (`ae88760`) |
| **B** | B-orch discovery planning (hybrid paths) | ✅ Done | `build_hybrid_mcp_discovery_resource_decisions` (`390e2dc`) — see Appendix A |
| **B** | B-orch live search adapter | 🟡 Partial | Contract args + confirmation; live `splunk_mcp.py` COE-gated — see Appendix A §O3 |
| **B** | B-orch dependency-aware resource scheduler | ✅ Design ready / code open | MCP may be prerequisite/intermediate/final; scheduler→resource→reconcile loop — see Appendix A §A.3–A.9 |
| **C** | C1 wire synthesis scaffold | ✅ Done | `pipeline.py` → `run_governed_synthesis_lab` |
| **C** | C2 synthesis stage + narration | 🟡 Flag-gated | `lab_runner.py`, `live_narration.py`; CP blocks live narration |
| **C** | C3 answer guard | 🟡 Flag-gated | `answer_guard/runner.py` wired; default off |
| **C** | C4 kill switches | ✅ Done | Flags + `AI_SOC_LLM_MODE=disabled` + air-gap |
| **D** | Route-plan shadow exercise | 🟡 Testable | Default hook returns `None`; tests inject candidates |

---

## Phases (ordered by dependency + risk)

### Phase A — Pre-live hardening ✅ (complete; maintain regression)

**A1. Empty-result correctness** — **DONE**

Executed-but-empty MCP results → `full_answer`/`partial_answer` with `execution_negative_result`, never `insufficient_evidence`. Verified: `build_source_evidence` sets `collection_status=collected`, `result_count=0`, `execution_outcome=negative_result`.

**A2. Results→evidence injection defense** — **DONE**

Defense at adapter boundary: `data_minimizer` + `scan_mcp_preview_rows` (wraps `prompt_injection_filter`). Sensitivity flags → sufficiency Rule 1 → `blocked_by_policy`.

**A3. Audit lineage hooks** — **PLACEHOLDERS ONLY**

Populate `llm_raw_output_placeholder` / `adapter_overrides_placeholder` when live narration or guarded adapter runs (follow-up under Phase C production enablement).

---

### Phase B — Real MCP adapter (Wall 1) ❌ COE-gated

**B1. COE connection contract (gate; blocks B2).**

Draft exists: `contracts/splunk_mcp_connection_contract.md`. COE must confirm: server URL, transport, auth, discovered tool names, **exact arg schema** (`search_query`, `earliest_time`, `latest_time`, `max_results`), approval workflow. Set `schema_confirmed=true` after S5 sign-off.

**B2. Implement real `call_tool`.**

- ✅ Gate uses `splunk_search_tool_arguments()` / `build_splunk_search_inputs()` (`ae88760`).
- ❌ Real transport in `app/connectors/mcp/splunk_mcp.py`; flip `_gate_review` `:276` once COE confirms schema.
- Reuse `live_schema_capture.py` + `discovery.py` for tool discovery.
- Align tool name aliases (`splunk_run_query` ↔ `search_splunk` ↔ contract `splunk.search`) at live boundary.

**B4. Per-run approval workflow.**

- ✅ `AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION` (default true): analyst must confirm or paste updated SPL; safe `validate_spl` before `call_tool`.
- ✅ Chat UI: Confirm & run / Run updated SPL / Reject on `spl_execution_confirmation` card.
- Mock path complete; live path uses same gate after COE enables execution flags.

**B3. Cost + allowlist safety.**

Enforce bounded `earliest/latest` + `SPL_MAX_RESULT_LIMIT` at validation **before** execution (wired via `splunk_search_tool_arguments`). Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` with live Splunk deployment (COE env).

**Missed: discovery vs search.** See **Appendix A** — Step 5 discovery planning (planned-only) vs Step 7 `splunk_run_query` execution (gated). B2 covers search; B-orch Phase O1 covers hybrid/spl_review discovery checklists.

**B2b. SPL source resolution (cross-plan — does not replace B2).**

Prerequisite for LLM-generated SPL to reach `normalized_spl` and enter the search gate. Documented in [`llm_lab-tier_spl_exposure` plan](/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md) Phase H; **extends** this plan, does not contradict it.

| Step | Source | Pipeline node | Executes? |
|------|--------|---------------|-----------|
| G | Lab-tier LLM SPL exposure (placeholders visible) | ✅ Done | `validate_spl_lab_candidate`, pipeline exposure split (`8f44eee`) |
| H0 | Config / skills / `SPL_ALLOWED_*` env map | ✅ Done | `source_profile_resolver.py`, `AI_SOC_SOURCE_PROFILE_MAP` |
| H1 | **RAG / playbook** — KB `splunk_indexes`, `sourcetypes`, `fields` | ✅ Done | `rag_source_profile_bridge.py` |
| H2 | MCP discovery **execution** (`splunk_get_indexes`, `splunk_get_metadata`) | ✅ Mock + Settings | `run_mcp_source_discovery()`; COE UI persist; resolve-time MCP > store (`567fe62`) |
| H3 | HIL `spl_source_profile_clarification` | ✅ Done | `build_spl_source_profile_review`, session `source_profile_slots` |
| H4 | `validate_spl` → `normalized_spl` | ✅ Done | Feeds `graph_node_execution`; B2 search adapter still open |

**Alignment rules (no contradiction with scope guardrails below):**
- Step 5 discovery **planning** (`plan_splunk_discovery_calls`) stays plan-only by default — unchanged.
- H2 discovery **execution** is the orchestration plan's optional Phase C executor — separate from B2 search.
- RAG slot values flow only through governed `SourceEvidence` / deterministic resolver — **no RAG→LLM direct path** for index substitution.
- B3 allowlist enforcement applies **after** substitution (resolved index must be in `SPL_ALLOWED_INDEXES`).
- B4 HIL reused for unresolved slots and execution approval.

---

### Phase C — Synthesis stage (Wall 2) 🟡 partially landed

**C1. Wire scaffold** — **DONE** (`pipeline.py` after context stage).

**C2. Synthesis + narration** — **FLAG-GATED**

- `run_governed_synthesis_lab` builds `GovernedSynthesisPackage` and deterministic draft.
- Live narration: `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` + sufficiency in `_LAB_READY_MODES` + **not** `CONTROL_PLANE_ENABLED`.
- **Gap:** populate lineage placeholders; resolve CP vs legacy narration ownership for production.

**C3. Answer guard** — **FLAG-GATED, WIRED**

`run_answer_guard_lab` runs dormant semantic guards when `AI_SOC_LLM_ANSWER_GUARD_ENABLED=true`. Distinct from `final_answer_validator` (always-on contract check on composed card).

**C4. Kill switches** — **DONE** (defaults false).

---

### Phase D — Route-suggestion LLM exercise (testable now, lowest risk) 🟡

Validate routing governance with supplied route-plan JSON — no live model required.

- Inject via `generate_llm_route_plan_candidate` or monkeypatch `_route_plan_shadow_candidate` (default `None` in `pipeline.py`).
- Confirm: `validate_route_plan_candidate` → `deterministic_route_plan_wins=True` → `disagreements` logged → deterministic skill reaches user. Shadow only.

---

## Appendix A — MCP execution orchestration (canonical)

*Merged from `2026-06-13_mcp-execution-orchestration-plan.md` (2026-06-13). Governs **who decides**, **plan vs execute**, and **what the analyst sees** for Splunk MCP in live `/chat`.*

### A.1 Design principles

| Principle | Rule |
|-----------|------|
| LLM never calls MCP | Backend-only via `evaluate_mcp_execution` / discovery helpers |
| Deterministic authority | Route, SPL validation, tool selection, execution flags, MITRE, severity stay policy-driven |
| LLM advisory only | Tool recommendations, narration — never override gates |
| Fail closed | Missing envelope, timeout, schema mismatch → no fabricated evidence |
| Separate plan vs execute | Step 5 plans *what could run*; Step 7 executes *only what passed gates* |
| No route skill for MCP | Resource Planner sub-phase — not a sixth live route skill |

### A.2 MCP tool surface (7 tools)

| Tool | Auto-execute? | Role |
|------|---------------|------|
| `splunk_get_indexes`, `splunk_get_metadata`, `splunk_get_index_info`, `splunk_get_knowledge_objects` | **No** (planned checklist) | Discovery planning |
| `splunk_get_info` | **No** | Registry/status only |
| `splunk_get_user_info` | **Never** | Blocked |
| `splunk_run_query` | **Only if all gates pass** | Search execution (Step 7) |

Mutating / SAIA / write tools: discoverable for status, always blocked.

### A.3 Dependency-aware planner model

```text
Layer 1 — Evidence/resource planning (early planner)
  Node:   graph_node_evidence_planning / compose_resource_plan
  Output: governed step graph, evidence gaps, dependencies, policy limits
  Rule:   no MCP I/O; steps describe capability needs, not user-selected authority

Layer 2 — Runtime resource scheduling
  Node:   graph_node_resource_scheduler
  Output: next ready PlanStep or terminal decision
  Inputs: step dependencies, produced evidence keys, prior outcomes, budgets
  Rule:   choose only a ready, policy-eligible step; no connector call

Layer 3 — Resource-specific planning and execution
  MCP:    graph_node_mcp_call_planning -> graph_node_mcp_execute_one -> graph_node_mcp_result_assess
  Other:  existing RAG / SPL / MITRE / HIL nodes through the same scheduler contract
  Output: produced evidence keys + step outcome + lineage

Layer 4 — Reconcile and continue
  Node:   graph_node_plan_reconcile
  Rule:   mark dependents ready, select governed fallback, request HIL, or stop
  Loop:   reconcile -> resource_scheduler until terminal or budget exhausted
```

Discovery remains a distinct call class:

```text
Discovery planning (Resource Planner)
  Output: resource_decisions.mcp.planned_discovery_calls[]
  Execute: never by default; optional only when COE enables discovery execution

Search execution
  Execute: splunk_run_query only, one call per executor-node visit
  Repeat:  bounded and serial in v1; no parallel fan-out
```

**Source-profile resolve (B2b):** `run_mcp_source_discovery()` at placeholder resolve time is separate — MCP > COE store > HIL; not auto-chained into search.

MCP call classes must remain distinct:

| Call class | Example | May run when | What it can unlock |
|------------|---------|--------------|--------------------|
| `metadata_discovery` | `splunk_get_indexes`, `splunk_get_metadata` | Plan requires missing source/schema metadata | Source-profile resolution, template selection, clarification |
| `evidence_search` | `splunk_run_query` | Approved `normalized_spl` and all execution gates pass | SourceEvidence, correlation pivots, sufficiency |
| `investigation_pivot` | second governed `splunk_run_query` | Recipe dependency and typed bounded outputs from a prior call | Cross-source correlation evidence |
| `job_lifecycle` | submit/poll/fetch or one server abstraction | Search was accepted asynchronously | Final envelope only; does not count as a new investigation decision |

The planner must distinguish **investigation calls** from **transport lifecycle operations**. A submit plus several polls is one logical `McpCallSpec` and consumes one investigation-call budget, while poll count/time is bounded separately by the connector lifecycle policy.

Search call planning remains post-resolution: the scheduler may select metadata MCP earlier, but it cannot materialize an `evidence_search` or `investigation_pivot` from `candidate_spl`. Those steps stay blocked until source resolution and full SPL validation produce approved `normalized_spl`.

### A.4 Target graph and imperative parity

```text
resource_scheduler
  -> metadata MCP ---------> assess -> reconcile ----+
  -> RAG -------------------> assess -> reconcile ----+
  -> SPL generation/resolve -> validate -> reconcile -+
  -> evidence MCP ----------> assess -> reconcile ----+--> resource_scheduler
  -> HIL/clarification -----> reconcile --------------+
  -> context_finalize when terminal
```

The same pure node functions must be used by both runtimes:

- LangGraph uses conditional edges from `resource_scheduler` and `plan_reconcile`.
- The imperative pipeline uses a bounded driver loop around the same scheduler, resource nodes, and reconcile function.
- `execute_plan_dispatch()` remains a compatibility dispatcher during migration; it must not become the multi-call planner.
- Add explicit source-resolution and reconcile stages to the live graph so LangGraph and imperative execution have the same safety order.
- The existing planner-led fan-out/fan-in shadow graph is a parity baseline, not the final adaptive execution topology. Intermediate MCP dependencies require a scheduler/reconcile loop rather than a fixed terminal MCP branch.
- LangGraph must adopt the same scheduler/reconcile semantics for the complete resource loop, not only the search stage or `execute_plan_dispatch()` on the imperative side.

### A.5 Authority matrix

| Decision | Authority | LLM role |
|----------|-----------|----------|
| Whether MCP is needed | Evidence plan + `path_type` | None |
| Investigation recipe | Deterministic recipe registry + route/evidence policy | Shadow suggestion only |
| Next resource step / stop decision | `graph_node_resource_scheduler` + `graph_node_plan_reconcile` | None |
| MCP capability needed for a step | Step `requires`/`produces` + deterministic evidence-to-capability mapping | None |
| Concrete MCP tool | Capability mapping + live safe discovery metadata + allowlist + registry health | Advisory only; cannot select |
| Tool fallback | Predeclared equivalent-capability alternatives with identical/lower authority | None |
| Discovery tools to *plan* | `plan_splunk_discovery_calls()` + path policy | None |
| Search tool to *select* | `select_mcp_tool()` | Advisory only if `LLM_TOOL_RECOMMENDATION_ENABLED` (default off) |
| Whether search may run | `evaluate_mcp_execution` + flags + B4 confirmation | None |
| Search arguments | `splunk_search_tool_arguments()` + SPL policy env | None |
| Empty vs failed vs timeout | Envelope validation + context sufficiency | Narration of deterministic conclusion only |
| MITRE / severity from rows | Deterministic MITRE + severity policy | None |

User-requested MCP server/tool: **preference only** — re-validated by `mcp_tool_selector.py`.

`PlanningDecision.selected_tools` remains route-level planning/trace metadata. It must not authorize execution. `ResourcePlanV2` step capability, runtime registry status, deterministic mapping, argument validation, and the execution gate jointly determine the concrete tool at runtime.

#### MCP decision algorithm

For every scheduler iteration:

1. Recompute unresolved required/optional evidence keys from validated step outcomes.
2. Find plan steps whose `depends_on` conditions are satisfied and whose outputs are still needed.
3. If the ready step requires an MCP capability, map the evidence need through `evidence_mcp_mapping.py` and the resource registry.
4. Intersect mapped tools with live discovered tools, server availability, read-only capability, identity/RBAC, per-server flags, and step policy.
5. Rank deterministically: exact governed tool binding, then approved equivalent-capability fallback; user/LLM preferences never outrank policy.
6. Validate arguments with the tool-specific schema. Search tools additionally require approved `normalized_spl`; metadata tools require bounded allowlisted selectors.
7. If no eligible tool exists, apply the step's declared failover. Otherwise emit one `McpCallSpec`.
8. After the result, classify the outcome, record produced evidence keys, and reconcile the next step.

### A.6 Multi-call state and contracts

Do not overload the existing singular `execution` object as the source of truth. Add a versioned orchestration envelope:

```text
mcp_orchestration:
  schema_version: "1"
  orchestration_id: <trace-scoped id>
  recipe_id: <governed recipe or single_search>
  status: planned|awaiting_approval|running|complete|partial|blocked|failed|budget_exhausted
  call_budget: {max_calls, calls_planned, calls_started, calls_completed, max_wall_time_ms}
  unresolved_evidence_keys: []
  calls: McpCallRecord[]
  next_call: McpCallSpec|null
  stop_reason: string|null
```

`McpCallSpec` must include `call_id`, `sequence`, `depends_on`, `purpose`, server/tool, argument template, normalized SPL hash, required policy checks, and approval state. `McpCallRecord` adds timestamps, outcome classification, redacted arguments, result-envelope reference, result count, warnings, and error type.

Extend `PlanStep` or introduce `ResourcePlanV2` with:

```text
depends_on[]
activation_condition
requires_evidence_keys[]
produces_evidence_keys[]
resource_capability
resource_alternatives[]
on_unavailable / on_empty / on_error / on_timeout / on_denied
max_attempts
```

Fallbacks are edges to other plan steps or terminal policies, not ad hoc exception handling inside the connector.

Compatibility during migration:

- Keep response `execution` as a derived summary of the primary/last search for existing clients.
- Make `mcp_orchestration.calls[]` authoritative for lineage and new UI.
- Update evidence adaptation to produce one `SourceEvidence` item per successful/empty call; failed calls produce limitations, never negative evidence.
- Aggregate sufficiency across call evidence without merging row counts or distinct counts across sources unless an explicit deterministic aggregation policy allows it.

### A.7 Bounded planning and stop rules

Initial defaults are conservative and remain configurable only within hard server-side caps:

- Serial execution only.
- `MCP_MAX_CALLS_PER_TURN=3` proposed default; hard cap must not be user- or LLM-controlled.
- One active logical investigation call at a time; each call has its own lifecycle timeout/poll cap and the orchestration has a total wall-clock budget.
- Every search call requires approved, non-null `normalized_spl` and deterministic validation immediately before execution.
- Approval binds `orchestration_id`, `call_id`, SPL hash, server, tool, and bounded arguments. Any material change invalidates approval.
- Default production posture requires approval per search call. A future recipe-level approval may cover multiple calls only if the UI shows every exact query/argument set before approval and COE explicitly enables it.

Stop when any condition is true:

1. Required evidence keys are satisfied.
2. The governed recipe has no eligible dependent call.
3. A call is blocked, denied, schema-invalid, or permission-failed.
4. Timeout/error policy says fail closed; retries are not automatic in v1.
5. Call or wall-clock budget is exhausted.
6. Analyst rejects or changes scope.

An empty result may activate a predeclared fallback call only when the recipe explicitly defines that edge. It must never trigger open-ended LLM replanning. The LLM *may* propose the broadened query content on such an edge (see A.17 `broaden_scope_on_empty`) — bounded by validation, allowlist, budget, and per-call approval. "Bounded LLM-proposed retry" is permitted; "open-ended LLM replanning" (LLM adds calls, raises budget, leaves allowlist, or re-plans the investigation) is not.

### A.8 Failover policy

| Failure/outcome | Allowed deterministic failover | Prohibited behavior |
|-----------------|--------------------------------|---------------------|
| Preferred tool undiscovered/unavailable | Select predeclared equivalent-capability tool on an approved server | Guess a tool name or let LLM choose |
| Metadata discovery unavailable | Use fresh COE source-profile store, then governed RAG metadata, otherwise HIL clarification | Generate executable SPL with unresolved sources |
| Search tool unavailable | Stop or use explicitly approved equivalent search tool with same validation/approval | Fall back to SAIA/generative/write/admin tool |
| Connector/transient error | At most configured retry of the same idempotent lifecycle operation; then partial/review | Generate a different search automatically |
| Async job still running | Poll within poll/time budget; optionally persist resumable job state | Count each poll as a new investigation or poll indefinitely |
| Permission denied/RBAC | Stop and request admin/analyst review | Retry with broader service identity |
| Schema mismatch | Reject envelope, mark evidence unavailable, require adapter/COE review | Pass raw rows to synthesis |
| Search validation failure | Return to SPL revision/HIL; revalidate after changes | Execute candidate or unvalidated SPL |
| Successful empty result | Mark scoped negative evidence; follow only explicit `on_empty` recipe edge | Treat as connector failure or broad “no threat” conclusion |
| Partial/truncated result | Preserve partial evidence and limitation; follow explicit recipe policy | Silently present as complete |

Fallback selection must not increase authority, data scope, time range, result cap, or tool capability. Any fallback that changes executable arguments invalidates prior approval.

### A.9 Governed recipe shape

Multi-call behavior must come from a small deterministic recipe registry, not free-form planner prose. Start with `single_search` and add one COE-approved investigation recipe at a time.

```text
recipe:
  recipe_id
  eligible_skills / path_types
  max_calls
  calls[]:
    call_id, purpose, depends_on, activation_condition
    call_class, resource_capability, resource_alternatives
    spl_template_family or deterministic transform
    required_evidence_keys
    produces_evidence_keys
    on_unavailable, on_empty, on_error, on_timeout, on_denied, terminal
```

Allowed activation conditions in v1: `always`, `previous_ok`, `previous_empty`, `evidence_key_missing`. Conditions operate on normalized envelope metadata, not arbitrary row-content interpretation. Any follow-up SPL produced by a deterministic transform re-enters source resolution and full SPL validation.

### A.10 Execution outcomes (what the analyst sees)

| Outcome | Answer mode | HIL |
|---------|-------------|-----|
| Connector error | `analyst_review_required` or partial + limitation | Yes |
| Timeout | Partial — job did not complete in window | Yes |
| Permission denied | Blocked + review | Yes |
| Failed search (validation/schema) | No evidence conclusion | Yes |
| Success, 0 rows | Honest negative — **not** “no threat” | Optional |
| Success, truncated | Partial + review truncated preview | Yes |
| Mock execution | Fixture labeled | Yes (unless demo relax flag) |
| Mixed multi-call outcomes | Partial answer with per-call limitations | Yes |
| Budget exhausted | Partial/review-required; list unresolved evidence | Yes |

**Rule:** empty ≠ failed. LLM must not treat failed execution as negative evidence. Same-turn follow-up is allowed only through a predeclared governed recipe, per-call validation, budget checks, and required HIL.

### A.11 Orchestration delivery sub-phases (O0–O7)

| Sub-phase | Scope | Status |
|-----------|-------|--------|
| **O0** | Document & align (`details.html`, this appendix) | ✅ |
| **O1** | Discovery planning for hybrid/spl_review/guided (`composer.py`) | ✅ `390e2dc` |
| **O2** | Envelope hardening | ✅ (= Phase A) |
| **O3** | Live `splunk_run_query` adapter | 🟡 (= Phase B2; mock complete, live COE) |
| **O4** | Optional auto discovery execution | ❌ Proposed (`MCP_DISCOVERY_EXECUTION_ENABLED`) |
| **O5a** | `ResourcePlanV2` dependency/failover contracts + deterministic recipe registry | ✅ Contract landed — `app/planner/recipe_registry.py` (`single_search`, `broaden_scope_on_empty`), `app/orchestration/mcp_orchestration.py` (envelope + HIL-approval gate `can_execute_call`/`approve_call`), `ResourcePlanV2` in `resource_plan.py`; `test_recipe_registry_contract.py` (15 tests). No connector change; default-off |
| **O5b** | Resource scheduler + MCP plan/execute-one/assess + reconcile loop | ❌ Ready to implement behind flags |
| **O5c** | Async lifecycle, evidence aggregation, lineage, UI, parity tests | ❌ Required before live multi-call |
| **O6** | LLM narration of MCP-informed answers | 🟡 (= Phase C; flag-gated) |
| **O7** | Live activation and staged rollout | ❌ COE-gated |

### A.12 Configuration flags (MCP + confirmation)

| Flag | Default | Controls |
|------|---------|----------|
| `MCP_GLOBAL_EXECUTION_ENABLED` | false | Any live MCP call |
| `MCP_SERVER_*_EXECUTION_ENABLED` | false | Per-server execution |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | false | Mock search in gate |
| `AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION` | true | Analyst confirm/update before search |
| `MCP_DISCOVERY_EXECUTION_ENABLED` | false (proposed) | Auto-run discovery tools |
| `MCP_MULTI_CALL_ORCHESTRATION_ENABLED` | false (proposed) | Enables bounded recipe loop; false preserves single-call behavior |
| `MCP_MAX_CALLS_PER_TURN` | 3 (proposed, server-capped) | Maximum started MCP calls in one turn |
| `MCP_ORCHESTRATION_MAX_WALL_TIME_MS` | COE decision | Total MCP loop wall-clock budget |
| `MCP_MAX_POLLS_PER_CALL` | COE decision | Async lifecycle poll cap per logical call |
| `LLM_TOOL_RECOMMENDATION_ENABLED` | false | Advisory tool hints |
| `SPL_VALIDATION_ENABLED` | true | Required before search |

### A.13 COE decisions before live search (O3/O7)

1. Splunk MCP URL, transport, auth; set `schema_confirmed=true` on contract
2. Identity model: analyst pass-through vs service account
3. Async vs sync `splunk_run_query` lifecycle
4. Whether O4 discovery auto-execution is in scope
5. Max discovery + search calls per turn and total wall-clock budget
6. Production index/sourcetype allowlist
7. Per-call approval vs exact predeclared recipe approval
8. First governed multi-call recipe and allowed activation conditions
9. Equivalent-capability tool fallback allowlist per server
10. Async submit/poll/fetch schema, poll interval, cancellation, and resumability
11. Whether ML-model-application MCP tools (Lantern Cloud Platform pattern, A.17 #2) enter scope; if so, model-discovery + apply call classes under the same authority matrix

### A.14 Required tests and acceptance criteria

- Metadata MCP can run before SPL when it is an explicit prerequisite.
- Search MCP emits no call before source resolution and approved validation.
- `candidate_spl` can never enter `McpCallSpec`.
- One executor-node visit performs at most one connector call.
- Async submit/poll/fetch remains one logical investigation call with bounded polls.
- Maximum-call and wall-clock limits stop the loop deterministically.
- Empty, timeout, permission denied, schema mismatch, partial, and mixed outcomes remain distinct.
- Approval hash mismatch blocks execution after any SPL/argument change.
- A failed call cannot satisfy an evidence key or become negative evidence.
- Every call has trace/lineage records; secrets and raw auth never appear.
- Imperative and LangGraph paths produce equivalent orchestration summaries and evidence for the same fixture.
- Tool-unavailable, metadata-store, RAG-metadata, HIL, equivalent-tool, and no-fallback paths are independently tested.
- Fallback cannot increase authority/scope and argument changes invalidate approval.
- Feature flag off preserves current single-call response contracts and governance baseline.
- Governance regression, full backend tests, harness 6/6, and frontend build pass.

### A.15 Trace / UI surfaces

- `evidence_plan.resource_plan.provenance.resource_decisions.mcp` — planned discovery + skip reasons
- `execution` — tool, status, envelope, `result_count`
- `mcp_orchestration` — recipe, budget, ordered calls, per-call outcome, stop reason
- `human_review` — gate blocks, `spl_execution_confirmation`, source-profile HIL
- Settings → **Source Profiles** — COE index/sourcetype map
- Analyst card: discovery checklist, executed search, limitations on failure

### A.16 Out of scope

Splunk telemetry writes; SAIA/generative tools; free-form or LLM-initiated MCP calls; unbounded retries; parallel MCP fan-out in v1; MCP as sixth route skill.

### A.17 External guidance reconciliation — Splunk Lantern (2026-06-13)

Reviewed two Lantern MCP-investigation playbooks:

- Security / Automation: *Leveraging LLM reasoning and ML capabilities for Jira alert investigations* (Splunk MCP server for Cloud Platform + Jira; applies pre-existing ML models so users skip writing the SPL needed to run them).
- Observability / Troubleshoot: *Automating alert investigations by integrating LLMs with the Splunk platform and Confluence* (Atlassian MCP `searchConfluenceUsingCql`/`getConfluencePage` for runbooks; Splunk MCP `run_splunk_query`/`get_indexes`/`get_metadata`; Plan-Run-Adapt-Re-run loop; "stop and ask me for guidance" HIL; one-time auth).

Most guidance already matches this plan (discovery-before-query, runbook→plan→query, per-call approval, HIL, tool surface, secret-safe auth). Three deliberate divergences and one capability gap:

| # | Lantern pattern | Our governed stance | Resolution |
|---|-----------------|---------------------|------------|
| 1 | **Plan-Run-Adapt-Re-run** — on empty results the LLM autonomously widens the time window / tries alternative sourcetypes and re-runs | A.7 forbids *open-ended* LLM replanning; A.9 `on_empty` activation must be predeclared | **Adopt the value, govern the loop — LLM proposes, deterministic validates.** Add a `broaden_scope_on_empty` recipe whose retry edge is *triggered* deterministically (`previous_empty`) but whose broadened query is *proposed by the LLM* through the existing LLM-primary SPL failover path. The proposal is a lab-tier candidate — it re-enters R5 relevance → source resolve → `validate_spl` → allowlist → per-call approval before it can run. Adaptive intelligence kept; authority not ceded. Not a closed rigid transform. |
| 2 | **ML-model application without SPL** (Cloud Platform MCP runs pre-existing ML models) | Plan is SPL-search-centric; air-gapped 7-tool surface (A.2) has no model-apply tool | **Forward note only.** Treat `apply_ml_model` / model-discovery as a future call class behind the same authority matrix (capability mapping → discovery → allowlist → approval). Not in the 7-tool air-gapped surface; raise as COE decision A.13 #11. Out of v1 scope (A.16). |
| 3 | Prompt gives **contextual hints, no exact tool prescription**; LLM may steer toward an MCP | LLM is fully out of tool selection; selection is deterministic (A.5) | **No change to authority.** Contextual hints are fine *for narration only* (C2). Tool choice stays deterministic; LLM hints never authorize a call. Documented divergence — intentional, stricter than Lantern. |
| 4 | Atlassian MCP for runbook retrieval | Our runbooks live in governed SOC-KB RAG (H1), not a live Confluence MCP | **No change.** RAG path is the air-gapped equivalent; no live Confluence MCP. If COE later wants live Confluence, it enters as a separate read-only MCP under the same registry, never an LLM-direct path. |

**Governed `broaden_scope_on_empty` recipe (delta 1 — the one concrete addition):**

```text
recipe:
  recipe_id: broaden_scope_on_empty
  eligible_skills: [spl_generation, guided_investigation]   # COE to confirm
  max_calls: 2
  calls:
    - call_id: c1_primary_search
      call_class: evidence_search
      activation_condition: always
      spl_template_family: <route-bound family>
      produces_evidence_keys: [primary_search_rows]
    - call_id: c2_broadened_search
      call_class: evidence_search
      depends_on: [c1_primary_search]
      activation_condition: previous_empty   # deterministic TRIGGER
      # broadened query is LLM-PROPOSED, deterministically validated:
      spl_source: llm_failover_candidate     # reuses AI_SOC_LLM_SPL_FALLBACK path
      proposal_context:
        - empty_primary_query + route + evidence gap (no raw rows to LLM)
        - allowed indexes/sourcetypes + earliest cap (LLM proposes WITHIN bounds)
      validation_chain: [r5_relevance, source_resolve, validate_spl, allowlist, approval]
      produces_evidence_keys: [broadened_search_rows]
      on_empty: terminal   # honest negative; never "no threat"
      on_invalid_proposal: terminal   # LLM proposal fails any gate -> stop, HIL
```

**LLM-assisted failover loop (why this is not a closed rigid solution).** On `previous_empty`, the recipe invokes the existing LLM-primary SPL failover (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`, default off) — *no new flag*. The LLM reasons about *why* the primary returned empty (wrong sourcetype, time window too tight for a slow attack, over-narrow filter) and proposes a broadened/alternative SPL. That proposal is **advisory and non-executable**: it enters as a lab-tier candidate (`validate_spl_lab_candidate`), passes the R5 `spl_relevance_check`, resolves sources, runs full `validate_spl`, and consumes a **fresh per-call approval** before any execution. The deterministic layer owns the bounds (LLM cannot exceed `SPL_DEFAULT_EARLIEST`, leave `SPL_ALLOWED_INDEXES`/`_SOURCETYPES`, raise the result cap, or select a blocked tool); the LLM owns the *judgment* of what to try. Scope change invalidates the prior approval hash; the call counts against `MCP_MAX_CALLS_PER_TURN`; raw rows never reach the prompt. A still-empty or gate-failed result is an honest terminal outcome — not connector failure, not "no threat." This is the governed analog of Lantern's adapt step: **LLM intelligence in the loop, deterministic authority around it.**

---

## Final architecture review (2026-06-13)

| Existing architecture contract | Final plan alignment | Implementation consequence |
|-------------------------------|----------------------|----------------------------|
| Planner-led control plane chooses paths/branches; LLM is advisory | Early planner creates governed `ResourcePlanV2`; scheduler and reconcile remain deterministic | Do not put MCP invocation or free-form tool choice in an LLM node |
| `EvidencePlan` owns required/missing evidence keys | Step `requires_evidence_keys` / `produces_evidence_keys` drive readiness and stop decisions | MCP is called only when an unresolved evidence dependency maps to an eligible MCP capability |
| MCP evidence mapping is report-only today | Promote mapping logic into a gated runtime selector without changing its authority rules | Extend mappings by capability; do not hard-code question text or trust tool suggestions |
| Resource registry owns capabilities and availability | Concrete tool selection intersects plan capability with safe live discovery and registry policy | Unknown, blocked, mutating, SAIA, and admin tools remain ineligible |
| Candidate SPL never executes | Only search-class MCP steps consume approved `normalized_spl` | Metadata MCP may run earlier; search MCP remains blocked until validation completes |
| Multi-step correlation replaces risky subsearches | Typed bounded outputs from Search A may bind governed slots in Search B | Revalidate extracted entities, rendered SPL, scope, and approval before Search B |
| Splunk may use async jobs | Submit/poll/fetch is one logical call with separate lifecycle bounds | Connector owns polling state; planner sees normalized logical outcome |
| Planner-led LangGraph shadow is current architecture baseline | New scheduler/reconcile loop extends that architecture for adaptive dependencies | Update imperative and LangGraph paths together and rerun dual parity |
| Fail closed and preserve empty-vs-failed semantics | Explicit outcome/failover matrix and per-call SourceEvidence | No failed call can unlock evidence-dependent steps or become negative evidence |

### Implementation order

1. **O5a contract commit:** ✅ **Done** — `ResourcePlanV2` + dependency/failover fields (`resource_plan.py`), `mcp_orchestration` models + HIL-approval gate (`mcp_orchestration.py`), recipe registry with `single_search` + `broaden_scope_on_empty` (`recipe_registry.py`), contract tests (`test_recipe_registry_contract.py`, 15 green). No connector behavior change; nothing wired into live pipeline. The broadened call is LLM-proposed, full-validation-chained, and HIL-gated: `can_execute_call` blocks until `approve_call` flips approval to `approved` — "if HIL approves, execute."
2. **O5b scheduler commit:** Add pure scheduler/reconcile functions and fixture-only resource execution. Keep the feature flag off; prove metadata-MCP-before-SPL and Search-A-to-Search-B paths.
3. **O5c integration commit:** Wire imperative and LangGraph paths to the same nodes; add source-evidence aggregation, lineage, HIL continuation, async lifecycle fixtures, and parity tests.
4. **O3 adapter commit:** Implement the COE-confirmed live transport and exact schemas behind existing execution flags. Do not combine this with scheduler contracts.
5. **O7 activation:** Enable one approved recipe/server in staging, observe budgets/failures, run governance regression, then seek production sign-off.

### Final verdict

The plan is **ready to implement for contracts, scheduler logic, mock/fixture orchestration, and parity work**. It now supports MCP as a prerequisite, intermediate evidence step, multi-search pivot, or final evidence step. It also defines how MCP need is decided, how tools are selected, and how unavailable tools, connector failures, async jobs, empty results, validation failures, RBAC denial, and schema mismatch are handled.

Live MCP activation is **not** ready until the COE decisions in A.13 are closed. Implementation must begin with O5a and keep all new runtime behavior default-off.

---

## Scope guardrails (per CLAUDE.md)

- One commit per concern; do not combine execution changes with connector-readiness or UI-only changes.
- Candidate SPL stays non-executable; only approved `normalized_spl` enters the gate.
- LLM never calls MCP directly; backend mediates.
- All MCP/LLM status output redacts secrets (`url_configured`/`auth_configured` booleans only).
- Phases B/C production enablement stay flag-gated and need explicit COE sign-off.
- Experience Center (`coe_synthetic_fixture`) stays isolated — never route live synthesis through demo path.

## Verification (end-to-end)

- Governance regression: `./scripts/run_stage3_governance_regression.sh` → PASS, harness 6/6.
- Backend: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`.
- Frontend: `cd frontend && npm run build`.
- Per phase:
  - A1/A2 — `test_negative_result_sufficiency.py`, `test_mcp_result_injection_defense.py` (regression pins).
  - B2 — mock real transport; assert `build_splunk_search_inputs` arg mapping + envelope validation.
  - B2b — placeholder SPL → RAG/config resolution → `normalized_spl`; MCP discovery exec mock; HIL on ambiguous RAG.
  - C2/C3 — flag off = deterministic-only; flag on in lab = guarded answer; **also test `CONTROL_PLANE_ENABLED=true` blocks live narration**.
  - D — supplied route-plan JSON → deterministic wins + disagreement in trace.
  - Parity — repeat C/D checks on LangGraph path when `langgraph_orchestration_enabled`.

## Plan housekeeping

- SPL generation audit **closed** — [`2026-06-13_spl-generation-audit-completion.md`](2026-06-13_spl-generation-audit-completion.md).
- MCP orchestration content is **Appendix A** in this file (standalone orchestration plan superseded 2026-06-13).
- `plan-reviewer` before non-trivial open work (B2 live, C production enablement).
- `validator` after each phase.
