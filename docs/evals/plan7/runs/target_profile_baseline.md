# Plan 7 P0.4 — target-profile baseline (unchanged code)

Posture (P0.3, verified by read-back): LangGraph **ON**, ResourcePlan execution **ON**,
dispatch-v2 **OFF**, T4 **ON** @ **2.0 s**, live capability enforcement **OFF**, `MCP_MODE=mock`.
**No code was modified for this run.** This is the "before" for every later Plan 7 claim.

Runs: `docs/evals/plan6/runs/20260814T125340Z/` (arm F, 12 rows) and
`docs/evals/plan6/runs/20260814T130605Z/` (arm D, 9 rows — the 8 T4 paraphrases plus
`p6.t4.out_of_registry`, which carries both arms). **21 row-runs, 20 distinct rows.** Harness
exit 0 on both; `missing_qualification_tier` **none**.

`degrade_reason` here is the schedule-authority label, not a failure: `merge` = the Plan 5 merge
seam produced the schedule; `no_schedulable_step` = the compiler downgraded and the run fell
back to the fixed deterministic schedule.

## Arm F — 12 rows

| row_id | route | tier | fingerprint | degrade_reason | phase_names | inline | T4 | ms |
|---|---|---|---|---|---|---|---|---|
| `p6.t1.knowledge` | `knowledge_recall` | T2 | `54643926bb` | — | `[]` | `[]` | not invoked | 55,526 |
| `p6.t2.known_nontrivial` | `knowledge_recall` | T2 | `54643926bb` | — | `[]` | `[]` | not invoked | 60,700 |
| `p6.t4.out_of_registry` | `guided_investigation` | T4 | `fd65002b17` | **merge** | `prepare_rag_only, rag_early` | `[]` | invoked, **timed_out 2001 ms** | 66,296 |
| `p6.spl.draft` | `attack_discovery` | T2 | `99ccd9213e` | **merge** | `workflow_spl, spl_postprocessor, spl_source_resolve, execution` | `[]` | not invoked | 58,469 |
| `p6.spl.mcp` | `attack_discovery` | T2 | `3a8fae8d68` | **merge** | `workflow_spl, spl_postprocessor, spl_source_resolve, mitre_finalize, execution` | `[]` | not invoked | 235,940 |
| **`p6.multi.knowledge_spl_mcp`** | `spl_generation` | T2 | `16d973d375` | **`no_schedulable_step`** | **`[]`** | `[]` | not invoked | 3,268 |
| `p6.clarify` | `knowledge_recall` | T4 | — | — | `[]` | `[]` | invoked, **timed_out 2003 ms** | 44,167 |
| `p6.unsafe` | `knowledge_recall` | T4 | — | — | `[]` | `[]` | invoked, **timed_out 2001 ms** | 41,773 |
| `p6.alert.summary` | `knowledge_recall` | T2 | `59ad8ff336` | — | `[]` | `[]` | not invoked | 123,580 |
| **`p6.live_posture.d1_003`** | `spl_generation` | T1 | `59ad8ff336` | **`no_schedulable_step`** | **`[]`** | `[]` | not invoked | 1,469 |
| `p6.repeat.refinement` | `spl_generation` | T4 | `1bc3fa1464` | **merge** | `workflow_spl, spl_postprocessor, spl_source_resolve, execution` | `[]` | invoked, **timed_out 2001 ms** | 43,041 |
| `p6.fail.degraded` | `attack_discovery` | T2 | `1bc3fa1464` | **merge** | `workflow_spl, spl_postprocessor, spl_source_resolve, execution` | `[]` | not invoked | 2,467 |

**Merge executed on 6/12.** `no_schedulable_step` on **exactly 2/12** — the two rows Plan 6
identified, reproduced on the target posture. The remaining 4 are `rag_only`-shaped turns that
never reach the seam.

## Arm D — 9 rows (8 residual paraphrases + the shared T4 row)

Every paraphrase: route `knowledge_recall`, tier **T4**, no fingerprint, no merge, T4 **invoked
and timed out at ~2000 ms**, `accepted=false`, `rejected_reasons=['timed_out']`,
`notes=['llm_assist_timed_out']`.

| row_id | route | tier | T4 invoked | accepted | elapsed | ms |
|---|---|---|---|---|---|---|
| `p6.para.003` | `knowledge_recall` | T4 | yes | **no** | 2,002 ms | 42,264 |
| `p6.para.004` | `knowledge_recall` | T4 | yes | **no** | 2,002 ms | 93,794 |
| `p6.para.005` | `knowledge_recall` | T4 | yes | **no** | 2,001 ms | 93,991 |
| `p6.para.006` | `knowledge_recall` | T4 | yes | **no** | 2,000 ms | 93,829 |
| `p6.para.007` | `knowledge_recall` | T4 | yes | **no** | 2,000 ms | 94,355 |
| `p6.para.008` | `knowledge_recall` | T4 | yes | **no** | 2,000 ms | 94,087 |
| `p6.para.012` | `knowledge_recall` | T4 | yes | **no** | 2,000 ms | 94,309 |
| `p6.para.015` | `knowledge_recall` | T4 | yes | **no** | 2,000 ms | 93,876 |
| `p6.t4.out_of_registry` | `guided_investigation` | T4 | yes | **no** | 2,001 ms | 56,529 |

## T4 instrumentation summary (B0 fields, recorded not hidden)

| Field | Result |
|---|---|
| Invoked on T4 rows | **12/12** T4-tier row-runs |
| Invoked on T1–T3 rows | **0** — `semantic_t4` is `null` on every T1/T2 row (qualification correct) |
| Accepted contracts | **0** |
| Timeouts | **12/12**, all at 2000–2003 ms against the 2.0 s bound |
| Malformed / empty output | 0 observed — the bound is hit before any parse |
| Slot-busy | 0 observed |
| Clarification preserved | yes — `p6.clarify` still clarifies after T4 fails |
| False capability widening | **0** — no T4 failure widened a route or capability |
| Route after failure | deterministic fallback, unchanged from Plan 6 Arm A |

**T4 is ON and failing visibly.** That is the intended diagnostic state for this phase; it is
not sufficient for production activation, and it must not be "fixed" by turning T4 off.

## Latency

Arm F p50 ≈ **55.5 s**, materially below Plan 6's exec-OFF/v2-ON p50 of 92.9 s. The likely
cause is dispatch-v2 being OFF (no bounded pre-SPL MCP discovery), not a Plan 7 improvement —
**not** claimed as one. The two `no_schedulable_step` rows are the fastest in the corpus
(3.3 s, 1.5 s) precisely because they skip the SPL lifecycle work they owe.

## Carried into A0

`p6.multi.knowledge_spl_mcp` and `p6.live_posture.d1_003` reproduce the Plan 6 defect exactly on
the target posture: contract owes SPL, compiler downgrades, no PhaseContract is applied, and the
executed schedule omits `spl_postprocessor`.
