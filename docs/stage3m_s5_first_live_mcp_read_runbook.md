# Stage 3M-S5: First Controlled Live Splunk MCP Read

**Status:** Runbook + manual capture harness (no CI, no production enablement).

---

## Goal

Prepare the first **controlled, read-only** Splunk MCP search result capture and COE schema review — without enabling production execution or automatic `schema_confirmed=true`.

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| Splunk MCP Server App | Target App ID **7931** (COE) |
| Endpoint | `STAGE3M_S5_MCP_ENDPOINT` or `SPLUNK_MCP_BASE_URL` |
| Auth | `STAGE3M_S5_MCP_TOKEN` or `SPLUNK_MCP_TOKEN` (never commit) |
| Tool | Allowlisted read-only search tool: `run_splunk_query` / `splunk_run_query` |
| RBAC | Read-only search role; no write/admin/SAIA tools |
| Flag | `STAGE3M_S5_LIVE_MCP_CAPTURE=true` (manual runs only) |

---

## Policies

| Policy | Value |
|--------|--------|
| SPL | Low-risk template only (see harness default) |
| Timeout | ≤ 30s recommended |
| Row cap | Internal envelope max **100** (not a Splunk platform guarantee) |
| Redaction | Secrets stripped before writing capture file |
| Schema | `schema_confirmed=false` until COE signs captured JSON |

Default read-only SPL (harness):

```spl
search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count | head 5
```

---

## Manual capture script

```bash
export STAGE3M_S5_LIVE_MCP_CAPTURE=true
export STAGE3M_S5_MCP_ENDPOINT=https://your-splunk-mcp.example/mcp
export STAGE3M_S5_MCP_TOKEN=***
export STAGE3M_S5_MCP_TOOL=run_splunk_query
# After COE live call, save raw JSON and point the harness at it:
export STAGE3M_S5_RAW_FIXTURE_PATH=/tmp/splunk_mcp_raw_sample.json

python3 scripts/capture_stage3m_s5_live_mcp_schema.py
```

Output: [`docs/stage3m_s5_live_mcp_schema_capture.json`](stage3m_s5_live_mcp_schema_capture.json) (created only on success).

**Fail-closed:** missing flag, endpoint, auth, or fixture path → non-zero exit; **no file write**.

Live HTTP from the script is **not** enabled in CI. Operators perform the MCP read under COE change control, save raw JSON, then run the harness to produce a redacted envelope sample.

---

## Rollback / disable

1. Unset `STAGE3M_S5_LIVE_MCP_CAPTURE`.
2. Keep `MCP_GLOBAL_EXECUTION_ENABLED=false` (default).
3. Do not merge `schema_confirmed=true` until COE review record exists.
4. Delete or archive `stage3m_s5_live_mcp_schema_capture.json` if capture is invalidated.

---

## COE schema confirmation

Only after COE reviews `docs/stage3m_s5_live_mcp_schema_capture.json` and signs the shape:

1. Update capture doc `schema_confirmed` to `true` under change control.
2. Wire real adapter mapping in a **future** stage (not S5).
3. Never auto-set `schema_confirmed=true` from the capture script.

---

## Explicit non-goals (S5)

- No `/chat` live MCP wiring
- No CI live calls
- No `MCP_GLOBAL_EXECUTION_ENABLED` default change
- No production `mcp_execution_gate` behavior change
- No Hugging Face / LLM calls
- No analyst answer changes

---

## Verification (automated)

```bash
cd backend && python3 -m pytest app/tests/test_live_schema_capture_stage3m_s5.py -q
```
