# MCP Tool Routing (repo-true)

> **Scope correction (2026-08-10).** Two different MCP discovery mechanisms exist. Read this
> before using anything below.
>
> - **The multi-hop discovery loop described in this document is fenced off from the live
>   path.** `graph_node_evidence_planning` — the HUB that calls `initialize_loop` / `assess_loop`
>   — fails closed under canonical mode with `canonical_forbids_legacy_evidence_planning`
>   (`app/chat/pipeline.py`). It is not a node in the Resource Planner graph, which is the
>   production spine (`LANGGRAPH_ORCHESTRATION_ENABLED` defaults true). Consequently
>   `MAX_MCP_HOPS`, the chronology proposal, the data-silence advisory, the O5c recipe path and
>   the `evidence_observer` **do not run on a live `/chat` turn** today. Treat the walkthroughs
>   below as the design of that lane, not as current runtime behaviour.
> - **Bounded pre-SPL MCP discovery *is* live** when `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` is
>   true. `graph_node_workflow_spl` calls `graph_node_pre_spl_mcp_discovery` inline; the result
>   lands in `pipeline_dispatch["runtime_context"]["mcp_discovery_context"]` and feeds the SPL
>   plan compiler and saved-search preference. This is a single bounded step on the SPL path,
>   not a hop loop.
>
> So "MCP discovery never runs" is wrong, and "the discovery loop runs" is also wrong. The
> accurate statement is: *the legacy multi-hop loop is fenced; bounded pre-SPL discovery runs
> under dispatch-v2.* Gated execution via `evaluate_mcp_execution` is unaffected either way.
>
> **Update (2026-08-11, Plan 2 B1 = `RETIRE`).** The fenced lane is no longer merely unreachable:
> its unreachable call sites were removed (`55ae6a7`). `graph_node_evidence_planning` remains the
> evidence loop's only initializer and still fails closed under canonical mode, so `loop_initialized`
> is permanently false on a canonical turn. **`MAX_MCP_HOPS` was deliberately kept**, because it is
> *not* inert: it still bounds recipe call budgets at `evidence_loop.py:639`. Read it as a recipe
> budget bound, not as live hop semantics on `/chat`. The retired LLM planning rails (inline bridge,
> discard-only shadow runner, imperative guided-hybrid proposer) are gone as planning authorities;
> deterministic guided dispatch, validators and evidence collection remain. Bounded pre-SPL
> discovery under dispatch-v2 is untouched and stays live — it is a different mechanism from the
> retired legacy loop, and the two must not be conflated.


**Status:** Dev-facing reference for intent → MCP tool routing on the existing evidence-loop spine.  
**Canonical sources:** `backend/app/connectors/mcp/mcp_tool_playbook.json`, `backend/app/chat/evidence_loop.py`, `backend/app/orchestration/mcp_execution_gate.py`, `backend/app/connectors/mcp/mcp_tool_chronology.py`  
**Related:** `docs/architecture/catalogue_auto_execute_policy.md`, `contracts/splunk_mcp_connection_contract.md`, plan `plans/2026-07-04_1736_intent-mcp-tool-routing-hardening.md`

This document replaces the external MCP routing blueprint with repo-true node names, tool matrix, and walkthroughs. Legacy blueprint labels are mapped in the translation table below. It is the single doc owner for item 6’s insider-threat alternative text.

---

## Governance invariants

1. **LLM proposes chronology once per turn** — `plan_tool_chronology` / `review_proposed_tool_chronology` runs at evidence-planning first entry. The evidence-loop HUB (`assess_loop`) only routes among already-approved tools; it never invokes per-hop LLM tool selection.
2. **Deterministic wins** — playbook review drops blocked, RBAC-denied, intent-mismatched, and surface-pending tools. Default chronology is the fallback when the LLM proposal is empty or fully rejected.
3. **Execution stays gated** — `MCP_GLOBAL_EXECUTION_ENABLED` + per-server execution flags + SPL validation + HIL/COE. Candidate SPL is never executed; only approved `normalized_spl` reaches the gate.
4. **Read-only discovery auto-plans; search requires HIL** — discovery hops may be `planned` when execution is off; `splunk_run_query` and `splunk_run_saved_search` always pass through `evaluate_mcp_execution`.

