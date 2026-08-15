# Plan 7 D1 — reliability and failure behaviour on the target posture

Artifacts: `d1_reliability.json`, `d1_db_failure.json`. Harness:
`scripts/eval_plan7_d1_reliability.py` (runs inside the backend container; D0 established the
dispatch seam is unreachable outside it).

## Exact target flags (read back from the running container)

```
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED     = true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED        = false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED   = true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS = 120.0
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED = false
MCP_MODE                                   = mock
```

## Human-only model restart

`architecture.md` makes Cisco model restart human-only. **No model restart was performed,
requested, scheduled or automated in D1.** `llama-server` ran unbroken throughout (same PID,
uptime 01:21:38 at the restart-row check). `HUMAN_RESTART_REQUIRED` did **not** occur. The
restart/recreate row exercises the **application container only**, which the Plan 7 deployment
workflow already authorizes.

## Failure taxonomy correction (Step 2)

Confirmed at `sidecar_governance.py`: `except Exception` returned `timed_out=True` with note
`llm_assist_timed_out`, so a provider error was indistinguishable from a timeout — the exact
ambiguity the LLM-unavailable and LLM-timeout rows must resolve.

Smallest correction: `SidecarLlmCallResult.failure_kind` (`timeout` / `provider_unavailable` /
`pool_rejected` / `slot_busy`) plus note `llm_provider_unavailable`. **`timed_out` keeps its
existing meaning** for the many callers that branch on it, so no downstream behaviour changed;
T4 derives its reported class from `failure_kind`, and `failure_kind` is exposed on
`debug_summary`. Verified by 7 failing-first tests.

One existing test pinned the defect (`test_slot_released_on_provider_error` asserted a provider
error emits `llm_assist_timed_out`). Its real subject — slot release — is preserved; only the
note assertion was corrected, and a `failure_kind` assertion added.

## API liveness vs inference health

Both measured, and they disagree in two independent places:

| Surface | Liveness | Usable health |
|---|---|---|
| Cisco model | `/v1/models` = **200** while the host was swap-thrashing and generation took >360 s (C3) | only a bounded **inference probe** shows it |
| Database | `/health` = **200** with postgres stopped | `readiness.database_migrations.ready` correctly flips to **false** |

The DB surface already separates them; the model surface does not. Recorded, not fixed here.

## The ten mandatory classes

