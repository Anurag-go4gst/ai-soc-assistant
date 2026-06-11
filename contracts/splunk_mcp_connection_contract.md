# Splunk MCP Connection Contract (WS4c — readiness / COE hand-off)

**Status:** Draft readiness contract — `schema_confirmed=false` until COE S5 sign-off.  
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

## S5 first-read checklist (COE-gated — do not run in WS4c/d)

- [ ] COE signs binding target (7931 vs livehybrid vs hosted)
- [ ] URL, transport, auth validated in staging
- [ ] `capture_stage3m_s5_live_mcp_schema.py` records sample payloads
- [ ] Adapter mapping verified against live JSON
- [ ] Flags flipped only during controlled window; flipped back after capture
- [ ] `schema_confirmed=true` only after COE approval
