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

## Verification

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p3_mcp_evidence_matrix.py -q
```
