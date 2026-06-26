# COE Observability & Debugging Mechanism

**Date:** 2026-06-15 (rev 2026-06-16 — plan review applied)
**Branch target:** new `cp-coe-observability`
**Status:** Proposed
**Goal:** Make the AI SOC Assistant debuggable in the COE environment. An operator must be able to answer, for any single `/chat` turn: *was the LLM ready, was MCP ready, which nodes ran in what order and how long, and why did this answer come out this way?* — without reading source or hand-writing SQL.

---

## 1. Principles (scope discipline)

- **Build on the existing connector**, do not invent a new telemetry stack. `DbTelemetryConnector` + Postgres tables + redaction already exist and are partly wired. Close the gaps, don't replace.
- **Observability is read + write.** Today only write exists. The headline deliverable is the **read side**: fetch one trace back, list recent traces, export a debug bundle.
- **Redaction is non-negotiable.** All new surfaces reuse `connectors/telemetry/redaction.py` (`minimize`/`truncate`/payload cap). No secrets, no raw events, no credentials, no prompts-with-data in any persisted or exported payload. Same posture as `/settings` (`*_configured` booleans only).
- **No new flags beyond a sink selector and a debug-API gate.** Honors flag-posture memory.
- **Air-gap first.** COE may forbid external sinks and may or may not want a telemetry DB. Provide a local-file JSONL sink so observability works with `TELEMETRY_MODE` pointed away from DB.
- **EC stays isolated.** Experience Center fixture path (`coe_synthetic_fixture`) must not start emitting live traces; keep the demo early-return untouched.

---

## 2. Where operators see telemetry (today vs after)

### Today (before this plan ships)

| Surface | Location | What you get | Limitation |
|---------|----------|--------------|------------|
| **Per-turn response** | Chat API response JSON (`trace_id`, `control_plane_trace`, `node_trace`, `llm_sidecars`, lineage in analyst card) | Why *this* answer — routing, SPL, MCP gate, governance panels | Ephemeral unless you saved the JSON; no cross-turn list |
| **Settings → Observability** | UI `Settings` page / `GET /api/settings/status` → `observability` block | Telemetry sink, write-failure counter, trace flags | Config only — not per-turn |
| **Health** | `GET /health` | Liveness + `telemetry_write_failures` counter | No trace list |
| **LLM / MCP readiness** | `GET /api/settings/llm/health`, `GET /api/settings/status` (MCP block) | Provider configured/available, MCP server status | Point-in-time — not tied to a specific turn |
| **Quality ledger** | UI Quality page / `GET /api/quality/chat-turns`, `GET /api/quality/chat-turns/{turn_id}` | Redacted turn snapshot (`control_plane_trace`, SPL, MITRE, query) keyed on **`turn_id`** | Analyst review workflow — not a durable event timeline; **`trace_id` ≠ `turn_id`** today |
| **Debug page** | UI sidebar **Debug** | Live COE observability when flag on; disabled/forbidden hints when off | Empty trace list until Phase 0 trace spine ships |
| **Postgres (raw)** | Tables `ai_trace_*`, `routing_*`, `mcp_execution_logs`, etc. | Orphan step rows (no parent run) | Requires SQL; incomplete without Phase 0 |
| **App logs** | Docker / uvicorn stdout | Warnings incl. `telemetry_write_failed` | No `trace_id` stamp on log lines |

### After Phases 0→2 + 2B (API + Debug UI — partial: API/UI landed 2026-06-16; trace spine Phase 0 pending)

