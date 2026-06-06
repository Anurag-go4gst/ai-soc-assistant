# Chat Pipeline State v2 and Per-Node Trace — Specification

> Slice **S1b** (work items **C1** + **C9**) of `plans/AI_SOC_MASTER_PLAN.md`.
> **Batch 4 runtime:** additive top-level visibility + `node_trace` ship in
> `app/chat/pipeline_visibility.py` (control-plane gated). The field inventory and schema
> below remain the C1/C9 reference. Where the master plan text diverges from code, see
> **Discrepancies**.

---

## 1. Current state (verified)

### 1.1 The real `ChatPipelineState` field list

Defined at `backend/app/chat/pipeline.py:ChatPipelineState` (`class ChatPipelineState(TypedDict, total=False)`, lines 89–127). It has **38 fields** (not "~30 keys" as the plan claims — see Discrepancies). Because the TypedDict is `total=False`, every key is optional and nodes accumulate them by returning `{**state, ...}`.

| # | Field | Type | One-line purpose |
|---|-------|------|------------------|
| 1 | `request` | `ChatRequest` | The inbound chat request (seed of the state). |
| 2 | `trace_id` | `str` | Per-turn UUID minted in `graph_node_init_routing`. |
| 3 | `query_understanding` | `Any` | Output of `understand_query()` (or degraded failover). |
| 4 | `selected_use_case` | `Any` | Use-case record matched to the query. |
| 5 | `routed` | `dict` | Deterministic routing result (`skill`, `tool_plan`, `confidence`, `comparison`, `routing_provenance`). |
| 6 | `route_plan_shadow` | `dict` | Shadow route-plan envelope; authority compare, preconditions, audits all nest here. |
| 7 | `routing_skill_resolution` | `dict` | Effective-skill resolution + `legacy_intent_authority`. |
| 8 | `skill_selection` | `Any` | `select_skill_chain()` result. |
| 9 | `selected_skill_chain` | `Any` | The selected chain from `skill_selection`. |
| 10 | `disagreement` | `bool` | True when deterministic vs shadow routing disagree. |
| 11 | `comparison` | `dict` | Routing comparison block (incl. `llm_shadow`). |
| 12 | `workflow_plan` | `dict` | Planned workflow (skill, tool_plan, required/missing sources, `execution_enabled`). |
| 13 | `candidate_spl` | `dict \| None` | Candidate (non-executable) SPL generation result. |
| 14 | `spl_validation` | `dict \| None` | Deterministic SPL validation outcome. |
| 15 | `execution` | `dict` | MCP execution-gate envelope (status, block_reason, tool selection). |
| 16 | `human_review` | `dict` | HIL gate payload (required, review_type, safe message). |
| 17 | `source_evidence` | `list[dict]` | Governed evidence items (`SourceEvidence`). |
| 18 | `structured_context` | `dict` | Structured context package. |
| 19 | `context_sufficiency` | `dict` | Sufficiency-gate result (status, synthesis_readiness, reasons). |
| 20 | `spl_template` | `dict \| None` | Template **summary** for the use case (not a status). |
| 21 | `mitre_mappings` | `list` | MITRE technique mappings. |
| 22 | `severity_decision` | `Any` | `decide_severity()` output. |
| 23 | `synthesis_status` | `Any` | Governed synthesis-lab status. |
| 24 | `answer_guard` | `Any` | Answer-guard lab result. |
| 25 | `action_capability` | `Any` | Allowed actions / tier capability. |
| 26 | `investigation_lineage` | `Any` | "How this answer was produced" lineage object. |
| 27 | `message` | `str` | Final user-facing message string. |
| 28 | `note` | `str` | Final note string. |
| 29 | `governance_trace` | `Any` | Governance trace block. |
| 30 | `query_to_intent` | `dict \| None` | Passive query→intent stage payload. |
| 31 | `intent_classification` | `dict \| None` | Intent classification extracted from `query_to_intent`. |
| 32 | `evidence_plan` | `dict \| None` | Evidence plan (control-plane gated). |
| 33 | `route_adjudication` | `dict \| None` | Control-plane route adjudication payload. |
| 34 | `llm_plan_validation` | `dict \| None` | LLM advisory plan validation payload. |
| 35 | `mitre_decision` | `dict \| None` | MITRE decision (status + registry metadata). |
| 36 | `answer_contract` | `dict \| None` | Answer contract read-model payload. |
| 37 | `soc_kb_retrieval` | `dict \| None` | Governed SOC-KB RAG retrieval result. |
| 38 | `response` | `PlaceholderResponse` | The assembled final response object. |

