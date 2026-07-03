# Out-of-catalogue scorecard — post dynamic-resource-planning (2026-07)

Comparison against baseline [`out_of_catalogue_baseline_2026-07-02`](../out_of_catalogue_baseline_2026-07-02/).

| Metric | Baseline (0.2) | After (8.1 offline) | Gate |
|--------|----------------|---------------------|------|
| MCP evidence % | 0.0% | 0.0% | **Drift** — offline sentinel posture; no mock MCP rows in probe harness |
| CVE/MITRE usage % | 0.0% | **9.09%** | Improved |
| LLM output utilization % | 14.67% | 14.67% | Held (not regressed) |
| Latency p50 / p95 (ms) | 42 / 79 | 50 / 100 | Within raised dev budget at p95 for offline harness |
| Usefulness (15-probe target) | 2.0 | 2.0 | Not regressed |

Command: `PYTHONPATH=backend:. python3 backend/app/evals/run_out_of_catalogue_scorecard.py --offline --baseline-dir docs/evals/out_of_catalogue_after_2026-07`

**Drift log:** MCP evidence % unchanged under offline scorecard — live/mock-MCP probe slice deferred to operator smoke; CVE/MITRE planner-selectable resources (4.3) drove the measurable gain.