| Surface | Location | What you get |
|---------|----------|--------------|
| **Debug UI** | App sidebar → **Debug** (`/debug`, optional `?trace_id=`) | Readiness snapshot, recent traces, event timeline, bundle JSON — requires `AI_SOC_DEBUG_API_ENABLED=true` + role |
| **Debug API — trace list** | `GET /api/debug/traces` (flag + auth + role) | Recent live `/chat` turns: `trace_id`, entrypoint, status, duration, skill, answer_mode |
| **Debug API — timeline** | `GET /api/debug/traces/{trace_id}` | Ordered event spine: run → steps → routing → SPL → MCP → LLM → RAG |
| **Debug API — bundle** | `GET /api/debug/traces/{trace_id}/bundle` | **COE handoff artifact**: timeline + bounded explainability (`control_plane_trace`, lineage, governance, sidecars) |
| **Debug API — readiness** | `GET /api/debug/readiness` (Phase 5) | One-shot LLM + MCP + RAG + telemetry sink health + fallback rates |
| **Per-turn response** | Same as today; `trace_id` now matches `ai_trace_runs.trace_id` | Copy `trace_id` from chat → paste into debug API |
| **Settings / Health** | Expanded counters (Phase 5) | Stage success/failure, LLM-fallback counts, telemetry-disabled signal |
| **App logs** | stdout (Phase 4) | Every `ai_soc.*` log line stamped with `trace_id` |
| **Postgres** | `ai_trace_runs` + child tables | Full durable store when `AI_SOC_TELEMETRY_SINK=db` |
| **File sink** | `AI_SOC_TELEMETRY_FILE_DIR` NDJSON (Phase 3) | Same events as DB, one line per event per day — for air-gap without Postgres |

### `trace_id` vs `turn_id` (explicit contract)

- **`trace_id`** — telemetry spine key. Generated once at live chat entry; returned in `PlaceholderResponse.trace_id`; used by `/debug/traces/{trace_id}`.
- **`turn_id`** — quality-ledger key. Assigned in `post_chat_response` for analyst review (`/quality/chat-turns/{turn_id}`).
- They **remain separate IDs**. `end_trace` metadata must include `turn_id` when available so bundle and quality views cross-link. COE runbook: debug by `trace_id`; promote/review by `turn_id`.

### Optional follow-on (deferred)

- Deep-link from Chat analyst summary card directly to Debug (Cockpit already passes `?trace_id=`).

---

## 3. Current state (verified 2026-06-15)

**Real & wired (write):**
- `connectors/telemetry/db.py` `DbTelemetryConnector` → tables `ai_trace_runs`, `ai_trace_steps`, `routing_decisions`, `routing_disagreements`, `spl_validation_results`, `mcp_execution_logs`, `rag_retrieval_logs`, `llm_call_logs`, `harness_test_runs`, `harness_test_case_results`, `user_feedback` (migration `0001_ai_soc_telemetry.sql`).
- `start_trace` / `end_trace` **already exist** on `TelemetryConnector`, `DbTelemetryConnector`, and `NullTelemetryConnector` — but `start_trace` is **not called** on live `/chat` (only harness import uses it).
- `redaction.py` minimize/truncate + `MAX_SERIALIZED_PAYLOAD_BYTES`.
- `null.py` no-op connector; selector in `connectors/telemetry/__init__.py` (`TELEMETRY_MODE`, `AI_SOC_TELEMETRY_SINK`).
- `metrics.py` two in-process counters (`telemetry_write_failures`, `telemetry_writes_skipped_null`).
- Call sites: `chat/pipeline.py` (`record_step`, `record_spl_validation`), `routing/skill_router.py` (routing decision/disagreement), `orchestration/mcp_execution_gate.py` (rich `record_mcp_execution`, 15 event types), `routing/operation_audit_store.py` (`record_step`).
- **Response-embedded trace (Batch 4):** `chat/pipeline_visibility.py` builds `node_trace` in the response JSON — complements but does not replace durable DB timing (G6).

**Readiness (already good):** `/health`, `/settings/status`, `/settings/providers/status`, `/settings/llm/health`, `/settings/llm/check`, `/settings/providers/check`.

**Explainability in response (already good):** `control_plane_trace`, `lineage/builder.build_investigation_lineage`, `governance/trace_panels.build_governance_trace`, `chat/pipeline_visibility.py`, `llm_sidecars`.

**Overlap to respect (not duplicate):**
- **Quality ledger** (`quality/store.py`) stores a redacted answer snapshot per `turn_id` — analyst review, not event timeline.
- **Response `node_trace`** — per-turn packaging in JSON; Phase 1 DB rows add `duration_ms` + queryable sequence.

