# Plan 7 A0 — why mandatory lifecycle work disappears

Mechanism, not symptom. The two Plan 6 rows are used as *reproductions*; nothing in the
analysis or the tests depends on their identity.

Posture: exec **ON**, dispatch-v2 **OFF**, T4 **ON** @ 2.0 s, live capability enforcement
**OFF** (P0.3 read-back verified). Code unchanged.

## 1. Runtime reproduction

Both rows reproduce on the target posture (P0.4, run `20260814T125340Z`), captured from
`/debug` bundles:

| | `p6.multi.knowledge_spl_mcp` | `p6.live_posture.d1_003` | `p6.spl.draft` (control) |
|---|---|---|---|
| trace | `4e048382…` | `098bc233…` | `0c0fefea…` |
| route | `spl_generation` | `spl_generation` | `attack_discovery` |
| `intent_family` | `spl_generation_only` | `spl_generation_only` | `spl_generation_only` |
| `answer_goal` | `spl_artifact` | `spl_artifact` | `spl_artifact` |
| `required_capabilities` | `['spl']` | `['spl']` | `['spl']` |
| tier | T2 | T1 | T2 |
| `degrade_reason` | **`no_schedulable_step`** | **`no_schedulable_step`** | `merge` |
| `phase_names` (PhaseContract applied) | **`[]`** | **`[]`** | `workflow_spl, spl_postprocessor, spl_source_resolve, execution` |
| executed `dispatch_schedule` | `workflow_spl, spl_source_resolve, execution` | `workflow_spl, spl_source_resolve, execution` | `workflow_spl, **spl_postprocessor**, spl_source_resolve, execution` |
| wall | 3,268 ms | 1,469 ms | 58,469 ms |

**The control row is the proof this is structural, not query-specific.** `p6.spl.draft` carries
an *identical resolved-query contract shape* — same intent family, answer goal, required
capabilities — and still merges correctly. What differs is the **ResourcePlan**: the failing
rows' plans expose no purpose the compiler can turn into a hook. The query text is irrelevant to
the mechanism.

Both failing rows still run `workflow_spl` (SPL is produced) but **not** `spl_postprocessor` —
so a candidate SPL exists that never passed the deterministic post-processing the contract
declares mandatory. They are also the two fastest rows in the corpus, precisely because they
skip owed work.

## 2. The mechanism, in code

**(a) The compiler downgrades.** `resource_plan_execution_scheduler.compile_execution_schedule`
derives live purposes from the plan; `_compile_hooks` returns `[]` when none of
`knowledge_retrieval` / `spl_artifact` / `mcp_execution` is live and SPL is not blocked:

```python
hooks = _compile_hooks(...)
if not hooks:
    return None, "no_schedulable_step"
```

**(b) The merge returns before the lifecycle is applied.** `phase_schedule_merge.merge_schedule`
lines 204-206:

```python
compiled, downgrade = compile_execution_schedule(plan, inputs)
if compiled is None:
    return None, downgrade          # <-- _apply_phase_contract never runs
```

Everything that honours the PhaseContract — `_apply_phase_contract`, `validate_schedule_order`,
`phase_contract.validate_schedule` (which fails closed on a missing mandatory phase) — lives
*after* this line. On this branch the contract is resolved and then discarded unread.

**(c) `spl_postprocessor` has no other owner.** It is deliberately excluded from
`SCHEDULABLE_HOOKS` (`resource_plan_execution_scheduler.py:40`: "`spl_postprocessor` and
`reference_finalize` are driven by their own stage predicates, not by plan steps"), and
`phase_schedule_merge`'s own docstring names re-inserting exactly those phases as the merge's
first job. So the merge is its **only** re-inserter on this runtime.

**(d) The contract genuinely owes it.** `phase_policy.py:143` marks it mandatory whenever
`spl_required`:

```python
if spl_required:
    mark("workflow_spl", "spl artifact required")
    mark("spl_postprocessor", "spl candidate must be deterministically validated")
    mark("spl_source_resolve", "spl candidate carries source slots")
```

and `spl_required` is satisfied by `"spl" in required_capabilities` or `candidate_spl` evidence —
**it does not require a schedulable `spl_artifact` plan step**. That divergence between "what the
run owes" and "what the plan can schedule" is the defect's whole surface.

**(e) dispatch-v2 used to cover it.** With v2 ON, `_legacy_predicate_dispatch_schedule` copies
the v2 projected schedule, which includes `PipelineStage.spl_postprocessor`
(`pipeline_dispatch_builder.py:38,286`). With v2 OFF there is no projected schedule to copy, and
the predicate fallback builds `workflow_spl → rag_early? → spl_source_resolve → execution` — no
`spl_postprocessor`. **That is exactly the schedule both failing rows executed.**

So: contract owes it → compiler cannot schedule it → merge discards the contract → fallback does
not add it → v2 is off. No owner remains. Plan 6's C0 `KEEP OFF` was the correct call on this
evidence.

## 3. Failing-first test

`backend/app/tests/test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py`

The invariant asserted:

> When a PhaseContract declares an applicable mandatory lifecycle phase, that phase must remain
> represented/executable even when the ResourcePlan compiler has no schedulable resource step.

Four tests, none naming a query ID:

| Test | State | What it establishes |
|---|---|---|
| `test_compiler_downgrades_when_no_purpose_maps_to_a_hook` | **passes** | precondition — the shape really produces `no_schedulable_step` |
| `test_phase_contract_declares_the_lifecycle_phase_mandatory` | **passes** | precondition — the run really owes `spl_postprocessor` |
| `test_mandatory_lifecycle_phase_survives_compiler_downgrade` | **xfail(strict)** | THE invariant — currently violated |
| `test_defect_is_not_specific_to_spl_postprocessor` | **xfail(strict)** | the early return is phase-agnostic |

Observed: `2 passed, 2 xfailed`. `strict=True` means an accidental pass becomes a failure, so the
A3 fix must remove the markers deliberately.

The invariant test accepts **either** correct outcome — a schedule that still represents the owed
phase, **or** a fail-closed refusal naming the unmet obligation. What it rejects is today's
behaviour: a bare compiler downgrade that leaves owed work with no owner. That deliberately does
not prejudge the A2 ownership decision.

## 4. What A0 does *not* conclude

- It does **not** choose an owner for `spl_postprocessor` — that is the A2 STOP.
- It does **not** claim only two rows are affected — that is A1's job. A0 already shows the
  early return is phase-agnostic, so the population may include other lifecycle phases.
- It does **not** propose re-enabling dispatch-v2. v2 covering the gap is the status quo Plan 7
  exists to retire.
