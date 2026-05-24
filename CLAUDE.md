# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI SOC Assistant — internal experience-center scaffold for an AI-augmented SOC dashboard. FastAPI backend + React/TypeScript frontend + Postgres. The app currently supports skill routing, workflow planning, candidate SPL generation, deterministic SPL validation, MCP discovery/tool selection, human-in-the-loop gates, optional explicitly-enabled mock MCP execution, a generic multi-MCP readiness registry, a multi-LLM provider/model readiness registry, telemetry/status surfaces, and deterministic safeguards. Production access goes through Nginx at `https://cisco-vai.vnudge.com`; Docker service ports are bound to `127.0.0.1` and must never be exposed publicly.

## Stack

- Backend: Python 3.12, FastAPI, Uvicorn, SQLAlchemy, pytest
- Frontend: React 18 + TypeScript, Vite, Tailwind CSS, Radix UI, lucide-react, shadcn-style local primitives
- DB: PostgreSQL 16 (pgvector-capable)
- Orchestration: Docker Compose (primary dev path)

## Current Stage Boundaries

- `/chat` performs routing, returns a `workflow_plan`, can generate candidate SPL for eligible skills, validates SPL deterministically, evaluates MCP tool selection/execution gates, and returns `human_review` when execution cannot safely proceed.
- Workflow steps are `not_started` and `execution_enabled=false`.
- Candidate SPL is never executable. Only an approved validation result with non-null `normalized_spl` may enter the MCP execution gate.
- MCP is a generic multi-server registry. Splunk MCP is the first target MCP server type, not the whole framework.
- MCP execution is disabled by default globally and per server. Mock execution requires both `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- Real MCP execution remains not implemented until COE supplies server URL, transport, auth, discovered tool names, exact argument schema, and an approval workflow.
- Tool selection is deterministic; user-requested MCP server/tool values are preferences only. LLM recommendations are disabled by default and advisory only if later enabled.
- LLM is a provider/model registry. Cisco/Foundation-Sec is one family, not the only supported LLM option.
- Open-weight/local models are configured through provider types such as `openai_compatible`, `ollama`, `vllm`, `sglang`, `tgi`, `llamacpp`, and `custom_http`.
- The AI-SOC backend controls MCP access. The LLM must never call MCP directly.
- Do not add RAG retrieval, final LLM synthesis, Splunk telemetry writes, SAIA/Splunk AI Assistant SPL generation, or direct LLM-to-MCP tool calling unless a later stage explicitly asks for it.
- Do not execute raw `candidate_spl`; never pass prompts, reasoning, credentials, RAG chunks, or raw workflow internals to MCP.

## Run / Build

Primary path is Docker Compose, not bare uvicorn/npm:

```bash
docker compose build
docker compose up -d
```

Ports (all bound to 127.0.0.1):
- Backend: `http://127.0.0.1:8010` (uvicorn `--reload`, entry `app.main:app`)
- Frontend dev: `http://127.0.0.1:3010` (Vite)
- Postgres: `127.0.0.1:5434`

Frontend-only commands (run inside `frontend/`):
- `npm run dev` — Vite dev server on 3010
- `npm run build` — `tsc` + Vite build to `frontend/dist` (Nginx serves this in production)
- `npm run preview` — preview prod build

Backend bare-run (outside Docker, rare): `uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload` from `backend/`.

## Tests

Backend tests:

```bash
cd backend
python3 -m pytest
```

Frontend build:

```bash
cd frontend
npm run build
```

Independent harness:

```bash
python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
```

Expected current baseline:
- Backend pytest: all tests pass.
- Frontend build: passes.
- Harness default: 6/6 pass.
- Harness with `TELEMETRY_MODE=none`: 6/6 pass.

## Layout

Monorepo, backend + frontend split:

```
backend/
  app/
    api/           # routes: health, chat, investigations, scenarios, auth
    auth/          # FastAPI session login (replaced prior nginx basic auth)
    schemas/       # Pydantic request/response models
    graph/         # LangGraph workflow state & orchestration (stub)
    orchestration/ # workflow planner skeleton; planning only, no execution
    safeguards/    # data minimizer, prompt injection filter, SPL validator, output validator
    routing/       # deterministic + shadow LLM routing, route comparison
    connectors/    # MCP, LLM, RAG, embeddings, telemetry connector surfaces
    mcp/           # legacy Splunk MCP client + mock client placeholders
    rag/           # RAG interface (stub)
    llm/           # LLM routing schema/prompts placeholders
    db/            # SQLAlchemy models + session
    knowledge_graph/, audit/, telemetry/
  pyproject.toml   # `pip install -e .` in Docker
  Dockerfile

frontend/
  src/
    components/    # UI primitives (shadcn-style), debug components
    pages/, api/, types/, lib/
  vite.config.ts   # alias @ -> ./src
  tsconfig.json    # strict, ES2020, Bundler resolution
  tailwind.config.ts, postcss.config.js, components.json

docker-compose.yml
.env.example
```

