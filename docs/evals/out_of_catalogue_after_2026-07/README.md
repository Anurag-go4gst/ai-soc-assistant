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

**Drift log:** MCP evidence % unchanged under offline scorecard — live/mock-MCP probe slice deferred to operator smoke; CVE/MITRE planner-selectable resources (4.3) drove the measurable gain. **Resolved 2026-07-04 — see live section below.**

## Live re-run 2026-07-04 (drift closure, plan `2026-07-04_0428` item 3.1)

15-probe hand-score sample, live dev profile on the VPS: LLM on (`127.0.0.1:8081`, single-slot 8B), mock MCP with execution flags on, corrected budgets (`AI_SOC_LLM_TURN_DEADLINE_SECONDS=210` **and** `AI_SOC_LLM_T2_TURN_DEADLINE_SECONDS=210` — the missing T2 clamp was why the planner bridge never ran before). Includes this plan's intent-advisor consumer gate + candidate-constrained prompt and the O5c match-path fix.

| Metric | Baseline (0.2) | Live 2026-07-04 | Gate |
|--------|----------------|-----------------|------|
| MCP evidence % | 0.0% | **26.67%** | Improved — 4/15 probes carry collected `mcp_discovery` rows |
| CVE/MITRE usage % | 0.0% | **13.33%** | Improved |
| LLM output utilization % | 14.67% | **45.0%** (18/40 calls used) | Improved 3× |
| Latency p50 / p95 | — | 80.6s / 120.1s | Within 210s dev budget; steal avg 0.8% |
| Usefulness (15-probe target) | 2.0 | 2.0 | Not regressed |

Files: `scorecard_live_hand15_2026-07-04.jsonl`, `summary_live_hand15_2026-07-04.json`.

Measurement note: `extract_evidence_classes` originally only counted `execution.status == "executed"` — loop-driven discovery evidence (collected `source_evidence` rows on turns that correctly terminate at the HIL search gate) was invisible, so MCP% was structurally 0 even when mock discovery rows reached the answer. Extractor now also counts collected `mcp_discovery`/`splunk_mcp` source-evidence rows. First re-run before that fix (same probes, same stack) already showed the other gains: LLM util 43.9%, CVE/MITRE 13.33%.

Command: `AI_SOC_LLM_LOCAL_BASE_URL=http://127.0.0.1:8081/v1 PYTHONPATH=backend:. python3 backend/app/evals/run_out_of_catalogue_scorecard.py --live --probes <hand15 bank> --jsonl ... --summary ...`
