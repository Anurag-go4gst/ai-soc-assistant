# Splunk MCP tool manifest (COE reference)

**Captured:** 2026-07-03  
**Source:** `coe_signed_reference` (Splunk MCP Server 1.2.1 official surface + repo `EXPECTED_CORE_TOOLS`)  
**JSON artifact (agent mode):** commit `docs/splunk_mcp_tool_manifest_2026-07-03.json` with identical content.

## Tools observed

| Tool | Namespace | Notes |
|------|-----------|-------|
| `splunk_run_query` | splunk_core | Alias: `run_splunk_query` |
| `splunk_run_saved_search` | splunk_core | Requires MCP ≥ 1.2.1 |
| `splunk_get_info` | splunk_core | Readiness |
| `splunk_get_indexes` | splunk_core | Discovery |
| `splunk_get_index_info` | splunk_core | Optional discovery |
| `splunk_get_metadata` | splunk_core | Alias: `get_splunk_metadata` |
| `splunk_get_knowledge_objects` | splunk_core | Expanded KO types — see KO policy doc |
| `splunk_get_user_info` | splunk_core | RBAC-gated in AI-SOC |
| `saia_*` | saia | Blocked unless SAIA explicitly enabled |

## Diff vs `EXPECTED_CORE_TOOLS`

- **Extra observed:** `splunk_run_saved_search` (optional; gated by `allow_saved_search`)
- **Aliases:** documented in `backend/app/splunk/capabilities.py` `TOOL_ALIASES`

## Guardrails (Splunk app)

- Timeout: 60s
- Default rows: 1000
- AI-SOC parity: [`splunk_mcp_guardrail_parity.md`](architecture/splunk_mcp_guardrail_parity.md)

## Related docs

- [`splunk_mcp_gap_register.md`](architecture/splunk_mcp_gap_register.md)
- [`splunk_mcp_coe_configuration_worksheet.md`](operations/splunk_mcp_coe_configuration_worksheet.md)
