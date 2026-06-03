# COE live testing guide

This guide explains how to turn on **every supported lever** for COE validation, what still requires **engineering work** (not just `.env`), and how to get **Experience Center parity** in the main chat UI.

## Quick start

1. Copy the profile into your local env (never commit secrets):

   ```bash
   cp .env.coe-live-testing.example .env
   ```

2. Set `APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`, and LLM/MCP endpoints/tokens COE provides.

3. Rebuild and restart:

   ```bash
   docker compose build backend
   docker compose up -d
   cd frontend && npm run build
   ```

4. Hard-refresh the browser.

## Three layers (read this first)

| Layer | What you want | What `.env` can do today | What code still gates |
|-------|----------------|---------------------------|------------------------|
| **1 — EC parity in `/chat`** | Same analyst cards as Experience Center | `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=true` | Only when user text **exactly** matches a scenario query (normalized). Use picker text or copy query from `/demo/scenarios`. |
| **2 — Mock MCP on live pipeline** | Generate SPL + run → table row | `MCP_MODE=mock`, both execution flags `true`, `CONTROL_PLANE_ENABLED=true` | Mock heuristic rows, not COE Splunk events. No Foundation-sec fixture narrative unless layer 1 matches. |
| **3 — Real Splunk MCP + live LLM answers** | Query real `pgcil_soc` data + model narrative | Set `MCP_MODE=registry` + Splunk URL/token (see example file) | **`real_mcp_adapter_not_implemented`** in `mcp_execution_gate.py`. Synthesis lab is **deterministic**, not live Foundation-sec prose. |

**Setting every flag to `true` does not implement layer 3.** That needs the real MCP adapter and signed-off synthesis stage ([`plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md`](../../plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md)).

## Recommended COE phases

### Phase A — All Experience Center scenarios in live chat (now)

```env
AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=true
CONTROL_PLANE_ENABLED=true
```

Paste the **exact** scenario query from the picker, e.g.:

- Generate only: `Generate SPL for successful login after failures`
- Generate + run: `Generate SPL for successful login after failures and run on host APP-01 in index pgcil_soc sourcetype pgcil:auth for the last 60 minutes`

You get the same governed fixture payload as `/demo/scenarios/{id}/run`.

### Phase B — Live pipeline + mock Splunk (control-flow testing)

Use the full [`.env.coe-live-testing.example`](../../.env.coe-live-testing.example) **with** `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=false` if you want to exercise routing, validation, and the MCP gate without EC shortcut.

Requires:

- `CONTROL_PLANE_ENABLED=true`
- `MCP_GLOBAL_EXECUTION_ENABLED=true`
- `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`
- `MCP_MODE=mock`

“Generate … and run” → `spl_generation_and_run` → mock row when SPL validates.

### Phase C — Real Splunk MCP (COE connection)

Before flipping registry mode, COE must supply:

- MCP URL, transport, auth
- Discovered tool names and **exact** argument schema
- Approval workflow for execution

Until `app/connectors/mcp/splunk_mcp.py` implements `call_tool`, registry mode stops at **`real_mcp_adapter_not_implemented`**.

### Phase D — Live LLM final answers

Configure `AI_SOC_LLM_*` endpoints for sidecars (route-plan, MITRE candidates, etc.).

`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` enables the **governed synthesis lab** (deterministic draft from evidence). It does **not** call Foundation-sec for production narrative yet.

## Settings reference

| Goal | Key variables |
|------|----------------|
| EC = live chat | `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=true` |
| Intent / MCP policy | `CONTROL_PLANE_ENABLED=true` |
| Mock execute SPL | `MCP_MODE=mock`, `MCP_GLOBAL_EXECUTION_ENABLED=true`, `MCP_SERVER_MOCK_EXECUTION_ENABLED=true` |
| Real Splunk (blocked until adapter) | `MCP_MODE=registry`, `MCP_SERVER_SPLUNK_SOC_*` |
| SOC-KB in trace | `SOC_KB_RETRIEVAL_ENABLED=true`, `RAG_MODE=mock` |
| LLM sidecars | `AI_SOC_LLM_ENABLED=true`, `AI_SOC_LLM_MODE=cisco_foundation_sec`, provider URLs/keys |
| Synthesis lab draft | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` |
| SPL bounds | `SPL_ALLOWED_INDEXES`, `SPL_ALLOWED_SOURCETYPES`, `SPL_MAX_RESULT_LIMIT` |

Also see [`.env.live-full-throttle.example`](../../.env.live-full-throttle.example) and [p0 live flow-check profile](../gap_closure/p0_live_flow_check_profile.md).

## Verify

```bash
# Settings load
docker compose exec backend python -c "from app.config import settings; print(settings.ai_soc_live_chat_ec_parity_enabled, settings.control_plane_enabled)"

# Demo list (both success-after-failure scenarios)
curl -s http://127.0.0.1:8010/demo/scenarios | python3 -m json.tool | grep -A2 successful_login
```

After login, POST `/chat` with an exact EC query should return `demo_mode: true` when parity is on.

## Safety

- Never expose Docker ports publicly; use Nginx on `cisco-vai.vnudge.com`.
- Do not set `MCP_GLOBAL_EXECUTION_ENABLED` in production without COE approval.
- Candidate SPL is never executed; only approved `normalized_spl` enters the gate.
- LLM must not call MCP directly (backend mediates).
