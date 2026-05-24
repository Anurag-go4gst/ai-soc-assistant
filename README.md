# AI SOC Assistant

Internal development scaffold for an AI-Augmented SOC Assistant for Splunk.

This project is intended to become a production-convertible assistant using FastAPI, React + TypeScript, LangGraph orchestration, a generic MCP registry with Splunk MCP as the first target server, PostgreSQL with pgvector, Agentic GraphRAG, multiple LLM provider/model backends, and deterministic safeguards.

## Architecture Summary

- FastAPI backend exposes health, chat, investigation, and scenario placeholder routes.
- React + TypeScript frontend provides a structured SOC cockpit using Tailwind CSS, shadcn-style local UI primitives, Radix patterns, and lucide-react icons.
- MCP, LangGraph, RAG, GraphRAG, LLM routing, and production safeguards are represented by clean placeholder interfaces only. Splunk MCP is one MCP server type, not the whole MCP framework.
- PostgreSQL is included in Docker Compose for later persistence work.

## Start

```bash
cd /var/www/ai-soc-assistant
cp .env.example .env
docker compose build
docker compose up -d
```

Local backend health:

```text
http://127.0.0.1:8010/health
```

Development frontend:

```text
http://127.0.0.1:3010
```

## Internal Nginx Access

Production-style access is through Nginx only. Docker ports for the backend, frontend dev server, and Postgres are bound to `127.0.0.1`.

Internal URL:

```text
https://cisco-vai.vnudge.com
```

Local backend health check:

```bash
curl -s http://127.0.0.1:8010/health
```

Nginx serves the production frontend from `frontend/dist`, proxies `/api/` and `/health` to the local FastAPI backend, and redirects HTTP to HTTPS. App-level login is handled by the FastAPI backend using credentials from `.env`.

The frontend visual system was adapted from the existing Support Buddy app as a read-only UI reference. No Support Buddy secrets, auth logic, HR data, ticket logic, or runtime configuration are used by this project.

## UI Pages

The React app now ships with these top-level routes (left sidebar):

- **Cockpit** — 3-column investigation workspace (alerts/scenario, chat, context tabs)
- **Chat** — focused chat workspace optimized for 100% browser zoom
- **Investigations** — mock case list (persistence comes later)
- **Scenarios** — demo scenario library
- **Knowledge** — read-only SOPs and graph context
- **Settings** — non-secret configuration surfaces (see below)
- **Debug** — planner / router / compare traces, SPL trace, raw mock JSON

Trace summary cards in Cockpit link to **Debug**; the full developer surface lives there, not inside Cockpit.

## Settings Surfaces

`Settings` exposes read-only status for:

- MCP (multi-server registry status, transport/auth configured booleans, discovered safe tool names, blocked execution tool names)
- RAG (knowledge vault path, doc counts, vector / BM25 / KG status)
- LLM (multi-provider registry status, model family/role, router/synthesis/reasoning/teacher role mapping)
- Routing (mode, planner/shadow/compare flags, confidence thresholds)
- Safeguards (SPL validator, blocked commands, approval requirements)
- Observability (telemetry/trace flags, telemetry-write failure counter)

> **Telemetry storage:** `ai_soc` is this product's own namespace, not a Splunk
> product. AI-SOC runtime telemetry is stored in Postgres / the application
> database by default (`AI_SOC_TELEMETRY_SINK=db`). A Splunk telemetry connector
> is **deferred and not implemented** — setting `AI_SOC_TELEMETRY_SINK=splunk`
> or `both` makes the backend fail fast at startup with a clear configuration
> error. Set the sink to `none` to disable telemetry entirely.

The backing endpoint is `GET /api/settings/status` — it never returns tokens, passwords, usernames, bearer tokens, API keys, or session secrets, only `*_configured: bool` flags.

## Stage 3B Connection Readiness

Stage 3B prepares real-but-safe configuration surfaces only:

