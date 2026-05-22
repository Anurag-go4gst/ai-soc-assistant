# AI SOC Assistant

Internal development scaffold for an AI-Augmented SOC Assistant for Splunk.

This project is intended to become a production-convertible assistant using FastAPI, React + TypeScript, LangGraph orchestration, Splunk MCP, PostgreSQL with pgvector, Agentic GraphRAG, Foundation-Sec LLMs, and deterministic safeguards.

## Architecture Summary

- FastAPI backend exposes health, chat, investigation, and scenario placeholder routes.
- React + TypeScript frontend provides a structured SOC cockpit using Tailwind CSS, shadcn-style local UI primitives, Radix patterns, and lucide-react icons.
- Splunk MCP, LangGraph, RAG, GraphRAG, LLM routing, and production safeguards are represented by clean placeholder interfaces only.
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

- MCP (Splunk MCP base URL / token configured booleans, allowed tools, indexes, sourcetypes)
- RAG (knowledge vault path, doc counts, vector / BM25 / KG status)
- LLM (Foundation-Sec Instruct + Reasoning endpoint configured booleans)
- Routing (mode, planner/shadow/compare flags, confidence thresholds)
- Safeguards (SPL validator, blocked commands, approval requirements)
- Observability (telemetry/trace flags, telemetry-write failure counter)

> **Telemetry storage:** `ai_soc` is this product's own namespace, not a Splunk
> product. AI-SOC runtime telemetry is stored in Postgres / the application
> database by default (`AI_SOC_TELEMETRY_SINK=db`). A Splunk telemetry connector
> is **deferred and not implemented** — setting `AI_SOC_TELEMETRY_SINK=splunk`
> or `both` makes the backend fail fast at startup with a clear configuration
> error. Set the sink to `none` to disable telemetry entirely.

The backing endpoint is `GET /api/settings/status` — it never returns tokens, passwords, or session secrets, only `*_configured: bool` flags. MCP / RAG / LLM are still mock-mode; live connectors land in a later phase.

## Warning

This is an internal Experience Center scaffold. Do not expose Docker service ports publicly and do not commit auth credentials or session secrets.
