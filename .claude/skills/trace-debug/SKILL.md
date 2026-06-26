---
name: trace-debug
description: Debug a live /chat turn end-to-end using the COE read-only debug API — trace timeline, repro bundle, and pipeline readiness. Use when the user says "debug this chat turn", "why did this answer come out", "trace <id>", "what did the pipeline do", "pull the repro bundle", or /trace-debug.
disable-model-invocation: true
---

# trace-debug

Inspect what the live `/chat` control plane actually did on a turn, using the COE debug API (`backend/app/api/routes_debug.py`). Read-only, redacted, best-effort — it never alters chat. See `docs/observability/debugging.md`.

## Gating (must be on)
- `AI_SOC_DEBUG_API_ENABLED=true` (else every endpoint 404s as `debug_api_disabled`).
- Caller needs debug access: per-user `debug_access`, OR be in `AI_SOC_DEBUG_API_USER_ALLOWLIST`, OR `AI_SOC_DEBUG_API_ALLOW_ANY_AUTHENTICATED=true`. Otherwise 403.
- **EC fixture path emits no traces** (`coe_synthetic_fixture` is isolated). Only real live `/chat` turns produce a `trace_id`.

## Endpoints (behind session auth; via Nginx prefix with `/api`)
| Endpoint | Use |
|----------|-----|
| `GET /debug/traces` | List recent trace runs (find the `trace_id`). |
| `GET /debug/traces/{trace_id}` | Timeline: per-node `node.*` steps + `duration_ms`, routing, SPL, MCP, RAG, LLM `latency_ms`/outcome (cap 500 events). |
| `GET /debug/traces/{trace_id}/bundle` | Repro bundle for one turn (cap 200 events). |
| `GET /debug/readiness` | LLM + MCP + RAG + telemetry-sink readiness snapshot. |

`trace_id` must match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` — validated server-side.

## Workflow
1. **Confirm it's reachable** — `GET /debug/readiness`. If 404 → flag off; if 403 → no debug access.
2. **Find the turn** — `GET /debug/traces`, grab the `trace_id` (or the user gives one). Logs for `ai_soc.*` are stamped with `trace_id` (contextvar + LogRecordFactory) — grep logs by it.
3. **Read the timeline** — `GET /debug/traces/{id}`. Walk node `duration_ms` to find the slow/failed node; check routing decision, SPL gating, MCP outcome, LLM `outcome`/`latency_ms`, RAG hits.
4. **Pull the bundle** — `GET /debug/traces/{id}/bundle` for a portable repro of that turn.

## Air-gapped / no DB
Telemetry sink can be file/NDJSON: `AI_SOC_TELEMETRY_SINK=file` + `AI_SOC_TELEMETRY_FILE_DIR`. The read store has a file backend, so `/debug` works without Postgres.

## Reporting
Lead with the failing/slow node and its `duration_ms`, then the decisive routing/SPL/MCP/LLM event. Tie answer behavior to a concrete trace event — never guess at synthesis text without a captured payload. If the LLM is implicated, hand off to `/llm-doctor` for throughput triage.
