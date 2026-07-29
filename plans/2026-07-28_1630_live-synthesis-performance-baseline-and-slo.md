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

- [x] **E5-run-1** — First authorized exploratory run (operator-only)
  - **Do:** Run E-P1…E-P6 once via HTTPS harness against production
  - **Verify:** Inspect `/tmp/live_synthesis_benchmark_report.json` locally; no commit
  - **Depends on:** E5-wiring
  - **Evidence:** PARTIAL_EXPLORATORY — attempted=1, valid_samples=0; E-P1 HTTP 504 @ 120139ms; artifact SHA256 `22f4fbaf…`; no SLO conclusion

- [x] **E5-remediation** — Monotonic synthesis deadline + executor admission (PR #120)
  - **Do:** `narration_deadline.py` monotonic budget; per-hop `hop_timeout_seconds`; remove 120s synthesis floor; persistent executor with slot admission (no queue past deadline); `future.cancel()` on expiry
  - **Verify:** `pytest app/tests/test_synthesis_narration_deadline.py app/tests/test_synthesis_narration_executor_safety.py`; clean-env focused bundle; `run_langgraph_dual_parity_eval.py --check`
  - **Depends on:** E5-run-1
  - **Evidence:** PR #120 @ `fa59008`; deadline+executor tests 23/23; focused bundle 104/104 clean env; parity 120/0/0; P6 6/6 identical on control `aa6c194` and candidate

- [x] **E5-run-2** — Second authorized exploratory run (operator-only)
  - **Do:** Run E-P1…E-P6 once via HTTPS harness against production (no retry)
  - **Verify:** Inspect `/tmp/live_synthesis_benchmark_report_e5_run2.json` locally; no commit
  - **Depends on:** E5-remediation merged (blocked — remediation in draft PR)
  - **Evidence:** PARTIAL_EXPLORATORY — attempted=1, valid_samples=0; E-P1 HTTP 504 @ ~240s (Nginx ceiling); artifact SHA256 `f9f3c1c5…`; compound timeout-stack root cause documented

- [x] **E5-run-2-retry** — Post-`llama-server` restart retry (operator-only, still unauthorized as E5-run-3)
  - **Do:** Restart LLM smoke + single harness retry
  - **Verify:** `/tmp/live_synthesis_benchmark_report_e5_run2_retry.json`
  - **Depends on:** E5-run-2
  - **Evidence:** PARTIAL_EXPLORATORY — same 504 @ ~241s; zero valid `turn_timing` samples; not E5-run-3

- [ ] **E5-run-3** — Third authorized exploratory run (**not authorized**; blocked until remediation merged + fresh operator sign-off)
- [ ] **E6** — COE-reviewed SLO proposal from measured data only (**deferred** — zero valid timing samples after E5-run-2/retry)
- [ ] **E7** — Optimization candidates ranked by measured latency share (**deferred** — prompt-size/model-throughput work needs valid timing first)

## Merge-readiness notes (PR #120, 2026-07-29)

| Gate | Result |
|------|--------|
| Executor/queue safety | PASS — slot admission + 8 executor safety tests |
| P6 differential (clean env) | PASS — 6/6 control `aa6c194` and candidate `fa59008` identical |
| Focused synthesis bundle (clean env) | PASS — 104/104 |
| Governance (clean `env -i`, no DB) | pytest 4617 passed / 11 failed — **10 failure signatures byte-identical to control** on same files (no `DATABASE_URL`); 1 retention test flaky under full-suite order only |
| Parity | 120 exact / 0 approved / 0 critical |
| Nginx | Production stays **240s** `proxy_read_timeout`; no further increase proposed |
| E5-run-3 | **Unauthorized** |

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
| 2026-07-28 | E5-run-1 PARTIAL_EXPLORATORY: harness `urlopen(..., opener=...)` defect; Nginx `proxy_read_timeout=120s` fired before backend response; LLM `url_error:timeout` logged 1s later |
| 2026-07-29 | E5-run-2 + retry: zero-sample 504 @ ~240s (Nginx 240s ceiling); remediation PR #120 adds monotonic deadline + executor admission |
| 2026-07-29 | E5-run-3 not authorized; prompt/throughput optimization deferred until valid timing samples exist |
