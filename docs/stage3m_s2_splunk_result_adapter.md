# Stage 3M-S2: Splunk MCP Result Adapter

**Status:** Implemented (mock path + unconfirmed real adapter; no live MCP).

**Module:** `backend/app/connectors/mcp/splunk_result_adapter.py`

---

## Purpose

Route all post-connector search results through `SplunkResultEnvelope` before:

- `mcp_execution_gate` builds `execution.results_preview`
- `build_source_evidence` builds Splunk MCP evidence rows

Raw MCP dicts must not be consumed downstream past the adapter.

---

## Adapters

| Adapter | When | `origin` | `schema_confirmed` |
|---------|------|----------|-------------------|
| `MockConnectorResultAdapter` | `MCP_MODE=mock` (default) | `mock_connector` | `false` (`mock_payload`) |
| `UnconfirmedRealMcpResultAdapter` | `MCP_MODE=splunk_mcp` (if payload ever arrives) | `real_mcp` | `false` (`real_schema_unverified`) |

Live MCP execution remains blocked at the gate for non-mock registry mode (unchanged). The real adapter exists for schema-unconfirmed normalization only until S5.

---

## Execution dict

On successful mock execution, the gate adds:

- `results_preview` — from `envelope.preview_rows(5)`
- `result_count` — `min(envelope.row_count, 5)`
- `splunk_result_envelope` — `envelope.to_dict()` for evidence (stripped by `ExecutionEnvelope` API model if present)

---

## S2 non-goals

- No live MCP network calls
- No demo scenario / analyst text changes
- No `schema_confirmed=true` until S5 COE validation

---

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_splunk_result_adapter_stage3m_s2.py app/tests/test_mcp_execution_gate.py app/tests/test_evidence_context.py -q
```
