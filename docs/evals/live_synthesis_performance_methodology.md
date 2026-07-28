# Live synthesis performance methodology (workstream E)

**Status:** phase 1 instrumentation (no SLO targets)
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

## Cold vs warm

| Class | Rule |
|-------|------|
| **cold** | First synthesis call in process, or ≥120s since prior synthesis completion |
| **warm** | Subsequent synthesis within 120s |
| **harness override** | `AI_SOC_BENCHMARK_RUN_KIND=cold|warm` (benchmark script only) |

Aligns with [`/llm-live-probe`](../../.claude/skills/llm-live-probe/SKILL.md) KV-cache guidance.

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

Fail closed when `/health` or migrations are not ready, MCP is not mock-only, `workflow_plan.execution_enabled=true`, HTTP non-success, or `turn_timing` is malformed.

Committed live reports use `evidence_class=exploratory_live_wiring_validation` — **not** an SLO baseline. Store `client_run_kind` (first probe cold, subsequent warm) separately from server `turn_timing.run_kind` (may be `unknown`).

```bash
AI_SOC_LIVE_BENCHMARK_AUTHORIZED=1 \\
APP_AUTH_PASSWORD='${APP_AUTH_PASSWORD}' \\
PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py \\
  --live --confirm-live \\
  --base-url https://cisco-vai.vnudge.com \\
  --cases E-P1,E-P2,E-P3,E-P4,E-P5,E-P6 \\
  --json /tmp/live_synthesis_benchmark_report.json
```

Do not run live probes in CI.

## Proposed limited baseline probe matrix (phase 2)

| Case | Profile | Run kind | Rationale |
|------|---------|----------|-----------|
| E-P1 | `knowledge_recall` | cold | RAG-heavy, no SPL |
| E-P2 | `knowledge_recall` | warm | KV-cache warm repeat |
| E-P3 | `alert_summary` | cold | Template + MITRE path |
| E-P4 | `alert_summary` | warm | Warm repeat |
| E-P5 | `guided_investigation` | cold | Composer path |
| E-P6 | `spl_generation` | cold | SPL segment stress (synthesis often skipped) |

Estimated runtime (heuristic from 90–240s/turn smoke): **~13–15 minutes** for six probes on single-slot VPS. Re-estimate from phase-1 stub schema before live run.

## SLO policy

**No SLO targets** until sanitized baseline artifact is reviewed by COE. Phase 2 optimization is out of scope for phase 1.