---

## Blueprint → repo translation

External blueprint names are **not** runtime components. Use this table when reading older design docs:

| Blueprint label | Repo component | Module / constant |
|-----------------|----------------|-------------------|
| Node 5B (discovery hops) | Evidence-loop HUB discovery hops | `graph_node_evidence_planning` → `assess_loop`, `graph_node_mcp_call`, `MAX_MCP_HOPS=6` |
| Node 7C (search execution) | SPL chain + MCP execution gate | `_SPL_CHAIN` (`workflow_spl` → `spl_postprocessor` → `spl_source_resolve`) + `graph_node_execution` → `evaluate_mcp_execution` (`execution_intent=spl_search`) |
| Node 7D (saved search) | Saved-search branch in the same gate | `evaluate_mcp_execution` (`execution_intent=saved_search_execution`) |
| Validator B (saved-search policy) | Saved-search flags + name allowlist + HIL | `SPLUNK_ALLOW_RUN_SAVED_SEARCH`, `SPLUNK_ALLOWED_SAVED_SEARCHES`, `saved_search_name_allowed()`, `splunk_run_saved_search_require_hil` |

Live pipeline flow (control plane enabled):

```
query → intent/evidence plan → compose chronology (once)
  → [discovery loop: mcp_call ↔ evidence_planning HUB]
  → shadow_tail → workflow_spl / rag_early → spl_source_resolve
  → graph_node_execution (gate)
  → evidence_planning re-entry (post-execution) → context_finalize
```

---

## Repo-true tool matrix

Playbook schema version **2**. Seven **confirmed** air-gapped tools + one **surface-pending** entry. Saved search is **flag-gated outside the playbook** (no playbook row today).

| Tool | Playbook | Capability class | Key `produces` | Playbook `intents` | Execution posture |
|------|----------|------------------|----------------|-------------------|-------------------|
| `splunk_get_info` | yes | `metadata_discovery` | `server_version`, `server_name`, `readiness` | `system_health`, `connection_diagnostics` | Read-only; auto/planned discovery |
| `splunk_get_indexes` | yes | `metadata_discovery` | `accessible_indexes` | `source_mapping`, `scoping_data_availability` | Read-only; auto/planned discovery |
| `splunk_get_metadata` | yes | `metadata_discovery` | `sourcetypes`, `hosts`, `sources` | `data_silence_check`, `asset_visibility_audit`, `telemetry_verification` | Read-only; auto/planned discovery |
| `splunk_get_index_info` | yes (optional) | `metadata_discovery` | `index_detail` | `index_capacity_audit` | Read-only; only when target index known |
| `splunk_get_knowledge_objects` | yes (optional) | `metadata_discovery` | `saved_searches`, `macros`, `data_models`, … | `detection_rule_audit`, `knowledge_object_audit` | Read-only; auto/planned discovery |
| `splunk_get_user_info` | yes (on-demand) | `read_only_lookup` | `current_user_identity` | `session_capability_audit` | Read-only; RBAC-gated; not in default chronology |
| `splunk_run_query` | yes | `freeform_query_execution` | `result_rows` | `forensic_search`, `raw_event_analysis` | **HIL-gated** search; never in loop until SPL approved |
| `splunk_get_kv_store_collections` | yes | `metadata_discovery` | `kv_store_collections` | `threat_intel_feed_audit`, `asset_mapping_state` | **Surface-pending** — classified, not blocked, but dropped from chronology (`surface_unconfirmed`) until operator confirms live MCP exposes it |
| `splunk_run_saved_search` | **no playbook entry** | `saved_search_execution` | (connector rows) | — | **Flag-gated** (`SPLUNK_ALLOW_RUN_SAVED_SEARCH`) + name allowlist + HIL; see below |

### Blocked / out-of-scope tools

