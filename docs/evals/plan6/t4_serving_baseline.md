# Plan 6 D0 — T4 serving baseline (VPS, timeout 2.0s)

Endpoint: `resolve_local_primary_endpoint(sidecar=True)` only. Timeout stayed **2.0s**. Load at enable: `1.60 2.26 1.77`. Git SHA `1d32ac66dd6c707789db8b44574bd566af401952`.

JSON: `docs/evals/plan6/t4_serving_baseline.json`.

T4 was enabled on restored Arm A (exec OFF, v2 ON), then restored **OFF**.

## Failing-first: hop invoked on the 8 paraphrases

Yes. All 8 residual paraphrases plus `p6.t4.out_of_registry` show `control_plane_trace.resolved_query.semantic_t4.invoked=true`.

`debug_summary.resolved_query.semantic_t4` was **null** on the first harness pass because `redact_resolved_query` ran twice and looked only under `provenance`. CP trace had the status. Fixed to pass through an already-redacted top-level `semantic_t4` block. Metrics below are from CP traces.

## Serial (concurrency 1)

| Metric | Value |
|---|---|
| T4 rows | 9 (8 paraphrases + 1 out-of-registry) |
| invoked | **9/9** |
| accepted | **0/9** |
| timed_out | **9/9** (~2000–2003 ms hop) |
| empty_output | 0 |
| `llm_model_slot_busy` | 0 |
| paraphrase `/chat` p50 | 38784 ms |
| paraphrase `/chat` p95 | 42320 ms |
| cold first paraphrase `/chat` | 39294 ms |
| hop cold vs warm | all timeouts; no accepted contract, so no KV-cache warm win at 2.0s |

Same shape as Plan 5 D0 (8/8 invoked, 0 accepted, timeouts at 2.0s). The hop never returns a usable contract inside the SLO.

## T1–T3 controls (T4 flag ON)

| row_id | tier | semantic_t4 | wall_ms |
|---|---|---|---|
| p6.t1.knowledge | T2 | **null (not invoked)** | 15839 |
| p6.t2.known_nontrivial | T2 | **null** | 37936 |
| p6.live_posture.d1_003 | T1 | **null** | 30347 |

**Zero** T4 invocations on T1–T3. Flag-on does not tax known tiers.

## Concurrency N=2

Two paraphrases in parallel. Pair wall 34786 ms.

| row | hop | `/chat` wall |
|---|---|---|
| p6.para.003 | timed_out 2002 ms | 34641 ms |
| p6.para.004 | empty_output + `llm_model_slot_busy` | 1344 ms |

Slot-busy rate **1/2** under N=2. Matches Plan 5 D0’s concurrent empty/slot-busy pattern.

## `/chat` latency impact

T4 hop adds a bounded **2.0s timeout** on T4 turns only (then deterministic contract is kept). T1–T3 pay **0** hop time. Paraphrase `/chat` is still 33–42s from the rest of the pipeline; the 2.0s hop is not the dominant cost. Guided T4 `p6.t4.out_of_registry` was 92s `/chat`.

## Restore

`AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=false`, exec false, v2 true. health_ok. pytest `test_semantic_t4_understanding.py` 14 passed.