- `MCP_MODE=mock` keeps current mock behavior.
- `MCP_MODE=registry` parses named MCP servers from `MCP_SERVERS=splunk_soc,asset_inventory,ticketing`.
- Each MCP server has independent `configured`, `available`, `implemented`, and redacted `last_error` status.
- Splunk MCP targets the official Splunk MCP Server / Splunkbase App ID `7931` by default, but remains only one server type in the generic registry.
- MCP execution is disabled by both `MCP_GLOBAL_EXECUTION_ENABLED=false` and per-server `MCP_SERVER_<NAME>_EXECUTION_ENABLED=false`.
- Search/SPL execution tools and SAIA/SPL-generation tools are displayed as discovered but blocked.
- No MCP tool execution is implemented in this stage.
- The readiness layer uses a thin transport-agnostic adapter surface for `streamable_http`, `sse`, and `stdio`. If the official MCP Python SDK is added later, it should plug in behind this registry without changing environment variable names.

LLM readiness is provider/model based:

- `LLM_PROVIDERS` can list Foundation-Sec, local open-weight models, and enterprise gateways at the same time.
- Cisco/Foundation-Sec is one model family, not the only LLM option.
- Foundation-Sec Instruct and Foundation-Sec Reasoning are configured as separate providers/models when needed.
- Llama, Kimi, Qwen, Mistral, DeepSeek, and other open-weight models can be served through OpenAI-compatible gateways, vLLM, Ollama, SGLang, TGI, llama.cpp, or custom HTTP adapters.
- Workflow code resolves roles such as `router`, `synthesis`, `reasoning`, and `teacher` to configured providers; fallback must be explicit.
- `supports_tool_calling` is forced false in status because the AI-SOC backend controls MCP access. The LLM must never call MCP directly.
- LLM health canary completion is disabled by default with `LLM_HEALTH_CANARY_ENABLED=false`.

Current disabled work remains disabled: no SPL execution, no MCP tool execution, no RAG retrieval, no final LLM synthesis, and no Splunk telemetry write. Stage 3C adds candidate SPL generation plus deterministic validation only.

## Stage 3C SPL Generation And Validation

Stage 3C introduces a safe SPL gate before any future execution:

- `attack_discovery` and `spl_generation` chat routes produce candidate SPL with the stub generator.
- Candidate SPL is validated deterministically before it can be considered for future MCP execution.
- Validator rejects by default unless the SPL is positively classified safe.
- Validator enforces allowed commands, blocked commands, time bounds, index and sourcetype allowlists, wildcard index blocking, macro/subsearch blocking, external-call blocking, credential/secret pattern blocking, and out-of-band result caps.
- Chat returns candidate SPL and validation status, then stops. It does not call Splunk or MCP.

Default SPL policy:

```env
SPL_VALIDATION_ENABLED=true
SPL_ALLOWED_INDEXES=pgcil_soc
SPL_ALLOWED_SOURCETYPES=pgcil:auth
SPL_DEFAULT_EARLIEST=-24h
SPL_DEFAULT_LATEST=now
SPL_MAX_RESULT_LIMIT=100
SPL_ALLOWED_COMMANDS=search,stats,where,table,fields,sort,dedup,rename,eval,timechart,bin,head
SPL_BLOCKED_COMMANDS=delete,collect,outputlookup,sendemail,script,map,rest,loadjob,inputlookup
```

Example approved candidate:

```spl
search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure | stats count as fail_count by user | where fail_count > 50 | sort -fail_count | head 100
```

Example rejected candidate:

```spl
search index=* sourcetype=pgcil:auth earliest=-15m latest=now | outputlookup findings.csv
```

Reject reasons include `blocked_command:outputlookup`, `disallowed_index`, and `wildcard_index_not_allowed`.

### Mock Mode Example

```env
MCP_MODE=mock
MCP_DEFAULT_SERVER=splunk_soc
MCP_GLOBAL_EXECUTION_ENABLED=false
LLM_MODE=mock
LLM_HEALTH_CANARY_ENABLED=false
TELEMETRY_MODE=db
AI_SOC_TELEMETRY_SINK=db
```

### COE Readiness Example

Use placeholder values only until COE provides real endpoints and credentials:

