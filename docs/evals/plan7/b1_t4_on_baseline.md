# Plan 7 B0/B1 — T4 ON instrumentation and diagnostic baseline

T4 is **ON** at the **2.0 s** bound throughout Plan 7's runtime validation, as required. Nothing
below is suppressed, and T4 was never switched off to make a run green.

Sources: `docs/evals/plan6/runs/20260814T125340Z/` (P0.4 arm F),
`…/20260814T130605Z/` (P0.4 arm D — 8 residual paraphrases + the shared T4 row),
`…/20260814T134610Z/` (A4 arm F, post-fix). **33 row-runs total.**

## B0 — the nine fields, captured per row

Ridden on the existing `debug_summary.resolved_query.semantic_t4` block. **No new env flag.**

| Field | Source | Populated |
|---|---|---|
| invoked | `semantic_t4.invoked` | ✅ |
| contract accepted | `semantic_t4.accepted` | ✅ |
| timeout | `semantic_t4.timed_out` | ✅ |
| malformed / empty output | `semantic_t4.rejected_reasons` | ✅ (none observed) |
| slot-busy | `semantic_t4.notes` allowlist (`llm_model_slot_busy`) | ✅ (none observed) |
| clarification preserved | route + `human_review` on the turn | ✅ |
| capability widening | route/tier/fingerprint vs baseline | ✅ |
| route after failure | `chat.route` | ✅ |
| total latency | harness `wall_ms` + `semantic_t4.elapsed_ms` | ✅ |

## B1 — measured baseline

| Measure | Result |
|---|---|
| Row-runs | **33** |
| T4 invoked | **17** — every T4-tier row, across all three runs |
| T4-tier rows **without** invocation | **0** (failing-first check: T4 really is ON) |
| Invoked on T1–T3 rows | **0** — `semantic_t4` is `null`, qualification correct |
| **Accepted contracts** | **0** |
| Timeouts | **17 / 17** |
| `elapsed_ms` range | **2000 – 2005 ms** — the bound, hit every time |
| Notes observed | `llm_assist_timed_out` ×17, nothing else |
| Malformed / empty output | **0** — the bound is reached before any parse |
| Slot-busy | **0** observed |
| False capability widening | **0** |
| Clarification preserved after failure | ✅ (`p6.clarify` still clarifies) |
| Route after failure | deterministic fallback, identical to the Plan 6 Arm A baseline |

Current outcome, stated plainly:

```
T4 invoked → ~2 s bounded failure → deterministic safe fallback / clarification
```

## Assessment

**Qualification is correct; serving is not.** The hop fires exactly where it should, never where
it should not, degrades safely every time, and has never once widened a capability or lost a
clarification. It has also never produced a usable contract.

This is acceptable as **diagnostic** evidence for the architecture remediation phase. It is **not**
sufficient for production activation: per Plan 7's E2 amendment, T4 is a **hard GO requirement**
— if C3 records a non-viable serving posture, T4 is a **CRITICAL BLOCKER**, not an
out-of-scope item.

The 2.0 s bound stays until Workstream C produces evidence that specifically justifies changing
it. Raising the timeout is not a first move, and turning T4 off is prohibited.
