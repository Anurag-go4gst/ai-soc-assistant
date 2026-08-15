# Plan 8 U3 — T4 serving/contract revalidation after U2

Inherited Plan 7 C3 posture **unchanged:** `REMEDIATE_EXISTING_T4_IN_PLACE`. No model, provider, timeout, flag, or deployment change. No Cisco restart.

## Verify

```
PYTHONPATH=backend:. python3 scripts/eval_canonical_t4_serving.py --check
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_semantic_t4_understanding.py app/tests/test_t4_job_aware_invocation.py -q
```

`--check` **ok** (0 safety failures). Pytest **18 passed**.

## Contract vs Plan 7 C3

| Check | C3 (`c3_remeasurement.json`) | U3 after U1/U2 |
|---|---|---|
| Locked `intent_family` / `answer_goal` | preserved 4/4 | preserved 5/5 |
| Capability widening | none | none |
| Deterministic clarification cleared | no | no |
| C3 four vague queries | T4 invoked 4/4 (upstream already `clarification_required`) | **not invoked** (`next_action=CLARIFY`) — U1 job-aware gate |
| CALL_T4 hunt | not in C3 set | invoked |

U1 skipping T4 on the four C3 queries is a contract correction, not a serving regression. Those rows remain clarification; T4 cannot clear that.

## Serving (in-container, production `host.docker.internal` URL)

Host-side `--check` live hop failed in 19 ms with `provider_unavailable` (`host.docker.internal` does not resolve on the host). Same discarded C3 defect; **not** reported as a T4 timeout.

Inside `backend` container (same URL the app uses):

| | n | accepted | timed out | p50 | p95 |
|---|---|---|---|---|---|
| Live T4 invocations | 1 (`call_t4_hunt`) | **1** | 0 | **62216 ms** | **62216 ms** |
| Job-aware skips | 4 | n/a | n/a | n/a | n/a |

C3 accepted-hop latency was p50 ≈ 36 s / p95 ≈ 39 s (4 samples @ 120 s bound). This is **one** post-U2 sample at 62.2 s, still inside the VPS 120 s bound. It does **not** close F3.

## Disposition

- **C3:** `REMEDIATE_EXISTING_T4_IN_PLACE` preserved.
- **F2:** `/v1/models` HTTP 200 on the host does not prove a host-side hop can reach the configured Docker URL.
- **F3:** `T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER` remains a **CRITICAL BLOCKER**. No new serving decision.
- **HUMAN_RESTART_REQUIRED:** did not arise.