### 1.2 Current node execution order (verified)

The imperative path is `backend/app/chat/pipeline.py:_build_live_chat_response_inner` (lines 143–162). It is **branched**, not linear:

```
init_routing
  → query_to_intent
  → evidence_planning
  → shadow_enrichment
  → IF _uses_rag_only_path(state):           # evidence_plan.answer_mode == "rag_only"
        prepare_rag_only → rag_early
     ELSE:
        workflow_spl
        IF _uses_pre_mcp_rag(state):          # evidence_plan.needs_rag && rag_phase == "pre_mcp"
            rag_early
        execution
  → context_finalize
```

There are **9** `graph_node_*` functions:
`graph_node_init_routing` (165), `graph_node_query_to_intent` (204), `graph_node_evidence_planning` (224), `graph_node_shadow_enrichment` (239), `graph_node_workflow_spl` (331), `graph_node_execution` (365), `graph_node_prepare_rag_only` (383), `graph_node_rag_early` (414), `graph_node_context_finalize` (430).

The LangGraph path (`backend/app/graph/chat_workflow.py:_compiled_chat_graph`, lines 27–61) wraps the **same nine functions** with conditional edges (`_after_shadow_enrichment`, `_after_workflow_spl`, `_after_rag_early`) that reproduce the same branch. Parity is the explicit goal (`run_chat_via_langgraph` docstring, line 89). The path is selected by `langgraph_orchestration_enabled` (default `False`, `backend/app/config.py:241`), checked in `backend/app/api/routes_chat.py:47` and `backend/app/api/routes_chat_stream.py:65`.

Note: most node work is concentrated in `graph_node_context_finalize` (lines 430–770) — MITRE, severity, synthesis lab, answer guard, answer contract, final-answer validation, lineage, governance trace, control-plane trace, and the `PlaceholderResponse` assembly all happen there. This matters for C2–C8 (later slices), which propose decomposing it; this spec only documents it.

### 1.3 Current trace mechanism (verified)

There is **no per-node trace today.** A single unified trace is assembled **once** at the end, in `graph_node_context_finalize` (lines 692–706), by `backend/app/chat/control_plane_trace.py:build_control_plane_trace`.

Key properties of the current mechanism:

- **Post-hoc, single assembly.** It reads accumulated state (`route_plan_shadow`, `soc_kb_retrieval`, `spl_validation`, `candidate_spl`, `execution`, `mitre_decision`, `answer_contract`, `final_answer_validation`, …) and packages a summary tree. It is **not** emitted incrementally by each node.
- **Packaging-only.** The module docstring (`control_plane_trace.py:1–5`) states it "must not call RAG, MCP, SPL validation, MITRE resolution, or any LLM path." It only summarizes already-computed values.
- **Flag-gated.** Built only when `settings.control_plane_enabled` is true (`pipeline.py:693`; default `False`, `config.py:243`). When off, `control_plane_trace = None`.
- **Redacted.** `control_plane_trace.py:_redact` (lines 141–155) recursively masks any key matching `_SECRET_KEYS = ("secret","token","password","passwd","api_key","apikey","dsn","auth")` (line 11) and string values containing `bearer `, `password=`, `token=`.
- **Attached to the response** as `PlaceholderResponse.control_plane_trace` (`schemas/responses.py:391`, type `dict | None`).

---

## 2. Proposed `ChatPipelineState` v2 — additive fields (C1)