**Gaps:**
| # | Gap | Impact at COE |
|---|-----|---------------|
| G1 | No read API/CLI for persisted traces | Debug = raw SQL |
| G2 | `start_trace` never called on live `/chat` | No parent run, no timing, orphan steps, can't list turns |
| G3 | `record_llm_call` / `record_rag_retrieval` never called | LLM/RAG readiness-per-turn not captured |
| G4 | Dead stubs `app/telemetry/{decision_trace,node_trace,route_comparison,telemetry_sink}.py`, `audit/logger.py` | Confusion, false sense of coverage |
| G5 | No file/JSONL sink | Air-gapped COE w/o telemetry DB has nothing |
| G6 | No per-node **durable** timing/sequence in DB | "Which nodes ran, how long" unanswerable across turns |
| G7 | Logs not stamped with `trace_id` | Can't correlate app logs to a turn |
| G8 | No single-trace debug-bundle export | No clean repro handoff |

---

## 4. Telemetry sink matrix

Update `SUPPORTED_TELEMETRY_SINKS` in `config.py` to include `file` (Phase 3). `splunk` / `both` remain **startup fail-fast** (reserved, not implemented).

| `TELEMETRY_MODE` | `AI_SOC_TELEMETRY_SINK` | Connector |
|-------------------|-------------------------|-----------|
| `none` | any | `NullTelemetryConnector` |
| `db` | `none` | `NullTelemetryConnector` |
| `db` | `db` | `DbTelemetryConnector` → Postgres |
| `db` | `file` | `FileTelemetryConnector` → NDJSON dir (Phase 3) |
| `db` | `splunk` / `both` | **ConfigError at startup** (unchanged) |

---

## 5. Phases

### Phase 0 — Trace spine (G2) — *foundation, do first*

**Canonical hook** — do not only patch `routes_chat.py`. Today `trace_id` is created inside `graph_node_init_routing` (`pipeline.py`); routing steps can run before any parent run exists.

- Add `begin_chat_trace(request, *, entrypoint, user) -> str` (or equivalent) that:
  1. Generates `trace_id` once.
  2. Calls existing `start_trace(trace_id, entrypoint=..., user_id=<role not username>, metadata={route_mode, control_plane_enabled, langgraph_orchestration_enabled})`.
  3. Sets the Phase 4 `contextvars` trace context (stub until Phase 4 lands).
- Call from **all live entrypoints** (NOT EC early-return, NOT `/clear`):
  - `POST /api/chat` (`routes_chat.py`)
  - `POST /api/chat/stream` (`routes_chat_stream.py`)
  - LangGraph path (`run_chat_via_langgraph`) — pass `trace_id` into initial `ChatPipelineState`
  - Imperative path (`build_live_chat_response`) — same
- Refactor `graph_node_init_routing` to **consume** `state["trace_id"]` when present; do not mint a second UUID.
- On response finalize, call existing **`end_trace(trace_id, status=..., metadata={...})`** with terminal state:
  - `status`: `completed` | `human_review` | `blocked` | `error`
  - `metadata` keys (bounded, redacted): `answer_mode`, `selected_skill`, `synthesis_readiness`, `final_answer_validator_pass`, `turn_id` (when assigned), and **refs** to explainability blocks for bundle assembly:
    - `control_plane_trace` (bounded via `_bounded_json` / redaction)
    - `governance_trace` summary
    - `lineage_summary` (not full prose dump)
    - `llm_sidecars` advisory block
- Ensure `PlaceholderResponse.trace_id` equals the telemetry run key end-to-end.
- **Tests:** run row + child steps share one `trace_id`; EC/demo/`coe_synthetic_fixture` write nothing; imperative, LangGraph, and `/chat/stream` parity.

### Phase 1 — Close write coverage (G3, G6)

