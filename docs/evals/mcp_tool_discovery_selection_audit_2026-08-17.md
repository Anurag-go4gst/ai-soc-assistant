# MCP Tool Discovery & Selection Audit — 2026-08-17

> **Historical audit — superseded by PR #144**
>
> This document captures the MCP tool discovery/selection state before the
> effective catalog, exact-call AUTH0 closure, capability resolver, and
> production `/chat` enforcement were completed.
>
> Current implementation after PR #144:
> - Effective MCP catalog is enforced in `/chat`
> - EVENT_SEARCH → `splunk_run_query`
> - SAVED_SEARCH_EXECUTION → `splunk_run_saved_search`
> - exact-call AUTH0 is mandatory for user-triggered live MCP execution
> - deterministic capability-preserving fallback is enforced
> - remaining metadata capabilities are `PLANNING_SEMANTIC_GAP`
> - `LIVE_MCP_PROVEN=false`
>
> Do not use this file as the current operational status.

Read-only investigation. Worktree: `/var/www/ai-soc-master` (master @ `af93fb3`).
No architecture.md change, no MCP implementation change, no `/chat` call,
`MCP_GLOBAL_EXECUTION_ENABLED` left `false` throughout, no T4 tuning performed
as production decision (worktree-local `.env` only, unblock-only per commit
note in-file).

## Preceding step: commit range check

Frozen COE qualification candidate: `bf7c30468454fb20ceb6eeb1eda621b278523933`
Current master: `af93fb3`

```
git log --oneline --decorate bf7c30468454fb20ceb6eeb1eda621b278523933..af93fb3
af93fb3 docs(races): mark Experience Center plan done after #143 merge
d4f9210 Merge pull request #143 from Anurag-go4gst/feat/races-experience-center
e17a3e5 races(G5): record Draft PR #143 review evidence
6c88828 races(review): close pre-PR isolation and UX defects
68f9a1c races(G1-G4): record isolation evidence and close D-G
9f2e2b5 races(F1-F3): polish three-layer Experience Center UX
23c4a60 races(E1-E4): cover S5-S7 journeys and lab picker
6a3af34 races(D1-D3): add S2-S4 flagships and shared EC packs
3eed296 races(C1-C3): add S1 governed Splunk investigation flagship
ec046bd races(B1-B5): add ExperienceCenterResponse and /scenarios workspace
8269ce4 races(L0-A8): freeze live path and clean EC contradictions
```

