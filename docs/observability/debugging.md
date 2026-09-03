# COE Observability & Debugging

How to debug the AI SOC Assistant in the COE: was the LLM ready, was MCP ready,
which nodes ran and how long, why did this answer come out this way — without
reading source or hand-writing SQL.

Plan: [`plans/2026-06-15_1949_coe-observability-debugging.md`](../../plans/2026-06-15_1949_coe-observability-debugging.md).

## Enable

```bash
AI_SOC_DEBUG_API_ENABLED=true        # read-only /debug API (default on; auth + role gated)
AI_SOC_TELEMETRY_SINK=db             # db | file | none
AI_SOC_TELEMETRY_FILE_DIR=telemetry_logs   # only when sink=file (air-gapped, no Postgres)
```

Access to `/debug/*` requires an authenticated user with `debug_access` (per-user
flag in the auth registry; `soc_lead` default-on). When the flag is off the API
returns 404; when the user lacks access, 403.

## The one workflow

1. Reproduce the bad/slow answer in chat. Copy `trace_id` from the response.
2. `GET /api/debug/traces/{trace_id}/bundle` — the COE handoff artifact
   (default `detail=forensic`, lossless). Start with
   `explainability.effective_state`, then `explainability.debug_summary`.
   Add `?detail=reviewer` for the compact STANDARD export (`schema_version=reviewer_trace_v2`):
   final-state fields, artifact refs, and no duplicated heavy snapshots.
   Forensic LLM request/response bodies live on timeline `llm_call` events
   (`schema_version=llm_interaction_v1`).
3. Read the timeline top-to-bottom: route → evidence → SPL → MCP → LLM → answer.
4. `GET /api/debug/readiness` for the LLM/MCP/RAG/sink snapshot + counters.

## Surfaces — which one answers what

| Question | Surface |
|----------|---------|
| List recent turns | `GET /api/debug/traces?limit=&entrypoint=&status=&since=` |
| Full timeline of one turn | `GET /api/debug/traces/{trace_id}` (capped 500 events) |
| Repro/handoff bundle | `GET /api/debug/traces/{trace_id}/bundle` (capped 200 events, `detail=forensic` default) |
| Compact reviewer export | `GET /api/debug/traces/{trace_id}/bundle?detail=reviewer` |
| **Why no LLM / was a model actually called** | `explainability.debug_summary.llm` (`live_calls`, `skipped_roles`, `spl_path`, `spl_live_called`) + trace list `llm_live_calls` (not `llm_used`, which tracks SPL advisory flags). Timeline `llm_call` events for per-hop detail. |
| **Is the LLM working / why not** | readiness `llm` block + timeline `llm_call` events: `role`, `outcome` (`completed`/`timed_out`/`dropped`/`blocked`), `latency_ms`, `model`; counters `llm_calls_total`/`llm_calls_timed_out`/`llm_calls_fallback` |
| **Why this route / catalog steal** | trace list `match_path` + `use_case_id` + `matched_pattern`; bundle `debug_summary.routing` |
| **What answer did the analyst see** | `explainability.final_output` (redacted `message`, `analyst_summary`, severity, MITRE status, HIL) + trace list `answer_preview` (prefers real message over RunContract template) |
| **2C intent / dispatch schedule** | `explainability.debug_summary.intent` (`prompt_mode`, `call_2c_llm`, slots) + `debug_summary.dispatch` (`request_mode`, `stage_schedule`, `llm_hops`); mirrored on `control_plane_trace.intent_dispatch` / `pipeline_dispatch` |
| **SPL postprocessor proof** | `debug_summary.spl.postprocessor_evaluated`, `postprocessor_applied`, `no_op_reason`, `spl_raw_hash` / `spl_post_hash` |

| **Is MCP working / why not** | readiness `mcp` block + timeline `mcp_execution` events (15 event types incl. block/fail reasons) |
| **Is a response coming / why not** | run `status` (`completed`/`human_review`/`error`) + `duration_ms` |
| **How the answer was produced / which nodes** | timeline `node.*` steps with per-node `duration_ms` |
| **Complete telemetry** | one `trace_id` ties run + nodes + routing + SPL + MCP + LLM + RAG |
| Readiness at a glance | `GET /api/debug/readiness` |
| Liveness + counters | `GET /health` |

## `trace_id` vs `turn_id`

- `trace_id` — telemetry spine key; returned in the chat response; used by `/debug/traces/{trace_id}`.
- `turn_id` — quality-ledger key (`/quality/chat-turns/{turn_id}`).
- They are distinct. The run metadata cross-links `turn_id` so the bundle shows both.

## Sinks

- **db** — events in Postgres (`ai_trace_runs` + child tables). Full read API.
- **file** — append-only NDJSON, one file per UTC day under `AI_SOC_TELEMETRY_FILE_DIR`.
  Same redaction; the read API reconstructs runs/timeline from the files. For
  air-gapped sites without a telemetry DB.
- **none** — telemetry disabled (no-op connector).

## Log correlation

Every `ai_soc.*` log record carries `trace_id` (a `LogRecordFactory` stamps it
from a contextvar set at chat entry; `-` outside a request). Include
`%(trace_id)s` in the log format to pivot from a trace to app logs and back.

## Guarantees

- All `/debug` output is redacted (no secrets, prompts-with-data, or raw events).
- Telemetry writes are best-effort: a telemetry failure never breaks a chat turn.
- The Experience Center fixture path emits no live traces.


## Trace authority tiers (handoff discipline)

`control_plane_trace` and governance panels label fields with `authority_tier` and
`authority_note` so analysts can separate authoritative final-run state from planning,
advisory, and diagnostic shadow data.

| Tier | Examples |
|------|----------|
| **AUTHORITATIVE** | `run_contract`, `final_evidence_gate`, `route_adjudication`, final MCP execution decision |
| **PLANNING** | `evidence_plan`, `resource_planner`, `slot_constraint_projection` |
| **ADVISORY** | `llm_intent_advisory`, `llm_advisory_trace`, RAG hints, catalogue advisory matches |
| **DIAGNOSTIC** | `route_plan_shadow`, validator reject details, dropped LLM candidates |

`trace_authority_index` on `control_plane_trace` maps each section to its tier.
LLM dropped reasons are **ADVISORY** — they are not final routing failure unless
`route_adjudication` / `RunContract` says so.
