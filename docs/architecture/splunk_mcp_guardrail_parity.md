# Splunk MCP guardrail parity

COE reference: Splunk MCP Server app Guardrails tab (v1.2.1+ Timeout option).

| Guardrail | Splunk MCP Server (typical) | AI-SOC config | Parity |
|-----------|----------------------------|---------------|--------|
| Max events / rows | 1000 (default row limit) | `SPL_MAX_RESULT_LIMIT` default **100** | **Stricter** — OK |
| Max runtime | 60 seconds (Timeout guardrail) | `MCP_SEARCH_JOB_TIMEOUT_MS` default **120000** (120s) | **Looser** — recommend `60000` for production parity |
| Unsafe SPL | Server-side block | `SPL_BLOCKED_COMMANDS` + deterministic validator | Defense in depth |
| Global rate limit | Per 60s window (server) | Not mirrored in app | Operator tunes Splunk app; app does not burst past server |
| Connect timeout | N/A (HTTP) | `MCP_SERVER_*_CONNECT_TIMEOUT_SECONDS` / Settings `timeout_seconds` | Separate from search job timeout |
| Poll bounds | N/A | `MCP_MAX_POLLS_PER_CALL`, `MCP_SEARCH_POLL_INTERVAL_MS` | Connector-internal |

## Operator actions

1. Set `MCP_SEARCH_JOB_TIMEOUT_MS=60000` when aligning to Splunk Timeout guardrail.
2. Keep `SPL_MAX_RESULT_LIMIT` at or below Splunk default row limit unless COE approves higher caps.
3. Record Splunk app guardrail values in [`docs/operations/splunk_mcp_coe_configuration_worksheet.md`](../operations/splunk_mcp_coe_configuration_worksheet.md).
