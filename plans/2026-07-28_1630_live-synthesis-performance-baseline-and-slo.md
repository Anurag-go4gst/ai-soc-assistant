---
name: live-synthesis-performance-baseline
overview: "Measure live synthesis latency (cold/warm percentiles, timeout/fallback rates, path timing) before any SLO declaration; keep probes outside CI; sanitize committed artifacts."
status: in_progress
date: 2026-07-28
canonical_plan: plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md
depends_on: none
workstream: E
execution_scope: Phase 2 harness wiring (E5-wiring); no live probes or SLO
implementation_branch: feat/live-synthesis-perf-phase2-harness
implementation_worktree: .worktree-live-synthesis-phase2
baseline: 42bc899a519ba1c2cf326181952538e6222ac9fb
---

# Live Synthesis Performance Baseline and SLO

## Objective

Establish an **evidence-based** performance baseline for live LLM synthesis (`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED`) before declaring SLO targets or optimization work. Split **instrumentation/benchmarking** (phase 1) from **optimization** (phase 2).

**Not a correctness defect** (cutover gap 4). Does not block workstreams A–D.

## Stop conditions

- Phase 1 checklist E0–E4 checked with evidence, **or**
- COE defers live synthesis on production until baseline complete, **or**
- Instrumentation gate fails twice

## Locked decisions

| ID | Decision |
|----|----------|
| P1 | **No SLO targets** until phase 2 after controlled baseline review |
| P2 | Live probes run **outside CI** (manual or scheduled ops job); never block merge gates |
| P3 | Committed artifacts **sanitized** — no prompts, credentials, or raw analyst queries |
| P4 | Report **cold and warm** separately (KV-cache / server warm-up) |
| P5 | Break down **endpoint vs application** time (HTTP to LLM vs pipeline overhead) |
| P6 | Phase 1 uses **stub/deterministic harness tests** only; `--live` deferred |

## Dependency order

Independent of workstreams A–D. Recommended after workstream C operator attestation for production probes.

`E0 → E1 → E2 → E3 → E4` (phase 2 `E5+` deferred)

## Phase 1 — Instrumentation and harness (this PR)

- [x] **E0** — Methodology + metric schema
  - **Do:** Add `docs/evals/live_synthesis_performance_methodology.md` with segment definitions and sanitized schema
  - **Verify:** `test -f docs/evals/live_synthesis_performance_methodology.md`
  - **Depends on:** none
  - **Evidence:** methodology doc committed with schema_version 1 fields

- [x] **E1** — Turn timing instrumentation
  - **Do:** Add `app/synthesis/turn_timing.py`; wire canonical planning, retrieval/SPL close, lab/composer endpoint timing, `control_plane_trace.turn_timing`
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_synthesis_turn_timing.py -q`
  - **Depends on:** E0
  - **Evidence:** 4 passed `test_synthesis_turn_timing.py`

- [x] **E2** — Benchmark harness
  - **Do:** Add `app/evals/live_synthesis_benchmark.py` + `scripts/run_live_synthesis_baseline_benchmark.py` (`--stub`, `--matrix`, `--estimate`; `--live` exits 2)
  - **Verify:** `PYTHONPATH=backend:. python3 scripts/run_live_synthesis_baseline_benchmark.py --stub --json /tmp/live_synth_stub.json`
  - **Depends on:** E1
  - **Evidence:** stub JSON with summary percentiles + 6 probes

- [x] **E3** — Harness unit tests
  - **Do:** Add `test_live_synthesis_benchmark.py`
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_live_synthesis_benchmark.py -q`
  - **Depends on:** E2
  - **Evidence:** 3 passed `test_live_synthesis_benchmark.py`

- [x] **E4** — Phase 1 gates (no full pytest/governance)
  - **Do:** Run `git diff --check`; plan discipline audit
  - **Verify:** `git diff --check`; `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-28_1630_live-synthesis-performance-baseline-and-slo.md`
  - **Depends on:** E3
  - **Evidence:** `git diff --check` clean; plan audit 5 checked / 0 gaps; pytest 7/7 (timing + harness)

## Phase 2 — Live harness wiring (draft PR; no live probes in CI)

- [x] **E5-wiring** — Controlled live harness (`--live` path)
  - **Do:** Wire `run_live_benchmark` + CLI gates (`--confirm-live`, `AI_SOC_LIVE_BENCHMARK_AUTHORIZED=1`, approved case ids, auth via env, sequential/no-retry, `/tmp` default output)
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_live_synthesis_benchmark.py -q`
  - **Depends on:** E4
  - **Evidence:** 27 passed `test_live_synthesis_benchmark.py`; 35 passed with `test_synthesis_turn_timing.py`; corrective pass on mock-only preflight + pair labels + error allowlist

- [ ] **E5-run** — Controlled live baseline run (operator-only, outside CI)
- [ ] **E6** — COE-reviewed SLO proposal from measured data only
- [ ] **E7** — Optimization candidates ranked by measured latency share

## Metrics required (minimum)

| Metric | Phase 1 instrumented | Phase 2 measured |
|--------|---------------------|------------------|
| Cold p50 / p90 / p95 | schema + stub | live artifact |
| Warm p50 / p90 / p95 | schema + stub | live artifact |
| Timeout rate | yes | live artifact |
| Fallback rate | yes | live artifact |
| Segment timing breakdown | yes | live artifact |
| Endpoint HTTP timing | yes | live artifact |
| Per-turn total | yes | live artifact |

## Out of scope (phase 1)

- Live production synthesis probes
- SLO declaration
- Production configuration changes
- CI integration of live probes
- Changing synthesis authority (facts remain deterministic)

## Drift log

| Date | Note |
|------|------|
| 2026-07-28 | Skeleton created from gap reconciliation disposition #4 |
| 2026-07-28 | Phase 2 corrective pass: mock-only preflight semantics, pair/sequence labels, allowlisted error codes |