```env
MCP_MODE=registry
MCP_SERVERS=splunk_soc,asset_inventory,ticketing
MCP_DEFAULT_SERVER=splunk_soc
MCP_GLOBAL_EXECUTION_ENABLED=false

MCP_SERVER_SPLUNK_SOC_ENABLED=true
MCP_SERVER_SPLUNK_SOC_TYPE=splunk
MCP_SERVER_SPLUNK_SOC_TRANSPORT=streamable_http
MCP_SERVER_SPLUNK_SOC_URL=https://splunk-mcp.example.invalid/mcp
MCP_SERVER_SPLUNK_SOC_AUTH_MODE=bearer
MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN=replace-with-token
MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST=list_tools,splunk_get_indexes,splunk_search,saia_generate_spl
MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED=false
MCP_SERVER_SPLUNK_SOC_SPLUNK_APP_ID=7931
MCP_SERVER_SPLUNK_SOC_SPLUNK_PLATFORM=unknown

LLM_PROVIDERS=foundation_sec_instruct,foundation_sec_reasoning,llama_local,kimi_local,enterprise_gateway
LLM_DEFAULT_PROVIDER=foundation_sec_instruct
LLM_ROUTER_PROVIDER=foundation_sec_instruct
LLM_SYNTHESIS_PROVIDER=foundation_sec_instruct
LLM_REASONING_PROVIDER=foundation_sec_reasoning
LLM_TEACHER_PROVIDER=enterprise_gateway
LLM_GLOBAL_CONCURRENCY=4
LLM_TIMEOUT_SECONDS=30
LLM_HEALTH_CANARY_ENABLED=false

LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_ENABLED=true
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_TYPE=cisco_compatible
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_BASE_URL=https://foundation-sec-instruct.example.invalid/v1
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_API_KEY=replace-with-api-key
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_AUTH_MODE=api_key
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_MODEL=replace-with-instruct-model
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_MODEL_ROLE=instruct
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_FAMILY=foundation_sec
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_SUPPORTS_TOOL_CALLING=false

LLM_PROVIDER_FOUNDATION_SEC_REASONING_ENABLED=true
LLM_PROVIDER_FOUNDATION_SEC_REASONING_TYPE=cisco_compatible
LLM_PROVIDER_FOUNDATION_SEC_REASONING_BASE_URL=https://foundation-sec-reasoning.example.invalid/v1
LLM_PROVIDER_FOUNDATION_SEC_REASONING_API_KEY=replace-with-api-key
LLM_PROVIDER_FOUNDATION_SEC_REASONING_AUTH_MODE=api_key
LLM_PROVIDER_FOUNDATION_SEC_REASONING_MODEL=replace-with-reasoning-model
LLM_PROVIDER_FOUNDATION_SEC_REASONING_MODEL_ROLE=reasoning
LLM_PROVIDER_FOUNDATION_SEC_REASONING_FAMILY=foundation_sec
LLM_PROVIDER_FOUNDATION_SEC_REASONING_SUPPORTS_TOOL_CALLING=false
```

### Status Shape Example

`GET /api/settings/status` redacts secrets and reports only booleans:

```json
{
  "mcp": {
    "mode": "registry",
    "default_server": "splunk_soc",
    "global_execution_enabled": false,
    "servers": [
      {
        "name": "splunk_soc",
        "type": "splunk",
        "url_configured": true,
        "auth_configured": true,
        "execution_enabled": false,
        "discovered_tools_safe_names": ["list_tools", "splunk_search"],
        "blocked_tools_safe_names": ["splunk_search"],
        "search_execution_allowed": false,
        "saia_spl_generation_allowed": false
      }
    ]
  },
  "llm": {
    "default_provider": "foundation_sec_instruct",
    "role_resolution": {
      "router": "foundation_sec_instruct",
      "reasoning": "foundation_sec_reasoning"
    },
    "providers": [
      {
        "name": "foundation_sec_instruct",
        "base_url_configured": true,
        "api_key_configured": true,
        "supports_tool_calling": false
      }
    ]
  }
}
```

## Warning

This is an internal Experience Center scaffold. Do not expose Docker service ports publicly and do not commit auth credentials or session secrets.