- **LLM:** wrap every **real** model call (live synthesis in `pipeline.py`, sidecars `mitre_risk_rationale.py`, route-plan candidate, intent advisor, streaming path if synthesis runs there) with `record_llm_call(...)`. Metadata only — no prompt/completion text. When flags disable a call, either omit or record `outcome=skipped` (pick one convention, document in runbook).
- **RAG:** call `record_rag_retrieval(trace_id, collection, query_hash, hit_count, top_score, governance_decision)` in `knowledge/soc_kb_retriever.py`. No chunk text.
- **Per-node timing (G6):** add `traced_node(trace_id, node_name)` context manager → `record_step` with `{node_name, status, duration_ms, started_at}`. Apply at LangGraph node boundaries (`graph/chat_workflow.py`) **and** imperative `graph_node_*` boundaries. **Do not** duplicate response `node_trace` summaries — DB rows are for durable/queryable timing; response `node_trace` stays as-is (Batch 4).
- **Tests:** one row per helper with `duration_ms`; failure → `status=error` + exception class name only.

### Phase 2 — Read side (G1) — *headline deliverable* — **partially landed 2026-06-16**

- Router `api/routes_debug.py` + `connectors/telemetry/read_store.py` + `debug/readiness.py`, mounted under `/api/debug`.
- **Access gate:** `_require_debug_api_access` checks per-user `debug_access` from `app/auth/user_registry.py` (persisted JSON). Users toggle yes/no in **Settings → Profile** (`PATCH /auth/profile`). Role (`analyst`, `soc_lead`, etc.) stays separate from debug permission. Optional break-glass: `AI_SOC_DEBUG_API_USER_ALLOWLIST`. Global kill switch: `AI_SOC_DEBUG_API_ENABLED` (default **`true`**).
- Endpoints (read-only, redacted):
  - `GET /debug/traces?limit=&entrypoint=&status=&since=` — recent runs (+ orphan-step fallback when no `ai_trace_runs` row yet)
  - `GET /debug/traces/{trace_id}` — assembled timeline
  - `GET /debug/traces/{trace_id}/bundle` — run summary + timeline + explainability from run metadata
  - `GET /debug/readiness` — telemetry + LLM + MCP + RAG snapshot
- Index migration `0003_ai_soc_telemetry_indexes.sql`.
- **Tests:** `test_debug_api.py` (flag, role, list, readiness, 404 bundle).

### Phase 2B — Debug UI wiring — **landed 2026-06-16**

Replace mock `DebugPage` with live COE observability UI:

- **API client** (`frontend/src/api/client.ts`): `getDebugTraces`, `getDebugTraceTimeline`, `getDebugTraceBundle`, `getDebugReadiness`.
- **Types** (`frontend/src/types/api.ts`): `DebugTraceRun`, `DebugTraceEvent`, `DebugTraceTimeline`, `DebugTraceBundle`, `DebugReadinessResponse`.
- **Page** (`frontend/src/pages/DebugPage.tsx`):
  - Readiness snapshot panel (telemetry sink, connector, write failures, RAG, debug flag).
  - Recent traces table (click to load).
  - Trace lookup input + `?trace_id=` URL param (deep link from Cockpit).
  - Event timeline + debug bundle JSON viewer.
  - Disabled/forbidden/error states with env hints (mirror Quality page UX).
- **Cockpit link** (`SocCockpit.tsx`): `Open Debug` → `/debug?trace_id={lastTrace.trace_id}`.
- Remove dependency on mock debug panels (`PlannerDecisionPanel`, etc.) from the page shell; legacy mock components may remain in tree unused until Phase 6 cleanup.
- **Tests:** frontend build (`npm run build`); manual smoke with `AI_SOC_DEBUG_API_ENABLED=true` + `APP_AUTH_ROLE=soc_lead`.

### Phase 2.5 — Index + disable visibility (cheap, same commit as Phase 2 or immediately after)

- Index migration (above).
- `/debug/readiness` stub or `/health` expansion: expose `telemetry_write_failures` + connector-disabled boolean.

### Phase 3 — File/JSONL sink for air-gap (G5)