## Required Env Vars

Copy `.env.example` to `.env` before first `docker compose up`. Keys split into:
- App: `APP_ENV`, `BACKEND_PORT`, `FRONTEND_PORT`, `DATABASE_URL`, `DEBUG_TRACE_ENABLED`
- MCP readiness: `MCP_MODE`, `MCP_SERVERS`, `MCP_DEFAULT_SERVER`, `MCP_GLOBAL_EXECUTION_ENABLED`, and `MCP_SERVER_<NAME>_*`
- MCP mock execution: `MCP_SERVER_MOCK_EXECUTION_ENABLED` (must stay false unless explicitly testing mock execution)
- LLM readiness: `LLM_PROVIDERS`, role provider vars, concurrency/timeout/canary vars, `LLM_TOOL_RECOMMENDATION_ENABLED`, and `LLM_PROVIDER_<NAME>_*`
- SPL policy: `SPL_VALIDATION_ENABLED`, `SPL_ALLOWED_INDEXES`, `SPL_ALLOWED_SOURCETYPES`, `SPL_DEFAULT_EARLIEST`, `SPL_DEFAULT_LATEST`, `SPL_MAX_RESULT_LIMIT`, `SPL_ALLOWED_COMMANDS`, `SPL_BLOCKED_COMMANDS`
- Legacy placeholders retained for current mock connectors: `SPLUNK_MCP_ENABLED`, `SPLUNK_MCP_BASE_URL`, `SPLUNK_MCP_TOKEN`, `LLM_ENABLED`, `FOUNDATION_SEC_INSTRUCT_URL`, `FOUNDATION_SEC_REASONING_URL`, `REASONING_ENABLED`
- Routing: `ROUTING_MODE`, `ROUTING_DETERMINISTIC_THRESHOLD`, `ROUTING_LLM_SHADOW_ENABLED`, `ROUTING_COMPARE_LOGGING_ENABLED`
- AI-SOC telemetry: `TELEMETRY_MODE`, `AI_SOC_TELEMETRY_SINK`
- App login (replaces nginx basic auth): `APP_AUTH_ENABLED`, `APP_AUTH_USER`, `APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`

Never commit `.env` or session secrets. Postgres dev creds in `docker-compose.yml` (`ai_soc` / `ai_soc_dev_password`) are dev-only — do not reuse in production.

## Gotchas

- Auth migration is recent: app-level FastAPI session login replaces the old Nginx basic auth. Don't reintroduce basic-auth assumptions.
- CORS origin is hardcoded to `http://127.0.0.1:3010` in the FastAPI middleware — update when deploying or changing dev ports.
- `MCP_MODE=mock` must keep mock behavior. It may execute bounded deterministic mock rows only when both execution flags are explicitly enabled.
- `MCP_MODE=registry` may report configured/available/discovered-tool status. Real MCP execution must remain blocked/not implemented until the COE connection and argument schema are supplied.
- All MCP and LLM settings/status output must redact secrets. Expose only booleans such as `url_configured`, `auth_configured`, `api_key_configured`.
- Splunk MCP App ID `7931` is the first target. Splunk search tools can only be selected for `spl_search` after deterministic policy checks; SAIA/generative/assistant/write/admin tools must remain blocked.
- LLM `supports_tool_calling` must remain false for now because direct LLM-to-MCP access is not allowed.
- Frontend visual system was adapted from a separate Support Buddy app as a read-only UI reference. No Support Buddy secrets, auth logic, or runtime config are reused — don't import them.
- Production traffic goes through Nginx at `cisco-vai.vnudge.com` serving `frontend/dist` and proxying `/api/` + `/health` to the backend. Don't expose Docker ports.

## Git Notes

Recent stage split:
- `459cb75 Add workflow planning after skill routing`
- `b6b8329 Add multi-MCP and multi-LLM readiness registry`
- `8afd560 Add candidate SPL generation and deterministic validation`
- `7a35038 Add MCP discovery, HIL, and gated SPL execution`
- `a47785d Add Stage 3D trace pipeline UI`
- `fdb4501 Add Splunk context document template`

Keep future changes similarly scoped. Do not combine workflow execution changes with connection-readiness or UI-only changes unless explicitly requested.