All 9 commits are `races` EC scenario work (PR #143). Diff against
`backend/app/mcp`, `backend/app/connectors`, `mcp_execution_gate.py`,
`spl_validator.py` between `bf7c304` and `af93fb3`: **empty**. `af93fb3` is
safe for MCP investigation — no core coupling from RACES work. Master not
reset.

## `--check` result

```
STATUS: READY_FOR_COE_CONFIGURATION
MCP_CONFIG_READY: true
MCP_CONTRACT_READY: true
LIVE_MCP_PROVEN: false / UNPROVEN
MISSING: []
```

Reached only after this worktree's local `.env` `AI_SOC_ENV_PROFILE`
`coe`→`development` + `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120`
(sourced verbatim from `env/profiles/development.env.example`'s own default,
tagged in-file as unblock-only, not a COE SLO decision). MCP block of `.env`
(registry mode, global execution `false`) left untouched. `.env` is
worktree-local and gitignored; no committed file touched.

`--live` is structurally inert on any VPS: even with
`AI_SOC_COE_LIVE_MCP_QUALIFICATION=1` it hardcodes `mcp_called: False` and
`live_status: COE_ONLY_PENDING` — real handshake is explicitly scoped to run
"on the COE Splunk MCP Server, not this VPS" (code comment,
`coe_qualification.py::_live_gate`).

## 1. CURRENT_SELECTION_PATH

| # | FILE | FUNCTION | INPUT | OUTPUT | AUTHORITY |
|---|---|---|---|---|---|
| 1 | `backend/app/planner/mcp_specialist.py::_fill_blank_proposals` (L179-208) | fills blank `execution_intent` on already-authorized step: `"spl_search"` if `purpose=="mcp_execution"` else `"metadata_discovery"` | DETERMINISTIC, advisory-only |
| 2 | `backend/app/chat/pipeline.py:3039` | `execution_intent = "spl_search"` hardcoded default; exception L3042-3043 for `saved_search_execution` | CONFIG/HARDCODED |
| 3 | `backend/app/orchestration/mcp_execution_gate.py::evaluate_mcp_execution` (L59-128) | selected_skill, workflow_plan, execution_intent, spl_validation, requested_mcp_server/tool | calls `select_mcp_tool()` | ORCHESTRATION gate |
| 4 | `backend/app/orchestration/mcp_tool_selector.py::select_mcp_tool` (L17-94) | execution_intent, `registry.servers[*].discovered_tools`, `user_requested_mcp_tool`, `rbac_role` | `selected_mcp_server`, `selected_mcp_tool` or `requires_human_review` | **DETERMINISTIC — actual decision point** |
| 5 | `backend/app/connectors/mcp/registry.py::load_mcp_registry_status` → `_discovered_tools_for_config` (L259-264) | `MCP_SERVER_<NAME>_TOOL_ALLOWLIST` env CSV | `discovered_tools` list (misnomer, see §4) | CONFIG (static `.env`) |
| 6 | `backend/app/orchestration/mcp_execution_gate.py:310` | `selection["selected_mcp_tool"]` string | `connector.call_tool(tool_name, arguments, server_name)` | terminal dispatch |
| 7 | `backend/app/connectors/mcp/splunk_mcp.py::call_tool` (L126) | tool_name | allowlist re-check then lifecycle execution | DETERMINISTIC — second gate |

**Can an LLM directly provide an arbitrary MCP tool name that becomes executable? NO.**

- `llm_tool_recommendation` param exists on `select_mcp_tool`/`evaluate_mcp_execution` but only `tool_category` is read and discarded (`mcp_tool_selector.py:44`) — never influences `selected_mcp_tool`.
- `pipeline.py` never populates `llm_tool_recommendation` — dead parameter, zero wiring found repo-wide beyond the two signatures.
- `requested_mcp_tool` comes from `request.requested_mcp_tool` (API request object / analyst preference), confirmed at `pipeline.py:3040,3212,6048,6141` — not LLM output.
- Any requested tool must pass `_tool_names_equivalent()` against config-sourced `discovered_tools` (L58-65), plus `_tool_blocked`, `_tool_matches_intent`, RBAC.
- Re-checked a second time inside `SplunkMcpConnector.call_tool` (`is_disallowed_tool`/`is_allowed_read_tool`).

## 2. CURRENT_TOOL_CATALOG

Source of truth: `discovery.py::SPLUNK_TOOL_CLASSIFICATIONS` (static dict) +
`.env` `MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST` (7 names, this worktree).

| tool | purpose | allowed/disallowed | discovery/execution | schema known? | needs `normalized_spl`? | needs AUTH0? | caller(s) |
|---|---|---|---|---|---|---|---|
| `splunk_run_query` | run validated SPL | allowed (`spl_search`) | execution | no | yes | yes | default path, `execute_validated_spl` |
| `splunk_run_saved_search` | run allowlisted saved search | allowed, gated by `splunk_allow_run_saved_search` + `saved_search_name_allowed()` | execution | no | no (saved-search name) | yes | `saved_search_execution` intent |
| `splunk_get_info` | server identity/version | allowed (discovery_context) | discovery-only | no | no | — | no `execution_intent` maps to it today |
| `splunk_get_indexes` | list indexes | allowed (metadata_lookup) | discovery-only | no | no | — | `metadata_discovery` intent |
| `splunk_get_index_info` | one index detail | allowed (metadata_lookup) | discovery-only | no | no | — | `metadata_discovery` intent |
| `splunk_get_metadata` | host/source/sourcetype metadata | allowed (metadata_lookup) | discovery-only | no | no | — | `metadata_discovery` intent |
| `splunk_get_user_info` | auth'd user context | allowed (identity_lookup, rbac_gated) | discovery-only | no | no | — | `identity_lookup`, name-pinned |
| `splunk_get_knowledge_objects` | saved-search/dashboard metadata | allowed (knowledge_object_context→metadata_lookup) | discovery-only | no | no | — | `metadata_discovery` intent |
| `splunk_get_kv_store_collections` | KV store list | classified but not in `.env` allowlist | n/a | no | no | — | never selectable |
| `splunk_get_user_list` | list all users | `admin_or_sensitive` → blocked | n/a | no | no | — | none |
| `saia_*` (4 tools) | SAIA generative | blocked (`saia_conditional_blocked`) | n/a | no | no | — | none |

Not in `.env` allowlist ⇒ never enters `discovered_tools` ⇒ never selectable
regardless of classification-table entry. List is code's closed universe,
**not empirically validated against a real server**.

## 3. SERVER_DISCOVERY_PATH

`SplunkMcpConnector.handshake_initialize_and_list_tools()`
(`splunk_mcp.py:111`) → `_StreamableHttpToolTransport.handshake()` (L260-283):
`initialize` then `tools/list`, two JSON-RPC calls, one bearer/TLS session.
Parses `result.tools[*].name` only (`_tool_names_from_list_result`,
L349-361) — description, inputSchema, annotations/read-write hints are never
extracted, even though `McpToolDescriptor.input_schema` field exists
(`discovery.py:61`) and is never populated anywhere. Not called from network
this session (no credentials configured, not requested).

## 4. CONFIGURED_VS_DISCOVERED_GAP

**No intersection is computed. Core finding.**

`registry.py::_discovered_tools_for_config()` builds `discovered_tools`
entirely from `.env` `TOOL_ALLOWLIST` — never from a real `tools/list` call.
"Discovered" means "configured" in current code. The real handshake path
(§3) is unconnected to the selection pipeline.

Consequences:
- **Approved tool absent from server**: undetected until a live call fails (`tool_not_found`, `splunk_mcp.py:309-310/321-322`).
- **Server exposes unknown extra tool**: never surfaces — selection never sees real server tool list.
- **inputSchema/description changes**: irrelevant — never read; classification keys off tool *name* only.
- **Tool disappears server-side**: same as "absent."
- **Server advertises write/admin tool**: cannot become executable even if wired in — unknown Splunk tool names default-blocked (`unknown_tool_not_allowlisted`) plus static token-blocklists catch common admin/write patterns. Safe by default, just not wired.

## 5. CURRENT_TOOL_SELECTION_LOGIC

| Goal | Capability tag | Tool chosen | Why |
|---|---|---|---|
| A. search events | `spl_search` | `splunk_run_query` | exact capability match; also pipeline's hardcoded default |
| B. available indexes | `metadata_discovery` | first eligible with `capability=="metadata_lookup"` | bucket too coarse to target "indexes" specifically |
| C. index metadata | `metadata_discovery` | same bucket as B | `splunk_get_index_info` not distinguished from `splunk_get_indexes` |
| D. Splunk metadata | `metadata_discovery` | same bucket | same |
| E. user context | `identity_lookup` | `splunk_get_user_info` | name-pinned exception — only capability with hardcoded tool name |
| F. saved searches/knowledge objects | `metadata_discovery` | same bucket as B/C/D | `knowledge_object_discovery` also maps into `metadata_discovery` |

Selection is capability-based within a hardcoded, coarse 4-value
`execution_intent` taxonomy (`spl_search`, `saved_search_execution`,
`metadata_discovery`, `identity_lookup`), defaulting to `splunk_run_query`
almost everywhere because `execution_intent` is hardcoded `"spl_search"` at
the one live call site.

## 6. CAPABILITY_MODEL_RECOMMENDATION — ALIGNS

Proposed model (capability → deterministic resolve → approved discovered
tool) does not conflict with frozen `architecture.md`. `architecture.md:1178-
1200` ("New MCP tools") already states: *"registers its tools and capability
metadata with existing registries. Resource/action planning may then
reference those registered capabilities. No orchestration redesign is
required merely because a new MCP server is connected."* Current
`discovery.py::classify_mcp_tool` capability tagging is a partial
implementation of exactly this pattern. Gap is on the request side: nothing
upstream produces the finer six-way capability signal; `execution_intent` is
hardcoded almost everywhere (§1, §5).

**Verdict: ALIGNS** — extension of an existing, partially-built mechanism,
not a new architecture, not a conflict.

## 7. TOOL_REFRESH_RECOMMENDATION

**Cached with controlled/operator-triggered refresh** (existing
`--check`/`--live` qualification pattern), not per-request, not implicit at
app startup.

- Security: per-request `tools/list` expands attack surface, isn't gated by `MCP_GLOBAL_EXECUTION_ENABLED` today.
- Latency: adds a network round-trip inside budget-constrained `/chat` turns.
- Determinism: `select_mcp_tool` must behave identically regardless of transient server state.
- Air-gapped COE: network calls must be operator-initiated, consistent with `--live`'s explicit opt-in.
- Schema/server drift: caught by periodic operator-run qualification, diffed against static allowlist before promotion, never silently absorbed.

New server tools must never become executable merely because `tools/list`
returns them — any future intersection logic must be `SERVER_DISCOVERED ∩
LOCAL_APPROVED_ALLOWLIST`, never `SERVER_DISCOVERED` alone.

## 8. TOOL_TEST_MATRIX

| tool | minimal safe input | expected output | risk | live Splunk? | AUTH0? | /chat? |
|---|---|---|---|---|---|---|
| handshake (`initialize`+`tools/list`) | none | `{status, initialized, initialize_ok, tools:[names]}` | none | yes | no | no — CONNECTIVITY TEST |
| `splunk_run_query` | `search index=<allowed> earliest=-15m latest=now \| head 1` | rows/empty, `evidence_source: live` | low | yes | yes | yes — PRODUCTION GOVERNED /chat TEST |
| `splunk_get_indexes` | none | index name list | none | yes | no | TOOL CONTRACT TEST (direct `call_tool`) |
| `splunk_get_index_info` | one known index name | index detail dict | none | yes | no | TOOL CONTRACT TEST |
| `splunk_get_metadata` | none/bounded query | host/source/sourcetype metadata | none | yes | no | TOOL CONTRACT TEST |
| `splunk_get_user_info` | none | authenticated user identity | none | yes | no | TOOL CONTRACT TEST |
| `splunk_get_knowledge_objects` | none | saved-search/dashboard metadata | none | yes | no | TOOL CONTRACT TEST |
| `splunk_run_saved_search` | one allowlisted saved-search name | rows | low | yes | yes | yes — PRODUCTION GOVERNED /chat TEST |

Discovery tools currently `raise NotImplementedError("Splunk MCP live
discovery execution is out of v1 scope (O4)")` inside `call_tool`
(`splunk_mcp.py:141`) — **classified allowed but not actually executable
today.**

## 9. ARCHITECTURE_IMPACT

No conflict with frozen `architecture.md`. Capability-registry pattern it
prescribes is already half-built in `discovery.py`/`registry.py`; closing
gaps in §4/§5/§8 is additive engineering inside the existing seam, not a
redesign.

## 10. P0/P1/P2/P3 FINDINGS

- **P0** — `registry.py::_discovered_tools_for_config` names its output `discovered_tools` but it is 100% config-sourced; real `tools/list` is never intersected with it anywhere in the runtime selection path. Server-side tool drift/removal undetected until a live call fails mid-turn.
- **P1** — `execution_intent` hardcoded `"spl_search"` at the sole live call site (`pipeline.py:3039`); the 4-way taxonomy in `mcp_tool_selector.py` exists but is almost never driven by anything except the coarse binary guess in `mcp_specialist.py::_fill_blank_proposals`. Goals B/C/D/F collapse into one bucket with no name-level distinction beyond list order.
- **P1** — Discovery tools classified `allowed` but hit `NotImplementedError` in `call_tool` — allowlisted-but-nonfunctional contract mismatch.
- **P2** — `input_schema` field on `McpToolDescriptor` is dead weight — always empty dict, never populated, never validated against.
- **P3** — No standalone CLI wraps `handshake_initialize_and_list_tools()` for operator use.

## Answer

**"Do we currently have a robust deterministic mechanism for choosing the
right MCP tool when multiple Splunk MCP tools are available?"**

**PARTIAL.** Safety boundary is robust and deterministic (closed allowlist,
no LLM tool-name injection possible, blocked-by-default unknowns, RBAC
re-check, second allowlist re-check inside connector). Selection *quality*
mechanism is thin: hardcoded coarse 4-value `execution_intent` that almost
never varies from `spl_search` in practice, no verified link to the real
server's advertised tool set, cannot distinguish between the 4 read-only
discovery tools beyond one name-pinned special case
(`splunk_get_user_info`). Safe, not yet capability-precise.

---
No code, `.env.example`, or committed files outside this doc changed.
`architecture.md` not modified. Cursor RACES worktree untouched. Global
execution stayed `false` throughout. No live network call made (no
credentials present).
