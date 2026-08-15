# Plan 7 C0/C1/C2 — T4 serving remediation: options, candidate, viability

Measured 2026-08-15 on the target posture (T4 **ON** @ **2.0 s**, exec ON, v2 OFF). Deliberately
few LLM calls: **6 probes total**, chosen to be decisive rather than exhaustive.

## C0 — what the T4 hop asks for, and what this host can serve

The hop (`chat/semantic_t4_understanding.py::_live_single_hop_provider`) is one
`LocalChatClient` call to `resolve_local_primary_endpoint(sidecar=True)` — the **same** local
primary the rest of the stack uses — with `max_tokens=400`, `temperature=0.1` and the timeout
from `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS`.

Host reality at measurement time:

| | |
|---|---|
| Model | Foundation-Sec-1.1-8B-Instruct **Q8**, `llama-server -c 4000 -t 4 -np 1`, port 8081 |
| RSS | **9.4 GB** of 16 GB (57.6 %) |
| Free RAM | **185 MB** |
| Swap | **4095 / 4095 MB — fully exhausted** |
| Models available locally | **one** (`/opt/models/foundation-sec-q8`, 8.0 GB). No second model, no Qwen, no failover endpoint |
| Decode slots | `-np 1` — a second concurrent slot is not available |

### Options inventoried

| Option | Available in-environment? | What it would take | What it would fix |
|---|---|---|---|
| **A** JSON-schema constrained decoding (`response_format`/`--json-schema`) | **yes, no download** | per-request field on the existing call | output **shape** only |
| **B** Smaller quantisation of the same model (Q4_K_M ≈ 4.7 GB) | no | ~4.7 GB download + operator restart | RSS pressure, likely the cold floor |
| **C** Small dedicated sidecar model (e.g. 1.5 B Q4 ≈ 1 GB) on a second port | no | download **plus** a separate sidecar endpoint setting — `resolve_local_primary_endpoint(sidecar=True)` currently returns the shared local primary, so this is a **config-surface change needing approval** | latency, isolation |
| **D** Raise the 2.0 s bound | forbidden before C3 | — | nothing — see measurements below |
| **E** Free host memory / reduce contention | operator action | stop competing workloads; swap is exhausted | the cold floor |

## C1 — candidate stood up

Only **Option A** could be stood up without a download or a new config surface, so that is the
candidate measured. It was exercised **per request against the existing endpoint** — the
persisted profile, the llama-server unit, and the application code were **not** modified.

## C2 — viability measurement

### Probe 1 — latency floor (cold)

```
prompt 30 tokens → 2 completion tokens → 50.72 s wall  (0.04 tok/s effective)
```

**A two-token reply took 25× the entire 2.0 s budget.** The floor is prompt-processing and
paging, not generation — consistent with 185 MB free RAM and fully exhausted swap.

### Probe 2 — unconstrained contract attempt

```
400 completion tokens → 89.17 s wall (4.49 tok/s)
output: English prose, not JSON — the "Return JSON only" instruction was ignored
```

### Probe 3 — constrained decoding (Option A)

```
80 completion tokens → 19.22 s wall (4.16 tok/s), correct JSON shape, correct field names
(truncated at the token cap, so not parseable — a budget artefact, not a shape failure)
```

Constrained decoding **does** fix the shape problem. It does nothing for latency.

### Probes 4–6 — semantic accuracy on 3 representative residual paraphrases

Constrained decoding, 120 tokens, unbounded time. **A representative subset, not all 8** — the
result was unanimous, so the remaining five were not spent.

| Row | wall | valid JSON | proposed `intent_family` | proposed `answer_goal` | semantic gain |
|---|---|---|---|---|---|
| `p6.para.003` | 27.05 s | ✅ | `knowledge_recall` | `policy_citation` | **none — echoes input** |
| `p6.para.008` | 44.64 s | ✅ | `knowledge_recall` | `policy_citation` | **none — echoes input** |
| `p6.para.012` | 109.31 s | ✅ | `knowledge_recall` | `policy_citation` | **none — echoes input** |

Every response repeats the deterministic contract it was handed. It also invents capability
values (`internet_query`, `text_analysis`, `query_understanding`) that are outside
`ALLOWED_CAPABILITIES` and would be discarded by the governed normalizer — the guard works, but
the proposal carries no usable signal.

These are exactly the rows T4 exists to resolve: hunt/detection asks that should reach an
SPL-capable family. The model proposes no reclassification on any of them.

### C2 metric table

| Metric | Result |
|---|---|
| Accepted structured-contract rate (production path, 2.0 s) | **0 / 17** row-runs |
| Accepted structured-contract rate (constrained decoding, unbounded) | shape valid **3/3**, but semantically empty |
| Semantic accuracy on residual paraphrases | **0 / 3** measured — zero reclassification |
| False widening on ambiguous T4 queries | **0** (governed normalizer rejects invented capabilities) |
| Cold latency | **50.7 s** for 2 tokens |
| Warm latency | 4.1–4.5 tok/s → **19–109 s** per contract |
| p50 / p95 (6 probes) | p50 ≈ **36 s**, p95 ≈ **109 s** |
| Concurrency | not measurable — `-np 1`, single decode slot |
| Slot pressure | inherent: any second caller queues behind a 20–110 s generation |
| Malformed / empty behaviour | prose without constraint; valid shape with constraint; truncation at low token caps |
| Bounded failure behaviour | **correct** — 2.0 s timeout, deterministic fallback, no widening, clarification preserved |
| End-to-end `/chat` impact | at the current floor the hop would add **19–109 s** to a blocking turn if the bound were raised |

## Assessment

Three **independent** failures, not one:

1. **Latency** — 13× to 55× over the 2.0 s bound; the cold floor alone is 25×.
2. **Shape** — fixable in-environment and for free via constrained decoding.
3. **Semantic value** — **zero** on the residual paraphrases. This is the decisive one: even a
   model served instantly and in perfect JSON adds nothing here.

Fixing (1) and (2) would still leave (3) unaddressed. No serving change available in this
environment produces a viable T4 posture, and raising the timeout is not supported by any
measurement — it would buy prose or an echo, at 19–109 s on a blocking turn.

Per the Plan 7 E2 amendment, if C3 records a non-viable posture, **T4 is a CRITICAL BLOCKER for
the Plan 7 production GO** — it must not be downgraded to "not in production scope".