- `FileTelemetryConnector` (`connectors/telemetry/file.py`): append-only NDJSON per day, same redaction, full protocol.
- Extend `SUPPORTED_TELEMETRY_SINKS` + selector for `file`. Env `AI_SOC_TELEMETRY_FILE_DIR`.
- `/debug` read endpoints use file backend reader when sink is `file`.
- **Tests:** write→read parity with db on temp dir.

### Phase 4 — Log correlation (G7)

- `contextvars` `trace_id` + logging filter on `ai_soc.*` records. Set in `begin_chat_trace` (Phase 0).
- Outside a request: `trace_id=-`.
- **Tests:** in-request logs carry active id.

### Phase 5 — Readiness debug consolidation

- `GET /debug/readiness` (same gate) stitches: LLM health, MCP status block, last N `llm_call_logs` / `mcp_execution_logs`, RAG status, telemetry sink health, `metrics.snapshot()`, **connector disabled** signal.
- Expand `metrics.py`: per-stage success/failure + LLM-fallback counters (counts only); surface in `/health` and this endpoint.
- **Tests:** shape contract, redaction, flag gate.

### Phase 6 — Cleanup (G4)

- Delete dead stubs under **`app/telemetry/`** (`decision_trace.py`, `node_trace.py`, `route_comparison.py`, `telemetry_sink.py`) and `audit/logger.py` after confirming no imports (check `app/telemetry/__init__.py`). Redirect any stragglers to connector.
- Update CLAUDE.md + `docs/observability/debugging.md` with the surface map (§2 of this plan).

---

## 6. COE operator runbook (summary)

1. **Bad answer in chat** → copy **`trace_id`** from analyst card or Cockpit → **Debug** page (or API).
2. **Enable debug** (COE): `AI_SOC_DEBUG_API_ENABLED=true`, `APP_AUTH_ROLE=soc_lead` (or allowlist / `AI_SOC_DEBUG_API_ALLOW_ANY_AUTHENTICATED=true` for dev).
3. **UI:** App → **Debug** — readiness, trace list, timeline, bundle JSON.
4. **API:** `GET /api/debug/traces/{trace_id}/bundle` for scripted handoff.
5. **Infra:** Debug readiness panel or `GET /api/debug/readiness`.

---

## 7. Deliverables for COE handoff

- Env block in `.env.example`: `AI_SOC_DEBUG_API_ENABLED`, `AI_SOC_DEBUG_API_USER_ALLOWLIST`, `AI_SOC_DEBUG_API_ALLOW_ANY_AUTHENTICATED`, `APP_AUTH_ROLE`, `AI_SOC_TELEMETRY_SINK`, `AI_SOC_TELEMETRY_FILE_DIR`.
- Debug UI wired at `/debug` (Phase 2B).
- `docs/observability/debugging.md` — runbook + surface map (§2 + §6).
- Governance regression green (`./scripts/run_stage3_governance_regression.sh`).

## 8. Non-goals (explicit)

- No external APM/OTel exporter, no Splunk telemetry write (boundary in CLAUDE.md), no Grafana.
- No change to answer logic, routing, or governance authority — observability only.
- No EC fixture-path tracing.
- No new architecture; no LLM-to-MCP path.

## 9. Sequencing / commits (one class per commit)

0. Trace spine (Phase 0) — all entrypoints + `end_trace` metadata
1. Write coverage: LLM/RAG/node-timing (Phase 1)
2. Read API + bundle + indexes (Phases 2 + 2.5) — **API landed**
2B. Debug UI wiring (Phase 2B) — **landed**
3. File sink (Phase 3)
4. Log correlation (Phase 4)
5. Readiness debug + metrics (Phase 5)
6. Dead-code cleanup + docs (Phase 6)

Phases 0→2 deliver core COE debuggability; 3–6 harden for air-gap and handoff.

## 10. Test additions (beyond per-phase notes)

- Parity: imperative vs LangGraph vs `/chat/stream` → one `ai_trace_runs` row each.
- EC isolation: demo early-return writes no run row.
- `trace_id` stability: all child events share response `trace_id`.
- Redaction: bundle keys never match `_SECRET_KEY_PARTS`.
- Telemetry disabled: flag on + null/disabled connector → empty list with readiness explanation.
