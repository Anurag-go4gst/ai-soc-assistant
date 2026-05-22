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

Backend health:

```text
http://SERVER_IP:8010/health
```

Frontend:

```text
http://SERVER_IP:3010
```

## Warning

This is an internal development scaffold. Do not expose it publicly through nginx or SSL until authentication, authorization, data boundaries, and deployment hardening are implemented.
