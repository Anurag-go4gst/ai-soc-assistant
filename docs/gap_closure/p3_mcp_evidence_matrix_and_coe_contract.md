# P3 — MCP evidence-needs matrix and COE adapter prep

**Status:** Started on branch `stage/p3-mcp-evidence-matrix`.

## Goal

Provide a report-first mapping from governed operations and the 105-question
runtime map to MCP evidence needs and deterministic tool candidates. This does
not enable real MCP execution.

## Deliverables

| ID | Item | Location |
|----|------|----------|
| P3-7 | Operation / promoted pattern evidence-needs matrix | `app/orchestration/mcp_evidence_matrix.py` |
| P3-8 | Non-promoted 105-row report estimates | `build_question_mcp_evidence_report()` |
| P3-9 | Deterministic evidence need → MCP tool mapping | `app/orchestration/evidence_mcp_mapping.py` |
| P3-COE | Adapter contract checklist | This document |

## Boundaries

- `mcp_called=false` and `execution_authorized=false` in the report.
- LLM tool suggestions are recorded as ignored advisory input.
- `splunk_run_query` is only a gated-after-validation candidate.
- Local lookup and detection registry evidence needs are not MCP execution.
- Real Splunk MCP remains blocked until the COE contract below is complete.

## COE MCP Contract Required Before Live Adapter

| Area | Required input |
|------|----------------|
| Endpoint | MCP URL, environment, and network path |
| Transport | streamable HTTP / SSE / stdio contract |
| Auth | auth mode, secret owner, rotation process |
| Tool names | exact safe tool names for metadata and search |
| Arguments | JSON schema for metadata calls and SPL search |
| Result schema | row envelope, field limits, preview caps, sensitivity flags |
| Approval | human approval workflow and rollback owner |
| Policy | saved-search, write/admin, SAIA/generative tool policy |
| Telemetry | audit fields required by SOC/COE |

## When MCP Becomes Live

Real Splunk MCP can move from report/mock to live read execution only when all
of these gates pass:

1. COE approves the contract above, including rollback owner and audit fields.
2. Registry mode is configured: `MCP_MODE=registry`, `MCP_SERVERS=splunk_soc`,
   `MCP_DEFAULT_SERVER=splunk_soc`.
3. The Splunk MCP server is enabled and configured with endpoint/transport/auth:
   `MCP_SERVER_SPLUNK_SOC_ENABLED=true`, `TYPE=splunk`, `TRANSPORT`,
   `URL` or `COMMAND`, `AUTH_MODE`, and non-committed credentials.
4. The tool allowlist contains only safe read tools: metadata tools and one
   validator-approved search tool (`splunk_run_query` or `run_splunk_query`).
5. `/settings/mcp/validate`, `/settings/mcp/test`, and
   `/settings/mcp/discover` pass without persisting secrets.
6. `splunk_live_readiness.ready_for_live_splunk_mcp=true` appears in
   `/settings/status`.
7. Only then set both execution switches in the approved environment:
   `MCP_GLOBAL_EXECUTION_ENABLED=true` and
   `MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED=true`.
8. Run governance regression and a bounded live-read smoke test with HIL and
   rollback owner present.

The readiness checker is implemented in
`app/connectors/mcp/live_readiness.py`. It never calls MCP; it only inspects
registry state and returns blockers.

## Verification

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p3_mcp_evidence_matrix.py -q
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p3_mcp_live_readiness.py -q
```
