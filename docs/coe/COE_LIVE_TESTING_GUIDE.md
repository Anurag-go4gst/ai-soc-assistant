# COE live testing guide

This guide explains how to turn on **every supported lever** for COE validation, what still requires **engineering work** (not just `.env`), and how to get **Experience Center parity** in the main chat UI.

**COE rollout (recommended flags + smoke checklist):** [`COE_ROLLOUT_CONFIGURATION.md`](COE_ROLLOUT_CONFIGURATION.md)  
**Canonical profile:** [`env/profiles/coe.env.example`](../../env/profiles/coe.env.example)

## Quick start

1. Create the local secrets selector (never commit secrets):

   ```bash
   cp .env.selector.example .env
   ```

2. Set `AI_SOC_ENV_PROFILE=coe`, `APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`, and any LLM/MCP endpoints/tokens COE provides.

3. Select the COE profile, rebuild, and restart:

   ```bash
   ./scripts/select_env_profile.sh coe
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
| **3 — Real Splunk MCP + governed live narration** | Query real `pgcil_soc` data + Foundation-Sec prose | Set `MCP_MODE=registry`, Splunk URL/token, per-server allowlist/execution flags, and synthesis flags | Adapter exists, but execution still requires approved SPL, allowlisted `splunk_run_query`, global + server execution flags, per-call analyst confirmation, and COE schema smoke. LLM prose is non-authoritative and falls back to deterministic text. |

**Setting every flag to `true` is not a safe layer-3 rollout.** Real execution also needs COE credentials, a reviewed tool allowlist, schema smoke, and an analyst confirmation on the exact normalized SPL.

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

Use `env/profiles/coe.env.example` **with** `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=false` if you want to exercise routing, validation, and the MCP gate without the EC shortcut.

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
- `MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST` including `splunk_run_query`
- Global + per-server execution flags
- Per-call analyst confirmation for the exact normalized SPL

The live search adapter is implemented. Registry mode still fails closed as `splunk_mcp_not_configured`, `mcp_global_execution_disabled`, `mcp_server_execution_disabled`, `live_transport_unconfigured`, or a confirmation review until all gates pass.

### Phase D — Live LLM final answers

Configure `AI_SOC_LLM_*` endpoints for sidecars (route-plan, MITRE candidates, etc.).

`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` plus `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` enables the governed answer composer to call Foundation-Sec for analyst prose when a non-mock provider is configured. The model rewrites only contract-grounded text; severity, MITRE status, SPL approval, and execution facts remain deterministic authority, and failures fall back to deterministic text.

## Settings reference

| Goal | Key variables |
|------|----------------|
| EC = live chat | `AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED=true` |
| Intent / MCP policy | `CONTROL_PLANE_ENABLED=true` |
| Mock execute SPL | `MCP_MODE=mock`, `MCP_GLOBAL_EXECUTION_ENABLED=true`, `MCP_SERVER_MOCK_EXECUTION_ENABLED=true` |
| Real Splunk search | `MCP_MODE=registry`, `MCP_SERVER_SPLUNK_SOC_*`, `SPLUNK_MCP_BASE_URL`, `SPLUNK_MCP_TOKEN`, execution flags, per-call confirmation |
| SOC-KB in trace | `SOC_KB_RETRIEVAL_ENABLED=true`, `RAG_MODE=mock` |
| LLM sidecars | `AI_SOC_LLM_ENABLED=true`, `AI_SOC_LLM_MODE=cisco_foundation_sec`, provider URLs/keys |
| Governed live narration | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true`, `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` |
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
- Do not set `MCP_GLOBAL_EXECUTION_ENABLED` or per-server execution flags in production without COE approval.
- Candidate SPL is never executed; only approved `normalized_spl` enters the gate.
- LLM must not call MCP directly (backend mediates).
