# AI SOC Assistant

Internal development scaffold for an AI-Augmented SOC Assistant for Splunk.

This project is intended to become a production-convertible assistant using FastAPI, React + TypeScript, LangGraph orchestration, Splunk MCP, PostgreSQL with pgvector, Agentic GraphRAG, Foundation-Sec LLMs, and deterministic safeguards.

## Architecture Summary

- FastAPI backend exposes health, chat, investigation, and scenario placeholder routes.
- React + TypeScript frontend provides a structured SOC cockpit.
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

## Warning

This is an internal Experience Center scaffold. Do not expose Docker service ports publicly and do not commit auth credentials or session secrets.
