# Plan 7 C3 — `P7_T4_SERVING_POSTURE_V2` decision packet

**STOP. The decision is the user's. No outcome is selected here, and nothing was changed.**

Question: does a **viable** T4 serving posture exist, and may the serving configuration or the
2.0 s bound now change?

Evidence: `docs/evals/plan7/c2_serving_viability.md`, `b1_t4_on_baseline.md`.
Posture unchanged throughout: T4 **ON** @ **2.0 s**, exec ON, v2 OFF, live-cap OFF, `MCP_MODE=mock`.
No timeout was raised, no serving config was modified, T4 was never turned off.

## What was measured

**Production path, 33 row-runs (B1):** T4 invoked on **17/17** T4-tier rows, **0** on T1–T3,
**0 accepted contracts**, **17/17** timeouts at 2000–2005 ms, **0** false widening, clarification
preserved every time.

**Six targeted probes (C2):**

| Probe | Result |
|---|---|
| Cold floor | **2 tokens → 50.72 s** (25× the whole budget) |
| Unconstrained contract | 400 tokens → 89.17 s, **prose not JSON** |
| Constrained decoding | 80 tokens → 19.22 s, **correct JSON shape** |
| 3 residual paraphrases (constrained, unbounded) | 27 / 45 / 109 s, valid JSON, **all three echo the deterministic contract — zero reclassification** |

Host: 8B **Q8** at 9.4 GB RSS, **185 MB free RAM**, **swap 4095/4095 exhausted**, `-np 1`
(no second decode slot), **one** model on disk, no failover endpoint, no Qwen.

## Three independent failures

1. **Latency** — 13×–55× over the bound; the cold floor alone is 25×.
2. **Shape** — the only failure fixable in-environment for free (JSON-schema constrained
   decoding on the existing endpoint).
3. **Semantic value** — **zero** on the residual paraphrases. Decisive: a model served instantly
   and in perfect JSON still adds nothing on the rows T4 exists to resolve.

Fixing 1 and 2 leaves 3 untouched.

## Options actually available

| Option | In-environment? | Cost | Fixes |
|---|---|---|---|
| A — constrained decoding | **yes, free** | per-request field | shape only |
| B — Q4 requantisation of the same model | no | ~4.7 GB download + restart | RSS/cold floor; **not** semantics |
| C — small dedicated sidecar model | no | download **+ a new sidecar endpoint config surface** (needs approval) | latency; semantics unknown |
| D — raise the 2.0 s bound | possible | none | **nothing** — buys prose or an echo at 19–109 s on a blocking turn |
| E — free host memory / reduce contention | operator action | ops work | cold floor only |

## Consequence of a non-viable finding

Per the E2 amendment you recorded: if C3 remains **NON-VIABLE**, **T4 is a CRITICAL BLOCKER for
the Plan 7 production GO**. It must **not** be downgraded to `NOT IN PRODUCTION SCOPE`. In
Plan 7, unlike Plan 6, T4 is part of the intended production architecture.

## Decision required — record one

1. **`T4_SERVING_NON_VIABLE_IN_ENVIRONMENT`** — accept the measurement: no viable posture exists
   here; keep T4 ON at 2.0 s with failures visible; T4 becomes a **CRITICAL BLOCKER** at E2 until
   a serving posture is procured and re-gated.
2. **`ADOPT_CONSTRAINED_DECODING_ONLY`** — adopt Option A because it is free and strictly
   improves shape, while recording that latency and semantic value remain unfixed and T4 stays a
   critical blocker. (Requires approving a change to the T4 call.)
3. **`PROCURE_SERVING_CAPACITY`** — authorise Option B and/or C: a model download and, for C, a
   **new sidecar endpoint config surface**, then re-run C2 before any bound change.
4. **`RAISE_THE_BOUND`** — not supported by any measurement here; recorded only for completeness.

Not changed and not decided by this STOP: dispatch-v2 stays OFF, ResourcePlan execution stays
ON, live capability enforcement stays OFF, repo defaults unchanged, and A7 (the
`session_spl_refine` fallback proof) remains outstanding.
