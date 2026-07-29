# Live synthesis performance methodology (workstream E)

**Status:** phase 2 harness wiring (no SLO targets; no live probes in CI)
**Date:** 2026-07-28
**Plan:** [`plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`](../../plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md)

## Objective

Measure live synthesis latency with segment breakdown **before** declaring SLO targets or optimization work. Probes run **outside CI**; committed artifacts are sanitized.

## Instrumentation probe points

| Segment | Probe location | Notes |
|---------|----------------|-------|
| `canonical_planning_ms` | `run_canonical_planning` (shared imperative + RP seam) | Lane, completeness, route resolution |
| `retrieval_spl_ms` | Close at `graph_node_context_finalize` before synthesis lab | RAG retrieval, SPL validation/generation, dispatch hooks |
| `synthesis_endpoint_ms` | `run_governed_synthesis_lab` narration + `compose_governed_answer` | HTTP round-trip to configured synthesis endpoint |
| `application_overhead_ms` | Derived | `end_to_end` minus measured segments |
| `end_to_end_ms` | Turn scope start → `finalize_turn_timing` | Imperative + RP `/chat` paths |

## Trace surface

Sanitized payload is attached to `control_plane_trace.turn_timing` on live `/chat` responses.

### Metric schema (`schema_version: "1"`)

```json
{
  "schema_version": "1",
  "run_kind": "cold|warm|unknown",
  "synthesis_path": "lab|composer|skipped",
  "outcome": "completed|timeout|fallback|skipped|disabled|blocked",
  "timeout_applied": false,
  "fallback_used": false,
  "segments_ms": {
    "canonical_planning": 5000,
    "retrieval_spl": 12000,
    "synthesis_endpoint": 45000,
    "application_overhead": 2000,
    "end_to_end": 64000
  },
  "endpoint_detail": {
    "provider_label": "local_or_failover",
    "model": "foundation-sec-8b-instruct",
    "http_round_trip_ms": 45000
  }
}
```

**Excluded from artifacts:** prompts, analyst queries, credentials, raw model output.

## Cold vs warm and harness labels

| Class | Rule |
|-------|------|
| **server `run_kind`** | Authoritative when present on `control_plane_trace.turn_timing` (often `unknown` on current production) |
| **`matrix_run_kind`** | Fixed approved label per E-P1…E-P6 — experimental test sequencing only |
| **`sequence_position`** | `first` for the first probe in the invocation; `subsequent` for all later probes |
| **`pair_id` / `pair_position`** | Repeat-pair posture: `knowledge_pair` (E-P1/E-P2), `alert_pair` (E-P3/E-P4), or `standalone` (E-P5/E-P6) |

Important:

- Matrix cold/warm is **experimental test sequencing**; it does **not** prove model-server cache state.
- E-P5/E-P6 are standalone first observations (`cold-intent`), not verified cold endpoint runs.
- `server_run_kind` remains authoritative when available; harness labels never overwrite it.
- Repeat pairs reuse the same application session posture within a run (session identifiers are never stored in reports).

Aligns with [`/llm-live-probe`](../../.claude/skills/llm-live-probe/SKILL.md) KV-cache guidance for operator interpretation only.

## Benchmark harness

```bash
PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub --json /tmp/live_synth_baseline_stub.json
PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --matrix
PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --estimate
```

### Live harness safety contract (phase 2 wiring)

Live probes require **all** of:

1. `--live` and `--confirm-live`
2. `AI_SOC_LIVE_BENCHMARK_AUTHORIZED=1`
3. Approved `--cases` from fixed E-P1…E-P6 definitions (no arbitrary query CLI)
4. `--base-url` pointing at the target backend
5. Auth via environment only (`APP_AUTH_USER` / `APP_AUTH_PASSWORD` when auth enabled)
6. Sequential execution, max six probes, no retries, bounded per-probe timeout
7. Default scratch output under `/tmp/live_synthesis_benchmark_report.json`

Fail closed when `/health` or migrations are not ready, any live/remediation connector is selectable, `workflow_plan.execution_enabled=true`, HTTP non-success, request timeout, or `turn_timing` is malformed.

Mock-only production posture is accepted when effective evidence confirms:

- registry `mode=mock` and `discovery_status=mock` with `status_detail=mock` (effective `MockMcpConnector` posture);
- executable MCP server list contains mock transport only;
- no live Splunk URL/token is configured;
- no live Splunk provider or remediation/write connector is selectable.

`MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true` are **allowed** in mock mode.