| Tool | Reason | Analyst alternative |
|------|--------|---------------------|
| `splunk_get_user_list` | `admin_or_sensitive_tool` — user enumeration / PII | Insider-threat and user-behavior asks use **`splunk_run_query`** over allowlisted auth/audit indexes. Index must appear in `SPL_ALLOWED_INDEXES`; internal indexes such as `_audit` require explicit allowlist + COE decision, not a default. |
| `saia_*` | `saia_conditional_blocked` | Governed template / validator SPL path only |

### Saved-search allowlists (three distinct layers)

Do not conflate these:

1. **Tool allowlist** — `MCP_SERVER_*_TOOL_ALLOWLIST` must include `splunk_run_saved_search` for the tool to be discoverable/selectable.
2. **Saved-search name allowlist** — `SPLUNK_ALLOWED_SAVED_SEARCHES` (comma-separated names) enforced by `saved_search_name_allowed()` in `app/orchestration/saved_search_allowlist.py`. Empty env list = deny all **unless** a name is bound in the catalogue map (DG-5 union).
3. **Catalogue COE binding allowlist** — `app/coverage/catalogue_execution_map_v1.json` / `catalogue_auto_execute_policy.md` binds verified `saved_search_name` values for catalogue-known auto-execute paths.

Gate order for saved search: global/server execution flags → `SPLUNK_ALLOW_RUN_SAVED_SEARCH` → **name allowlist** (before HIL card) → analyst confirmation → connector call.

---

## Intent → tool enforcement

- Playbook **`intents`** arrays (schema v2) map analyst intent classes to tools.
- LLM-proposed chronology: `_evaluate_tool_step` drops tools with no intent overlap (`intent_mismatch_dropped`). Deterministic default chronology is **exempt** from intent filtering.
- **`phase: surface_pending`** (e.g. KV store): dropped with `surface_unconfirmed`; not in `default_chronology`, `plan_splunk_discovery_calls()`, or `AIRGAPPED_TOOLS`.

---

## Data-silence advisory (not a circuit breaker)

When `splunk_get_metadata` shows **zero footprint** for scoped entity/index/timeframe (`totalCount == 0`, empty hosts for target), the loop emits a **data-silence advisory** before the gated `splunk_run_query` hop:

- Loop: `assess_loop` → `ROUTE_HUMAN_REVIEW`, reason contains `data_silence`; annotates `state["data_silence_advisory"]`.
- Gate: `evaluate_mcp_execution` blocks search HIL until analyst chooses **proceed anyway**, **broaden**, or **halt**.
- Metadata window may lag the proposed search window — advisory only; post-execution empty/broaden flows unchanged.

---

## Example walkthroughs

### 1. Firewall “log death” (HIL + allowlist caveat)

**Ask:** “Why did firewall logs stop on `fw-edge-01` in the last hour?”

1. Intent → `data_silence_check` / hunt; chronology (deterministic or LLM-reviewed): `get_info` → `get_indexes` → `get_metadata` (optional `get_index_info` if index pinned).
2. Metadata hop shows zero `totalCount` for `fw-edge-01` → **data-silence advisory HIL** (not hard halt).
3. Analyst **proceed anyway** → SPL chain produces candidate → validation → gate.
4. **HIL:** confirm normalized SPL on `splunk_run_query`.
5. **Allowlist caveat:** if the hunt later needs a **saved search**, the name must be on `SPLUNK_ALLOWED_SAVED_SEARCHES` or catalogue-bound — tool flag alone is insufficient.

### 2. Rogue asset (RAG before MCP + honest capability gap)

**Ask:** “Is asset `rogue-laptop-17` in CMDB and what did we see in Splunk?”

1. Evidence plan: `needs_rag` + MCP allowed → dispatch runs **`rag_early`** before SPL/MCP when `rag_phase=pre_mcp`.
2. Discovery chronology: indexes → metadata for scoped host.
3. **`asset_context` / `cmdb`** are **unservable** in Splunk MCP — loop returns **`ROUTE_CAPABILITY_GAP`** / honest degrade; answer cites RAG + MCP metadata only, not fabricated CMDB rows.
4. If SPL hunt proceeds: gated `run_query` after validation + HIL.