| # | CLASS | METHOD | LIVE/INJ | EXPECTED | OBSERVED | FAILURE_TYPE | DEGRADE | DUP SIDE EFFECT | VERDICT |
|---|---|---|---|---|---|---|---|---|---|
| 1 | restart/recreate | app container `--force-recreate` | live | authority survives, no replay | health 200→200; flags unchanged; 5 post-restart rows identical to D0 (`resource_plan_step_walk`, merge active, `spl_postprocessor`, `execution_eligible` null) | — | n/a | **none** | **PASS** |
| 2 | concurrency | 3 bounded concurrent turns | live (orch) | all complete, no shared-state bleed | 3/3 completed, 0 failed, **3 distinct trace_ids**, wall 1868 ms | — | n/a | **0 gate calls, 0 allowed** | **PASS** |
| 3 | repeated identical | 3 identical turns | live (orch) | stable contract, no replay | 3 distinct trace_ids, single route `spl_generation`, **schedules identical**, gate delta **0/0** | — | n/a | **none** | **PASS** |
| 4 | latency p50/p95 | 5 orchestration samples | live (orch) | bounded | **p50 853 ms, p95 993 ms** (orchestration with recorded T4). Live-model latency is C3's: p50 ≈36 s, p95 ≈39 s, warm-up 55.3 s cold | — | n/a | n/a | **PASS (scoped)** |
| 5 | LLM unavailable | `ConnectionRefusedError` at provider seam | injected | classified as unavailable, not timeout | `rejected=['provider_unavailable']`, `failure_kind=provider_unavailable`, **`timed_out=False`** | provider_unavailable | deterministic contract kept | **0 allowed** | **PASS** |
| 6 | malformed LLM output | non-JSON prose | injected | rejected, nothing enters authority | `rejected=['schema_invalid']`, not timeout, not provider error | schema_invalid | deterministic contract kept | none | **PASS** |
| 7 | LLM timeout | slow provider vs 1 s bound | injected | distinct from unavailable | `rejected=['timed_out']`, `timed_out=True`, `failure_kind=timeout`, elapsed 1000 ms | timeout | deterministic contract kept | none | **PASS** |
| 8 | DB failure/recovery | `docker compose stop/start postgres` (the procedure Plan 6 F3 already executed and committed) | live | safe degradation + clean recovery | health 200 with `ready:false`; chat **succeeded** but `dispatch_source` fell to `canonical_non_planned`; after restart back to `resource_plan_step_walk` | — | answers without ResourcePlan authority | **none** | **PASS with finding** |
| 9 | MCP unavailable | `ConnectionError` at `evaluate_mcp_execution` | injected | visible, no fabrication | `mcp_status=requires_human_review`, `execution_eligible=null`, no exception reached the caller | — | HIL preserved | **0 allowed** | **PASS** |
| 10 | model-slot pressure | 3 concurrent T4 turns vs a 3 s provider | injected | bounded shedding | **1 acquired** (accepted, elapsed 3001 ms), **2 shed** `failure_kind=slot_busy` in ~2.4 s | slot_busy | deterministic fallback | none | **PASS** |

`side_effect_totals` across the whole run: **`gate_calls: 1`, `allowed: 0`.**

## Two measurement flaws found in my own harness, corrected not reported

1. **Slot pressure was initially invalid.** The recorded provider returns instantly, so the
   single-flight semaphore was never contended and the row read `slot_busy_notes: 0`. Reporting
   that as a pass would have claimed bounded shedding that was never exercised. Re-measured with
   a 3 s provider; the superseded row is retained in the JSON and labelled.
2. **Rows were truncated at 900 chars** in the harness's own stdout, and the container `/tmp`
   was wiped by the restart row before the artifact was copied out — three rows became
   unreconstructable. Fixed (full payload printed) and re-run rather than reconstructing
   partial rows.

## Findings carried forward

**F1 — DB loss silently downgrades execution authority. `KNOWN_PLAN8_DEPENDENCY`.**
With postgres stopped the ResourcePlan cannot be committed, so the turn falls back to
`canonical_non_planned` and still answers. It is *safe* — nothing executed, nothing fabricated,
`execution_eligible` null, gates intact, recovery clean — but the target architecture's authority
disappears with no analyst-visible degrade signal. This is the health/degradation-signalling role
Plan 8 REL0 owns; it is not a Plan 7 patch, and D1 did not add one.

**F2 — model liveness ≠ usable inference health. `KNOWN_PLAN8_DEPENDENCY`.**
`/v1/models` returns 200 through a fully unusable model. Production health checks therefore
cannot detect the serving state that produced C3's 2/9 → 1/4 → 4/4 variance. Detection and
recovery are Plan 8 REL0; the existing manual procedure (`systemctl restart llama-server`, or the
`llm-control-watcher` control directory) remains **human-only**.

**F3 — serving stability remains unresolved (C3 carry-over).** D1 measured orchestration
reliability with a recorded proposal; it contributes **no** evidence that the live model is
reliably available. `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` stands.

## What D1 establishes

All ten mandatory classes have measured rows; every failure class is now reported truthfully and
distinguishably; no duplicate side effect was observed anywhere; degradation was deterministic
and bounded in every injected failure.

D1 completion is **not** production GO. The two `KNOWN_PLAN8_DEPENDENCY` findings and the
unresolved serving blocker travel to E2, which per the amendment treats T4 as a hard GO
requirement.
