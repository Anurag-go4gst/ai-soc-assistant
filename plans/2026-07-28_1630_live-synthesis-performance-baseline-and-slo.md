---
name: live-synthesis-performance-baseline
overview: "Measure live synthesis latency (cold/warm percentiles, timeout/fallback rates, path timing) before any SLO declaration; keep probes outside CI; sanitize committed artifacts."
status: proposed
date: 2026-07-28
canonical_plan: plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md
depends_on: none
---

# Live Synthesis Performance Baseline and SLO

## Objective

Establish an **evidence-based** performance baseline for live LLM synthesis (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`) before declaring SLO targets or optimization work. Split **instrumentation/benchmarking** (phase 1) from **optimization** (phase 2).

**Not a correctness defect** (cutover gap 4). Does not block outcome-invariant hardening.

## Stop conditions

- Phase 1 baseline artifact published (sanitized) with cold/warm percentiles, **or**
- COE defers live synthesis on production until baseline complete, **or**
- Instrumentation gate fails twice

## Locked decisions (draft)

| ID | Decision |
|----|----------|
| P1 | **No SLO targets** until phase 1 baseline is measured and reviewed |
| P2 | Live probes run **outside CI** (manual or scheduled ops job); never block merge gates |
| P3 | Committed artifacts **sanitized** — no prompts, credentials, or raw analyst queries |
| P4 | Report **cold and warm** separately (KV-cache / server warm-up) |
| P5 | Break down **endpoint vs application** time (HTTP to LLM vs pipeline overhead) |

## Dependency order

Independent of workstreams A–D. Recommended after C (ops closeout) if production probes required.

`P0 → P1 → P2` (phase 2 only after COE review of P1 artifact)

## Phase 1 — Instrumentation and baseline (skeleton)

- [ ] **P0** — Timing instrumentation spec
  - **Do:** Document probe points: synthesis invoke start/end, adapter HTTP round-trip, fallback path, timeout events. Align with `/llm-live-probe` skill rubric.
  - **Verify:** `docs/evals/live_synthesis_performance_methodology.md` reviewed
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **P1** — Baseline measurement run
  - **Do:** Run closed case set on production-like endpoint (:8081 or configured role URL); record cold/warm **p50/p90/p95**, timeout rate, fallback rate, synthesis-path segments
  - **Verify:** Sanitized artifact under `docs/evals/live_synthesis_baseline_<date>.json` (or gitignored template + committed summary only)
  - **Depends on:** P0
  - **Evidence:** _(fill when done)_

- [ ] **P1b** — Ops runbook
  - **Do:** How to re-run baseline; how to compare regressions; explicit “not in CI”
  - **Verify:** Section in `docs/coe/COE_ROLLOUT_CONFIGURATION.md` or linked ops doc
  - **Depends on:** P1
  - **Evidence:** _(fill when done)_

## Phase 2 — Optimization and SLO (deferred until P1)

- [ ] **P2** — COE-reviewed SLO proposal
  - **Do:** Propose targets from P1 data only; optimization candidates ranked by measured share of latency
  - **Verify:** COE sign-off recorded in plan drift log
  - **Depends on:** P1 + P1b
  - **Evidence:** _(fill when done)_

## Metrics required (minimum)

| Metric | Required |
|--------|----------|
| Cold p50 / p90 / p95 | Yes |
| Warm p50 / p90 / p95 | Yes |
| Timeout rate | Yes |
| Fallback to deterministic draft rate | Yes |
| Synthesis-path timing (app segments) | Yes |
| Endpoint HTTP timing | Yes |
| Per-turn total (smoke correlation) | Yes |

## Out of scope

- Changing synthesis authority (facts remain deterministic)
- EC / demo path live model calls
- CI integration of live probes

## Drift log

| Date | Note |
|------|------|
| 2026-07-28 | Skeleton created from gap reconciliation disposition #4 |