Reconciled against §1.1. **Additive only**: `ChatPipelineState` stays `total=False`, so adding keys cannot break existing nodes. The table maps each plan-proposed field to what already exists.

| Field | Type | Default | Populating node | Already exists? |
|-------|------|---------|-----------------|-----------------|
| `session_id` | `str \| None` | `None` | `graph_node_init_routing` (read from `request`) | **Genuinely new.** `ChatRequest` (`schemas/requests.py:4–7`) has no `session_id`. Depends on **A5** (session memory) adding the request field + `chat/session_store.py`. |
| `session_pins` | `dict \| None` | `None` | new session-load node (A5) | **Genuinely new.** No analogue today. Pins inform planning only; every gate must still re-run (C1 "Rule"). |
| `live_execution_skill` | `str \| None` | `None` | `graph_node_init_routing` | **Value exists, name is new.** This mirrors `routed["skill"]` (`pipeline.py:199`) / response `selected_skill` (`responses.py:357`). Add as an explicit alias; do **not** drop `routed`. |
| `planning_or_analytic_skill` | `str \| None` | `None` | new `graph_node_resolve_planning_skill` (C2) | **Genuinely new** as a first-class key. Derived from QU / 105 map / use case. Today the dual-skill notion lives implicitly in `routing_skill_resolution` / `route_authority` (`planning_primary_skill`), not as its own state key. |
| `skill_enrichment` | `dict \| None` | `None` | new `graph_node_load_skill_enrichment` (C2/Track B) | **Genuinely new.** Depends on **B1** `content_enrichment` schema. Must be loaded from local catalog only — never GitHub markdown. |
| `spl_template_status` | `str \| None` (`active` / `planned` / `unavailable`) | `None` | `graph_node_workflow_spl` (or future `graph_node_select_spl_template`, C4) | **Partial.** `spl_template` (field #20) exists but is a *template summary*, not a lifecycle *status*. New field is additive and distinct. |
| `mitre_evidence_status` | `dict[str, str]` (per-technique status) | `None` | `graph_node_context_finalize` (or future `graph_node_resolve_mitre_evidence_status`, C5) | **Partial / overlaps.** `mitre_decision` (#35) and `mitre_mappings` (#21) carry the data; this would be an aggregated per-technique status map in the §A2 vocabulary, derived from them. Risk of duplication — see Discrepancies. |
| `execution_decision` | `dict \| None` | `None` | `graph_node_execution` (or future `graph_node_prepare_execution_decision`, C4) | **Partial duplicate.** Overlaps `execution` (#15) + `human_review` (#16), which already encode the gate outcome. Recommend it be a thin derived summary, not a parallel source of truth. |
| `answer_guard_result` | `Any` | `None` | `graph_node_context_finalize` | **Duplicate.** Identical to existing `answer_guard` (#24, response field `responses.py:399`). **Do not add a second key** — reuse `answer_guard`. |
| `final_answer_validation` | `dict \| None` | `None` | `graph_node_context_finalize` | **Additive as a state key; already a response field.** Computed as a finalize-local (`pipeline.py:664–672`) and emitted as `PlaceholderResponse.final_answer_validation` (`responses.py:393`), but it is **not** currently a `ChatPipelineState` key. Cleanest "promote a computed local to a state key" case — useful so `node_trace` and parity tests can read it from state. |
| `node_trace` | `list[dict]` | `[]` | **every** node appends one record | **Genuinely new.** See §3. No per-node trace exists today. |

**Recommendations (C1):**
1. **Drop `answer_guard_result`**; reuse `answer_guard`.
2. **Promote `final_answer_validation`** from finalize-local to a state key (it is already a response field).
3. Treat `execution_decision` and `mitre_evidence_status` as **derived summaries** over existing keys, not new sources of authority, to avoid two-writers-one-fact drift.
4. `live_execution_skill` is an **alias** of the existing routed skill; keep `routed`/`selected_skill` authoritative.

**Hard rule (from C1):** session pins inform **planning only**; every deterministic gate (SPL validation, MCP execution, HIL, final-answer validation) re-runs regardless of pins.

---

## 3. `node_trace` record schema (C9)

### 3.1 Per-record shape

Each node appends exactly one record. This is a **new pattern** — see Discrepancies (current trace is single post-hoc assembly, not per-node emission).

```json
{
  "node_name": "graph_node_validate_spl",
  "input_summary": { "template_id": "auth_failed_login_spike" },
  "output_summary": { "approved": true },
  "decision_reason": "deterministic policy pass",
  "guardrail_status": "pass",
  "human_review_required": false
}
```

| Key | Type | Meaning |
|-----|------|---------|
| `node_name` | `str` | The `graph_node_*` function name. |
| `input_summary` | `dict` | **Summary** of the inputs the node read — IDs, flags, statuses. Never raw payloads. |
| `output_summary` | `dict` | **Summary** of what the node produced — decisions, booleans, status strings. |
| `decision_reason` | `str` | Short deterministic reason for the branch/outcome. |
| `guardrail_status` | `str` | `pass` / `block` / `not_run` / `n/a`. |
| `human_review_required` | `bool` | Whether the node forced/observed a HIL gate. |

### 3.2 Redaction rule (mandatory)

`input_summary` and `output_summary` follow the existing **packaging-only** discipline (`control_plane_trace.py:1–5`): summaries of already-computed values, never raw payloads. Specifically prohibited (per CLAUDE.md and `control_plane_trace.py:_redact`):

- **No secrets** — reuse `_redact` + `_SECRET_KEYS` (`control_plane_trace.py:11, 141–155`): mask any key containing `secret/token/password/passwd/api_key/apikey/dsn/auth`, and string values containing `bearer `, `password=`, `token=`.
- **No raw events** — no Splunk rows, no MCP tool outputs.
- **No prompts, credentials, or RAG chunks** — RAG appears only as match status / evidence refs / collection ids (mirror `control_plane_trace.py:_rag_trace`), never chunk text.
- **No reasoning traces or model internals.**

Implementation note: every record MUST pass through the same `_redact` before being attached, so the rule is enforced in one place rather than per node.

### 3.3 Where it attaches (recommendation, not open-ended)

The plan leaves "append to `control_plane_trace` vs new `node_trace` field" unresolved. **Recommendation: nest under the existing `control_plane_trace`** as `control_plane_trace["node_trace"]`, rather than adding a second top-level response field.

Rationale:
- Reuses the existing **flag gate** (`control_plane_enabled`) and the existing **redaction path** in one module.
- Avoids a second additive `PlaceholderResponse` field (smaller compat surface; C10).
- The trace already aggregates per-stage summaries, so per-node records are a natural sub-key.

Cost: slightly less discoverable than a top-level `node_trace`. If product later wants top-level prominence, a top-level field can be added additively then (still C10-safe). Either way, the in-state `node_trace` key (§2) is the accumulation buffer; the response surfacing is a packaging decision in finalize.

### 3.4 Additive-only guarantee (C10)

- `node_trace` is **only present when `control_plane_enabled` is true**, exactly like `control_plane_trace` today. When the flag is off, behavior and response shape are byte-identical to current.
- No existing `control_plane_trace` sub-key changes meaning; `node_trace` is purely additive within it.
- It must populate **identically in both the imperative and LangGraph paths** — that equivalence is what `test_langgraph_parity` (§4) guards.

---

## 4. Migration / rollout notes

- **Additive only.** `ChatPipelineState` stays `total=False`; new keys default absent/empty. No existing `PlaceholderResponse` field changes type or meaning (C10). The §2 fields are added incrementally as their owning nodes land (most depend on later slices: A5 for session, B1/C2 for enrichment & planning skill, C4/C5 for SPL/MITRE statuses).
- **Flag-gating.** Two **distinct** flags, neither flipped by this slice:
  - `langgraph_orchestration_enabled` (`config.py:241`, default `False`) selects **which path** runs (`routes_chat.py:47`).
  - `control_plane_enabled` (`config.py:243`, default `False`) gates **which features** run, including the entire trace. `node_trace` sits behind this flag.
  - Optional later flag `PIPELINE_SPLIT_ROUTING_NODES` (proposed in C2, default off) gates the node decomposition; out of scope here.
- **Backward compat (C10).** Frontend continues to consume `trace: response` in `ChatPanel.tsx`; new fields surface in the technical trace first. No frontend change is required for this spec.
- **Planned tests (describe only — none written this slice):**
  - **Per-node unit tests.** One test per `graph_node_*` with a fixture state in / asserted state out, including the appended `node_trace` record shape and that redaction masked any seeded secret. Fixtures should come from captured live runs, not hand-rolled (per CLAUDE.md LLM-app loop).
  - **`test_langgraph_parity`.** Run the same `ChatRequest` through `_build_live_chat_response_inner` and `run_chat_via_langgraph` and assert the resulting `node_trace` (and the rest of the response) match. This is the guard that the new per-node emission stays path-agnostic.
  - **Governance regression.** `./scripts/run_stage3_governance_regression.sh` must stay green (harness 6/6, 0 pytest failures) when the runtime lands — with the flag off, it must be unchanged.

---

## 5. Open questions / risks

1. **Per-node emission is a new pattern.** Today's trace is one post-hoc assembly (`build_control_plane_trace`, called once in finalize). Per-node `node_trace` requires each node to append a record as it runs — a real behavior addition, not an extension of the existing mechanism. The plan's C9 wording ("each node emits") implies it half-exists; it does not.
2. **Who owns the append?** Two options: (a) each `graph_node_*` builds and appends its own record (explicit, but 9+ edit sites and easy to drift), or (b) a thin decorator/wrapper around node functions captures a standardized summary. (b) is harder to make meaningful (summaries are node-specific) but enforces redaction centrally. Implementation decision deferred.
3. **`mitre_evidence_status` vs `mitre_decision`/`mitre_mappings` duplication.** Needs a single-source rule: is `mitre_evidence_status` derived-on-read from `mitre_decision`, or a stored aggregate? Recommend derived to avoid drift; confirm at C5.
4. **`execution_decision` overlap with `execution`/`human_review`.** Same risk; recommend a thin derived summary.
5. **`session_id`/`session_pins` depend on A5.** They cannot be populated until `ChatRequest` carries a session id and `chat/session_store.py` exists. Spec lists them; they are inert until A5 lands.
6. **`skill_enrichment` depends on later runtime integration.** Batch 2 added the offline `backend/app/use_cases/content_enrichment.json` metadata schema, but the chat state field remains a placeholder until Track B explicitly wires runtime use.
7. **`input_summary` granularity.** "Summary" is under-specified per node. Each node's exact summary keys should be fixed in the node's own unit test fixture when that node is implemented, not guessed here.

---

## Discrepancies (plan vs actual code)

- **Field count.** Plan (§G line 569) says `ChatPipelineState` is "~30 keys." Actual: **38 keys** (`pipeline.py:89–127`). Plan undercounts.
- **`answer_guard_result` is a duplicate.** C1 proposes it, but `answer_guard` (state field #24, response field `responses.py:399`) already exists. Should be dropped, not added.
- **`final_answer_validation` already exists as a response field.** C1 lists it as new; it is computed in finalize (`pipeline.py:664–672`) and emitted on the response (`responses.py:393`). Only its promotion to a *state key* is new.
- **C9 implies per-node emission already exists; it does not.** The current `control_plane_trace` is a single packaging-only post-hoc assembly (`control_plane_trace.py`), gated by `control_plane_enabled`. Per-node `node_trace` is a genuinely new emission pattern.
- **`graph/state.py:InvestigationState` is unused by chat.** Confirmed (`state.py:6–11`); a 4-field Pydantic stub (`trace_id`, `alert_id`, `evidence`, `route`) imported nowhere in the chat path. The chat state is the `TypedDict` in `pipeline.py`. The plan correctly notes this; flagged here so v2 work is not mistakenly applied to the stub.
