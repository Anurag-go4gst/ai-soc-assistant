# Splunk MCP Connection Contract (WS4c — readiness / COE hand-off)

**Status:** Adapter implemented (Step 3); `schema_confirmed=false` until operator staging smoke sign-off. **LIVE_MCP_PROVEN is not claimed.** COE qualification `--check` may reach `READY_FOR_COE_CONFIGURATION` without a live server.  
**Date:** 2026-06-10  
**Scope:** Read-only Splunk search via governed MCP adapter. No live execution in WS4c/d.

---

## Binding target (COE decision — do not pick in code)

| Candidate | Notes |
|-----------|--------|
| Splunkbase App **7931** | First target named in project governance (`CLAUDE.md`) |
| [livehybrid/splunk-mcp](https://github.com/livehybrid/splunk-mcp) | Hypothesis schema for `search_splunk` tool args |
| Splunkbase App **8747** AI Workbench | Consumer/host reference only |

**Canonical server id in AI-SOC registry:** `splunk` (type `splunk`).

---

## Allowed read tool

| Tool | Purpose | Status |
|------|---------|--------|
| `splunk.search` | Bounded event search from **validated** `normalized_spl` only | Read-only; primary execution tool |

**Registry aliases (internal):** `mcp_tool:search_splunk`, `search_splunk`, `splunk_run_query` (mock/fixture path).

**Transport model (locked):** Splunk search is **asynchronous**. The connector implements submit → bounded poll → fetch **inside** one `call_tool` invocation. The execution gate still performs one logical investigation call; poll iterations are connector-internal and bounded by `MCP_MAX_POLLS_PER_CALL` / `MCP_SEARCH_JOB_TIMEOUT_MS` (see plan Appendix A.12).

---

## Disallowed / mutating tools (must remain blocked)

- KV store: `create_kvstore_collection`, `delete_kvstore_collection`, `list_kvstore_collections` (mutations)
- SAIA / generative / assistant / write / admin / `outputlookup` / `sendemail` / `delete` SPL operators in executed queries
- Any tool not on the deterministic allowlist at connector boundary

---

## Required inputs (`splunk.search`)

| Field | Required | Source / constraint |
|-------|----------|---------------------|
| `search_query` | Yes | `spl_validation.normalized_spl` only — never `candidate_spl` |
| `earliest_time` | Yes | Bounded; default `SPL_DEFAULT_EARLIEST` when absent from validated SPL |
| `latest_time` | Yes | Bounded; default `SPL_DEFAULT_LATEST` |
| `max_results` | Yes | `<= SPL_MAX_RESULT_LIMIT` |
| `correlation_id` / `request_id` | When available | `trace_id` from `/chat` turn |

---

## Required preconditions (all must pass before real execution — S5 only)

1. `spl_validation.approved == true` and non-null `normalized_spl`
2. SPL passed deterministic validator (indexes, sourcetypes, commands, time window, row cap)
3. Bounded time range and result count (no raw dump)
4. Human-in-the-loop / COE approval for execution when policy requires
5. `MCP_GLOBAL_EXECUTION_ENABLED=true` **and** per-server execution flag enabled
6. Connector configured, healthy, and `availability` not `blocked`
7. MITRE `evidence_supported` requires source-grounded execution evidence — metadata-only contexts stay `candidate` / `requires_validation`

**WS4c/d default:** all real execution preconditions fail closed; adapter may emit `planned_tool_call` or `blocked_tool_call` only.

---

## Output envelope (internal — `SplunkResultEnvelope` + `SourceEvidence`)

| Field | Description |
|-------|-------------|
| `status` | `ok` \| `empty` \| `error` \| `timeout` \| `blocked` |
| `row_count` | Rows returned after server + policy caps |
| `fields` | Column names (capped) |
| `rows` | Preview rows (capped; minimized + injection-scanned) |
| `warnings` | Truncation, minimization, injection flags |
| `source_type` | `splunk_mcp` |
| `collection_status` | `collected` when executed with valid envelope; otherwise `blocked` / `unavailable` |
| `error_type` | When failed: `tool_unavailable`, `connector_not_configured`, `validation_failed`, `timeout`, `permission_denied`, `schema_mismatch`, etc. |

Executed with **zero rows** → valid **negative result** (`collection_status=collected`, `row_count=0`), not `insufficient_evidence`.

---

## Failure modes (adapter must classify honestly)

| Mode | User-facing behavior |
|------|----------------------|
| Tool unavailable | Blocked plan; review-required; no execution claim |
| Connector not configured | Blocked plan; configuration message |
| Validation failed | No MCP call; SPL review only |
| Timeout | Review-required; partial/error envelope |
| Empty result | Honest “no matching rows”; no compromise/no-compromise overclaim |
| Partial result | Review-required; truncated metadata in envelope |
| Schema mismatch | Block evidence-supported MITRE; review-required |
| Permission denied | Blocked; HIL required |

---

## Authority rules (non-negotiable)

- Tool selection is **deterministic**; user-requested server/tool are preferences only
- LLM tool recommendations are **advisory** and cannot authorize MCP
- LLM must **never** call MCP directly
- `candidate_spl` is **never** executable
- LangGraph orchestration cutover is **out of scope**

---

## Async search job lifecycle (Step 3 — implemented)

Splunk searches exceed HTTP timeouts, so `splunk_run_query` is async at the
transport layer. The execution gate calls `call_tool` **once**; the connector
(`splunk_mcp.py` → `splunk_search_lifecycle.py`) runs submit → bounded poll →
fetch internally. A submit + N polls is **one** logical investigation call.

Bounds (config, server-capped): `MCP_MAX_POLLS_PER_CALL=60`,
`MCP_SEARCH_JOB_TIMEOUT_MS=120000`, `MCP_SEARCH_POLL_INTERVAL_MS=2000`.

Normalized job outcomes → gate disposition:

| Job state | Payload `status` | Gate result |
|-----------|------------------|-------------|
| completed, rows > 0 | `ok` | executed (evidence) |
| completed, 0 rows | `ok` | executed, honest negative |
| failed / error | `failed` | failed + admin review |
| timed out / max polls | `timeout` | failed + admin review |
| denied / forbidden | `denied` | blocked + policy review |
| unknown state / bad rows | `schema_invalid` | failed + admin review |

Canonical tool name `splunk_run_query`; aliases `search_splunk` / `splunk.search`
normalize at the boundary. Wire framing (`tools/call` JSON-RPC over
streamable_http) is verified at first live connect — if the deployment exposes a
submit/poll job protocol instead of inline rows, only
`_StreamableHttpSearchTransport` changes; gate, lifecycle, and envelope mapping
stay the same.

## Externally supplied COE values (existing names)

| COE need | Repository field |
|----------|------------------|
| MCP mode | `MCP_MODE` (`mock` default; `registry` for live) |
| Endpoint | `SPLUNK_MCP_BASE_URL` / `MCP_SERVER_SPLUNK_SOC_URL` |
| Transport | `MCP_SERVER_SPLUNK_SOC_TRANSPORT=streamable_http` |
| Bearer token / secret reference | `SPLUNK_MCP_TOKEN` or `SPLUNK_MCP_TOKEN_FILE` / `MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN[_FILE]` |
| TLS verification | `SPLUNK_MCP_TLS_VERIFY` / `MCP_SERVER_SPLUNK_SOC_TLS_VERIFY` (default true) |
| Trusted CA path | `SPLUNK_MCP_CA_CERT_PATH` / `MCP_SERVER_SPLUNK_SOC_CA_CERT_PATH` |
| Connect timeout | `SPLUNK_MCP_CONNECT_TIMEOUT_SECONDS` / `MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS` |
| Request/tool timeout | `MCP_SEARCH_JOB_TIMEOUT_MS` |
| Row limit | `SPL_MAX_RESULT_LIMIT` |
| Allowed tools | `MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST` / `SPLUNK_ALLOWED_CORE_TOOLS` |
| Trace identity | `correlation_id` / `request_id` / `trace_id` |

Do not add duplicate config to match these labels. Do not introduce `npx` / `mcp-remote`.

## Splunk-side COE prerequisites (record, do not implement locally)

- Splunk MCP Server app installed on Search Head / SHC
- Splunk token authentication enabled
- service identity has `mcp_tool_execute`
- `mcp_tool_admin` only if administration/token/tool-management is required
- encrypted MCP token generated by Splunk MCP Server
- MCP endpoint supplied by the Splunk MCP Server app
- required read-only tools enabled server-side
- server guardrails/limits known

## Qualification probe

```bash
PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --check
# COE only (do not run from the VPS):
AI_SOC_COE_LIVE_MCP_QUALIFICATION=1 PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --live
```

`--check` never connects. `--live` is refused unless the COE opt-in env is set, and still does not claim `LIVE_MCP_PROVEN` from this host.

## Go-live checklist (operator-owned — no external COE)

- [ ] `cp .env.splunk-live.example .env`
- [ ] Set `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN` (service-account bearer)
- [ ] Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` to the deployment
- [ ] Staging smoke: run one approved search; verify submit/poll/fetch + envelope
- [ ] Verify HIL gate fires (analyst confirm before each search)
- [ ] `schema_confirmed=true` **after** the staging smoke (operator sign-off)
- [ ] No code change required — restart backend
