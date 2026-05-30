# Stage 3M-S1: SplunkResultEnvelope

**Status:** Implemented (fixture adapter only).

**Modules:**

- `backend/app/connectors/mcp/splunk_result_envelope.py`
- `backend/app/connectors/mcp/splunk_result_fixture.py`

---

## Disclaimer: real MCP schema unverified

Splunk MCP production JSON has **not** been validated in this repository. The fixture adapter normalizes **test/demo dict shapes** only. Any future `real_mcp` origin must keep `schema_confirmed=false` and `schema_confirmed_reason=real_schema_unverified` until COE provides a signed sample (Stage 3M-S5).

---

## Internal safety limits

Not Splunk platform limits — internal caps pending real schema validation:

| Constant | Value |
|----------|-------|
| `DEFAULT_MAX_ROWS` | 100 |
| `DEFAULT_PREVIEW_ROWS` | 5 |
| `FIELD_CAP` | 40 |
| `VALUE_CAP` | 240 |

---

## Envelope fields

| Field | Values / notes |
|-------|----------------|
| `status` | `ok`, `empty`, `error`, `timeout`, `blocked` |
| `origin` | `fixture`, `mock_connector`, `real_mcp` |
| `schema_confirmed` | `false` in S1 |
| `schema_confirmed_reason` | `fixture_adapter`, `mock_payload`, `real_schema_unverified` |
| `truncated` | Conservative: fixture `truncated=true` OR `total_row_count > row_count` OR row cap |
| `truncation_reason` | `row_limit`, `timeout`, `server_limit`, `fixture_declared`, `unknown` |
| `rows` | Sanitized; sensitive **keys kept**, values `[REDACTED]` |

---

## Normalization rules

### Empty

Input:

```json
{"status": "ok", "rows": [], "row_count": 0}
```

Output: `status=empty` (not `ok` with zero rows).

### Truncation

`truncated=true` if any of:

- `truncated: true` in fixture
- `total_row_count > row_count` (after sanitize)
- row list exceeds `max_rows`

### Redaction

Sensitive field names (password, secret, token, api_key, …): key preserved, value `"[REDACTED]"`.

---

## Fixture examples

```python
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload

# Success
envelope_from_fixture_payload({
    "status": "ok",
    "rows": [{"user": "svc_app", "fail_count": 184}],
    "row_count": 1,
    "duration_ms": 7,
    "spl_hash": "abc123",
})

# Empty → status empty
envelope_from_fixture_payload({"status": "ok", "rows": [], "row_count": 0})

# Error / timeout
envelope_from_fixture_payload({"status": "error", "error": "search_failed", "rows": []})
envelope_from_fixture_payload({"status": "timeout", "error": "search_timeout", "rows": []})

# Truncation
envelope_from_fixture_payload({
    "status": "ok",
    "rows": [{"id": i} for i in range(5)],
    "row_count": 5,
    "total_row_count": 100,
})
```

---

## API helpers

- `preview_rows(limit=5)` — capped safe rows for future execution gate
- `to_dict()` — stable key order for tests/trace

---

## S1 non-goals (explicit)

- No real MCP calls or network
- No `mcp_execution_gate` / `source_evidence` / demo / `/chat` changes
- No LLM, Answer Guard, or SPL execution changes

---

## Migration checklist

| Task | Stage |
|------|-------|
| Wire mock connector through adapter → envelope | S2 |
| `mcp_execution_gate` uses `preview_rows()` | S2 |
| `build_source_evidence` maps from envelope | S2 |
| Demo `_execution_payload` / fixture evidence | S3 |
| Live read + schema confirmation | S5 |
