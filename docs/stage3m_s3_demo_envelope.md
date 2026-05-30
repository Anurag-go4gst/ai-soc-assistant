# Stage 3M-S3: Experience Center Demo Envelope Wiring

**Status:** Implemented. Landed in commit `d153e44`.

**Module:** `backend/app/demo/mcp_result_envelope.py`

---

## Purpose

Route COE synthetic Splunk preview rows through `SplunkResultEnvelope` in the Experience Center demo path:

- `run_demo_scenario` mock execution (`mcp_execution_mode=mock_success`)
- `source_evidence` items with `source_type=splunk_mcp`

No Splunk MCP calls. No live customer data.

---

## Behavior

| Path | Change |
|------|--------|
| `_execution_payload` (mock_success) | Rows → `demo_envelope_from_rows` → `results_preview` + `splunk_result_envelope` on execution dict |
| `_with_trace` | Each `splunk_mcp` evidence item normalized via `apply_envelope_to_splunk_evidence` |

Analyst-facing golden text (`_analyst_response`, `analyst_summary`, `message`) is unchanged.

`route_plan_shadow` is not produced by demo scenarios (unchanged).

---

## S3 non-goals

- No live MCP / real Splunk
- No `/chat` production path changes beyond shared envelope library
- Demo analyst copy unchanged

---

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_demo_splunk_envelope_stage3m_s3.py app/tests/test_demo_scenarios_stage3jd.py -q
```
