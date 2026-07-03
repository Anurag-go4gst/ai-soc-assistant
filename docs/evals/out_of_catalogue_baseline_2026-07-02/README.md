# Out-of-catalogue scorecard baseline (2026-07-02)

Plan item **0.2** baseline for `plans/2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md`.

## Artifacts

| File | Mode | Description |
|------|------|-------------|
| `scorecard_offline.jsonl` | Sentinel offline posture | 55 probes, no live LLM/MCP execution |
| `summary_offline.json` | Offline aggregates | Target metrics for Phase 8 comparison |
| `scorecard_live.jsonl` | Host `.env` posture | Same probes without sentinel overlay |
| `summary_live.json` | Live-profile aggregates | Dev-stack reference (LLM/MCP depend on operator env) |

Regenerate:

```bash
cd backend
PYTHONPATH=../backend:.. python3 app/evals/run_out_of_catalogue_scorecard.py --offline --baseline-dir ../docs/evals/out_of_catalogue_baseline_2026-07-02
PYTHONPATH=../backend:.. python3 app/evals/run_out_of_catalogue_scorecard.py --live --baseline-dir ../docs/evals/out_of_catalogue_baseline_2026-07-02
```

## Baseline targets (plan must improve)

Captured from **offline** sentinel run on 2026-07-02:

| Metric | Baseline | Notes |
|--------|----------|-------|
| MCP evidence % | **0.0%** | No `mcp_discovery` / `mcp_search` in final answers today |
| CVE/MITRE usage % | **0.0%** | Planner-selectable CVE/MITRE resources not yet wired |
| LLM output utilization % | **14.67%** | 11 / 75 sidecar calls marked `used` (mostly shadow/dropped) |
| Usefulness (15-probe hand sample) | **2.0** (target rubric) | Pinned probes; human re-score before Phase 8 gate |
| Latency p50 / p95 (offline) | **40 ms / 81 ms** | In-process pipeline, no live model |
| vmstat steal (avg / max) | **0.6% / 2.0%** | `vmstat 1 5` at baseline capture |

## Interpretation

- **MCP 0%** matches current governance: execution flags off, discovery not surfaced as answer evidence class.
- **LLM utilization ~15%** reflects shadow-only resource-plan bridge and advisory hops with deterministic authority winning.
- **Live profile** on this host matches fast deterministic turns (no synthesis endpoint configured in bare runner context).