Committed live reports use `evidence_class=exploratory_live_wiring_validation` — **not** an SLO baseline. Per-run labels stored: `matrix_run_kind`, `sequence_position`, `pair_id`, `pair_position`, and `server_run_kind`.

### Error codes in committed JSON

Only bounded allowlisted codes may appear in report `error` / `abort_reason` fields:

`authorization_missing`, `health_not_ready`, `migrations_not_ready`, `live_connector_selectable`, `authentication_failed`, `http_non_success`, `request_timeout`, `malformed_turn_timing`, `execution_enabled`, `response_invalid`, `unexpected_client_error`.

No raw exception text, response bodies, headers, URLs, usernames, prompts, answers, tokens, cookies, or session identifiers are stored.

### Operator command (after merge to production `master`)

Run from the production checkout on merged `master`. `APP_AUTH_USER` and `APP_AUTH_PASSWORD` must already be exported in the **approved operator shell** (password manager export, locked CI secret injection, or `docker compose exec` env) — **do not** `source .env` for harness runs.

Why: production `.env` is Docker Compose dotenv (comma-containing values such as `SPL_ALLOWED_SOURCETYPES` are valid there) but is **not** valid POSIX shell syntax; `source .env` can emit `command not found` noise and does not reliably export auth vars.

```bash
cd /var/www/ai-soc-assistant
test -n "${APP_AUTH_USER:-}" || { echo "APP_AUTH_USER missing"; exit 1; }
test -n "${APP_AUTH_PASSWORD:-}" || { echo "APP_AUTH_PASSWORD missing"; exit 1; }
export AI_SOC_LIVE_BENCHMARK_AUTHORIZED=1

PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py \
  --live \
  --confirm-live \
  --base-url 'https://cisco-vai.vnudge.com' \
  --cases E-P1,E-P2,E-P3,E-P4,E-P5,E-P6 \
  --probe-timeout-s 300 \
  --inter-probe-pause-s 2 \
  --json /tmp/live_synthesis_benchmark_report.json
```

### Runtime guidance

| Item | Value |
|------|-------|
| Expected heuristic duration | approximately **10–15 minutes** |
| Maximum timeout-bound duration | approximately **30 minutes** plus preflight |
| Retries | none |
| Abort policy | first timeout, non-200, or safety violation aborts remaining probes |
| Partial output | sanitized partial report retained on abort |

Do not run live probes in CI.

## Synthesis wall-clock budget (runtime remediation)

| Layer | Owner | Production value | Role |
|-------|-------|------------------|------|
| Nginx `/api/` `proxy_read_timeout` | Nginx | **240s** | Gateway ceiling — not the primary remediation lever |
| Harness `--probe-timeout-s` | benchmark CLI | **300s** | Client-side upper bound (diagnostic only) |
| `live_synthesis_timeout_seconds()` | `progress_events` | **120s** | **Total** narration + failover wall-clock budget |
| `AI_SOC_LLM_TIMEOUT_SECONDS` | env / settings | operator value (e.g. 90) | Per-hop socket cap for synthesis (no silent 120s floor) |
| Sidecar socket ceiling | `endpoint_resolver` | 120s max | Sidecar paths only |

Worst-case before remediation (E5-run-2): `ThreadPoolExecutor` shutdown joined sequential failover hops (`max(configured,120)` per hop) → ~240s gateway 504 with zero `turn_timing`.

Corrected contract: one monotonic deadline across primary + all failovers; governed deterministic fallback and `turn_timing` (timeout/fallback flags) return before the 240s gateway ceiling.

## Proposed limited baseline probe matrix (phase 2)

| Case | Profile | Matrix label | Pair | Rationale |
|------|---------|--------------|------|-----------|
| E-P1 | `knowledge_recall` | cold | knowledge_pair / first | RAG-heavy, no SPL |
| E-P2 | `knowledge_recall` | warm | knowledge_pair / repeat | Repeat within knowledge pair |
| E-P3 | `alert_summary` | cold | alert_pair / first | Template + MITRE path |
| E-P4 | `alert_summary` | warm | alert_pair / repeat | Repeat within alert pair |
| E-P5 | `guided_investigation` | cold-intent | standalone | Composer path (standalone first observation) |
| E-P6 | `spl_generation` | cold-intent | standalone | SPL segment stress (generation only) |

Estimated runtime: approximately **10–15 minutes** heuristic; timeout-bound ceiling approximately **30 minutes** plus preflight.

## SLO policy

**No SLO targets** until sanitized baseline artifact is reviewed by COE. Phase 2 optimization is out of scope for phase 1.