### 3. Insider / jdoe activity (user enumeration blocked)

**Ask:** “Show jdoe’s privileged activity this week — any insider-threat pattern?”

1. **User-list enumeration is never proposed** — see blocked tools table (`admin_or_sensitive_tool`).
2. Chronology: `get_knowledge_objects` (owner-filtered saved searches/macros) → gated **`splunk_run_query`** on allowlisted **auth/audit** index (must be in `SPL_ALLOWED_INDEXES`; `_audit` not default).
3. Intent overlap keeps knowledge-object + forensic tools; user-list proposals dropped.
4. Gate: SPL validation → data-silence check if metadata empty → execution confirmation HIL → mock/live search.

### 4. Negative control — data silence as advisory

Same as walkthrough 1 when metadata is empty: the turn **does not terminate**; analyst card offers proceed/broaden/halt. Finalize may include an honest negative if search still returns zero rows after proceed.

---

## Phase 2: evidence observer and governed ReAct

Governed evidence observation (plan items 8–13, landed): a single small-model **`evidence_observer`** sidecar reads bounded sanitized MCP rows per turn (hard cap: one call), emits grounded JSON observations, and never overrides deterministic facts, severity, MITRE, or actions.

- **Input guard:** rows pass the prompt-injection filter first; instruction-like rows are withheld (`[row withheld: injection_suspect]`) with stable indexes. Prompt = sanitized analyst question + CanonicalFacts (entity/timeframe) + numbered rows — never RAG chunks, prior LLM output, or workflow internals.
- **Output guard:** deterministic grounding check (`app/synthesis/observation_grounding.py`) — every cited `row_refs` index must exist, every entity/number in a claim must appear in the cited rows; failures drop with `grounding_failed`, never silently. Surviving observations render only in the advisory card section, provenance `llm_observation`.
- **Governed ReAct:** the observer may propose `next_hop_hint` — on the chronology path only, an unrun read-only playbook tool may be appended (intent-overlap + budget + not-execution-class checks in `_evaluate_tool_step`); recipe turns record `observer_hint_ignored_recipe_turn`. LLM reasons and proposes; the deterministic HUB alone acts. Execution tools are un-hintable by construction.
- **Wiring:** `graph_node_evidence_planning` re-entry (both imperative and LangGraph paths); rows from post-HIL `execution` or the terminal discovery hop. Budget: counted inside `TurnLlmBudget`, skip with `skipped_reason="budget"`, deterministic answer never blocked.
- **Telemetry:** per-call record (latency, tokens, grounded/dropped counts, hint disposition, withheld-row count) into `control_plane_trace` + `ai_trace_runs`; raw rows and raw model output are never persisted.
- **Gates:** `ai_soc_llm_final_synthesis_enabled` + `ai_soc_llm_live_synthesis_enabled` + `evidence_observer` role availability (`ROLE_DEFAULTS`/`ROLE_ENV_MAP`). Repo defaults off; live posture enables both. EC/demo never invokes the observer.

---

## Key files

| Concern | Location |
|---------|----------|
| Playbook | `backend/app/connectors/mcp/mcp_tool_playbook.json` |
| Chronology review | `backend/app/connectors/mcp/mcp_tool_chronology.py` |
| Loop HUB | `backend/app/chat/evidence_loop.py` |
| Pipeline nodes | `backend/app/chat/pipeline.py`, `backend/app/graph/chat_workflow.py` |
| Execution gate | `backend/app/orchestration/mcp_execution_gate.py` |
| Data silence | `backend/app/orchestration/data_silence_advisory.py` |
| Saved-search names | `backend/app/orchestration/saved_search_allowlist.py` |
| Discovery plan records | `backend/app/connectors/mcp/splunk_mcp_readiness.py` (`plan_splunk_discovery_calls`) |
| SPL dispatch chain | `backend/app/chat/pipeline_dispatch_builder.py` (`_SPL_CHAIN`) |
