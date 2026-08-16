# Splunk MCP gap register (COE sign-off 2026-07-03)

Reference manifest: [`docs/splunk_mcp_tool_manifest_2026-07-03.json`](../splunk_mcp_tool_manifest_2026-07-03.json).

## Closed / aligned

| Area | Status |
|------|--------|
| Streamable HTTP + Bearer encrypted token | Settings UI + `connection_store` + `_StreamableHttpSearchTransport` |
| `tools/list` verification | `/settings/mcp/test` and `/settings/mcp/discover` via `_fetch_mcp_tools` |
| Core `splunk_*` search + discovery tools | Playbook + `EXPECTED_CORE_TOOLS` + allowlist |
| SAIA tools blocked by policy | Unless `saia_tools_enabled` and not air-gapped |
| Guardrail row cap | `SPL_MAX_RESULT_LIMIT` default 100 — stricter than Splunk 1000 |
| COE catalogue auto-execute policy | `docs/architecture/catalogue_auto_execute_policy.md` + kill-switch flag |

## Open gaps (tracked)

| ID | Gap | Mitigation / follow-on |
|----|-----|------------------------|
| G1 | Endpoint `/mcp` normalization was inconsistent | **Fixed 3.9:** `normalize_mcp_endpoint_url` shared by verify + transport |
| G2 | `allow_saved_search` not exposed in Settings UI | **Fixed 3.9:** checkbox in `McpSettingsPanel` |
| G3 | `splunk_run_saved_search` live `call_tool` blocked | **Fixed 4.4:** allowlist + transport tool name |
| G4 | Live discovery `call_tool` raises `NotImplementedError` | Deferred O4; Settings Discover works |
| G5 | SSL `mcp.conf ssl_verify` not in app | **Fixed for COE readiness:** `SPLUNK_MCP_TLS_VERIFY` / `MCP_SERVER_*_TLS_VERIFY` (default true) + optional CA path wired into streamable_http transport and Settings verify |
| G6 | Search timeout default 120s vs Splunk guardrail 60s | Documented in guardrail parity; operator may lower `MCP_SEARCH_JOB_TIMEOUT_MS` |
| G7 | Splunkbase app ID `7931` hardcoded | Confirm at connect; update env if Splunkbase ID changes |
| G8 | Token rotation / Invalidate Keys | Operator re-saves token in Settings after Splunk app rotation |
| G9 | `workflow_actions` KO type | Discovery-only; never execution via Splunk MCP in this architecture |
| G10 | Catalogue per-call HIL on live registry | **Fixed 4.5:** DG-5 exemption when `catalogue_auto_execute_eligible` |

## Saved-search lane

- Discovery + flags: `splunk_allow_run_saved_search`, gate branches, `connection_store` allowlist.
- Execution: wired in `splunk_mcp.py` when `allow_saved_search=true`.
- Catalogue binding: `catalogue_execution_map_v1.json` with `execution_mode=saved_search` (pilot rows TBD by COE inventory).
