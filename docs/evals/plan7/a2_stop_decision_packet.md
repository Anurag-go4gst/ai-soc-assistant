# Plan 7 A2 — `P7_SPL_LIFECYCLE_OWNERSHIP` decision packet

**STOP. The decision is the user's. Nothing is implemented and no option is selected here.**

Evidence: `a0_missed_work_analysis.md`, `a1_structural_population.md`,
`runs/target_profile_baseline.md`, failing-first test
`backend/app/tests/test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py`
(**2 passed, 2 xfailed(strict)**).

## Structural population

| | |
|---|---|
| Rows swept | **175** (Plan 6 corpus 20, goldens 105, Cisco 50) |
| Affected — offline, reproducible | **5** (1 plan6, 4 goldens, **0** Cisco) |
| Affected — runtime-confirmed only | **1** (`p6.multi.knowledge_spl_mcp`, trace `4e048382…`) |
| **Measured total** | **6 distinct rows — a lower bound, not a ceiling** |
| Benign downgrades | 11 `empty_resource_plan` (clarification lane, owes nothing) + 1 narration-only `alert_summary` |
| Merge dropped a phase *after* applying the contract | **0** |

Every affected row loses the **same four** hook-backed mandatory phases together:
`workflow_spl`, `spl_postprocessor`, `spl_source_resolve`, **`execution`**.

## Deterministic applicability condition (no query identity)

> A run is affected when its PhaseContract declares ≥ 1 hook-backed mandatory phase **and**
> `compile_execution_schedule` returns any downgrade — because `merge_schedule` discards the
> resolved contract before `_apply_phase_contract` and `validate_schedule` can run.

Dominant upstream trigger: an `spl_generation_only` intent routed to a skill whose capability
contract **vetoes** the `spl_artifact` step at composition, leaving a `narration`-only plan that
maps to no hook.

## Current ownership of `spl_postprocessor`

| Layer | Today |
|---|---|
| `PhaseRegistry` | declares the phase (`phase_registry.py:128`), `hook_name="spl_postprocessor"` |
| `PhasePolicy` | marks it **mandatory** whenever `spl_required` (`phase_policy.py:143`) — from `required_capabilities` / `candidate_spl`, **not** from a plan step |
| ResourcePlan compiler | **explicitly excludes it** from `SCHEDULABLE_HOOKS` (`resource_plan_execution_scheduler.py:40`) — "driven by their own stage predicates, not by plan steps" |
| Merge seam | its **only** re-inserter (`phase_schedule_merge` docstring, `_apply_phase_contract`) |
| dispatch-v2 | supplied it via the projected schedule (`pipeline_dispatch_builder.py:38,286`) — **off in the target architecture** |
| Predicate fallback | never adds it (`_legacy_predicate_dispatch_schedule`) |

So it is owned by the **PhaseContract in declaration** and by the **merge in execution**, with
v2 as the de-facto safety net that Plan 7 exists to remove.

## Why `no_schedulable_step` prevents it today

```python
compiled, downgrade = compile_execution_schedule(plan, inputs)
if compiled is None:
    return None, downgrade          # phase_schedule_merge.py:204-206
```

`_apply_phase_contract`, `validate_schedule_order` and `phase_contract.validate_schedule` — the
fail-closed check for a missing mandatory phase — all live **after** this line. The contract is
resolved, then discarded unread. The caller keeps the fixed deterministic schedule, which with
v2 OFF is `workflow_spl → spl_source_resolve → execution`: SPL is produced, and the mandatory
post-processing that makes it safe to consume is not.

## The five options

### A. PhaseContract lifecycle honoured independently of merge reachability

| | |
|---|---|
| **Ownership** | PhaseContract becomes authoritative for mandatory phases regardless of whether the compiler produced anything; the merge applies the contract before deciding it has nothing to do |
| **Applicability condition** | contract declares hook-backed mandatory phases ∧ compiler downgraded |
| **Blast radius** | one function (`merge_schedule`) — reorder so `_apply_phase_contract` runs on a possibly-empty compiled base, then validate; downgrade only if the contract itself is unplaceable |
| **Structural population covered** | all 6 measured, and any future downgrade reason (`empty_resource_plan`, `plan_parse_failed`, …) — the fix is phase-agnostic and reason-agnostic |
| **Other lifecycle phases** | fixes `mitre_finalize` / `cve_adapter` / `reference_finalize` losses by the same early return, which are latent today (0 measured) |
| **Flag-OFF compatibility** | exec OFF runs zero merge-seam code — untouched |
| **Duplicate-execution risk** | low but real: a contract-only schedule could re-run a hook the fallback would also run. Must be mutually exclusive — if the merge returns a schedule, the fallback must not also build one |
| **Fallback / seam interaction** | reduces reliance on `_run_legacy_dispatch_fallback`; does not adopt or retire any seam |
| **Tests required** | remove both strict-xfails; contract-only schedule ordering; validator still fails closed on unplaceable; flag-OFF byte-identical; no duplicate hook execution; the 6 measured rows |

### B. Compiler emits contract-only schedules

| | |
|---|---|
| **Ownership** | the compiler; it learns to emit lifecycle hooks with no backing plan step |
| **Applicability condition** | same, but evaluated inside `compile_execution_schedule` |
| **Blast radius** | larger — `SCHEDULABLE_HOOKS` was *deliberately* narrowed to plan-step-backed hooks; widening it re-couples the compiler to lifecycle concerns that Plan 5 C1 split out |
| **Population covered** | same 6 |
| **Other phases** | would have to special-case which non-step hooks the compiler may emit — reintroducing the coupling the merge exists to avoid |
| **Flag-OFF** | unaffected |
| **Duplicate risk** | higher — two layers (compiler and merge) could both insert the same phase |
| **Seams** | none |
| **Tests** | compiler emission rules; merge idempotence when the phase is already present; Plan 3 A0 stage-drop probe must stay at 0/5 |

### C. `spl_postprocessor` becomes a ResourcePlan step

| | |
|---|---|
| **Ownership** | the planner; validation becomes a planned resource step with a purpose |
| **Applicability condition** | plan composition would have to add it whenever SPL is planned — but the affected rows are exactly those where the **skill contract vetoed the SPL step**, so composition would have to add a validation step for an artifact the plan does not produce |
| **Blast radius** | large — new purpose in `_PURPOSE_HOOKS`, composer changes, resource-registry entry, specialist reports, fingerprint churn on **every** SPL row (all `resource_plan_fingerprint` values change) |
| **Population covered** | **does not cover the measured rows** — a vetoed plan stays vetoed |
| **Other phases** | would invite the same treatment for `reference_finalize`, dissolving the lifecycle/plan distinction |
| **Flag-OFF** | fingerprints change even flag-OFF, so Plan 6's parity/no-drift baselines move |
| **Duplicate risk** | moderate |
| **Seams** | none |
| **Tests** | broad re-baselining |

### D. Execution-seam responsibility

| | |
|---|---|
| **Ownership** | `execute_plan_dispatch` — after choosing a schedule, it reconciles it against the PhaseContract and appends missing mandatory phases |
| **Applicability condition** | any final schedule missing a contracted mandatory phase, whatever produced it |
| **Blast radius** | moderate — one reconcile point, but it also covers the **fallback** and predicate schedules, not just the merge |
| **Population covered** | all 6, **plus** paths where the merge never runs at all (`rag_only`, guided hybrid, session-SPL-refine) — the widest coverage of the five |
| **Other phases** | covers every mandatory phase uniformly |
| **Flag-OFF** | **risk**: the seam runs with execution OFF too, so a naive reconcile changes flag-OFF behaviour. Would have to be gated on the execution flag to preserve Plan 6's byte-identical flag-OFF guarantee |
| **Duplicate risk** | highest — appending to a schedule another layer already built is exactly how a hook gets run twice |
| **Seams** | touches the seam whose adoption C3 deliberately left at **0**; risks pre-empting `P7_DISPATCH_V2_RETIREMENT` (A6) |
| **Tests** | reconcile idempotence, no duplicate execution across all 10 inventoried paths, flag-OFF parity, seam-coverage pins |

### E. Explicit migration of legacy/v2-only behaviour

| | |
|---|---|
| **Ownership** | recognises the truth that `spl_postprocessor` scheduling is **v2-only behaviour** that was never migrated, and migrates it deliberately into the target architecture |
| **Applicability condition** | derived from what v2's `pipeline_dispatch_builder` emits, ported to the PhaseContract path |
| **Blast radius** | conceptually the cleanest framing, but as a *mechanism* it must still land in A, B, C or D — it is a migration mandate, not a distinct implementation site |
| **Population covered** | depends on the mechanism chosen |
| **Other phases** | forces an audit of every other v2-only stage before v2 is retired (A6) — valuable in its own right |
| **Flag-OFF** | depends |
| **Duplicate risk** | depends |
| **Seams** | it is the natural companion to `P7_DISPATCH_V2_RETIREMENT` |
| **Tests** | a v2-vs-target stage-coverage diff, asserting no stage exists only in v2 |

## Recommendation

**Option A, with Option E as its framing** — and A6 keeps the v2-stage audit that E demands.

Why A:

- It fixes the mechanism **where the mechanism is**. The bug is one early return that discards a
  resolved contract; every other option compensates for it somewhere else.
- It is phase-agnostic and downgrade-reason-agnostic, so it also closes the latent
  `mitre_finalize` / `cve_adapter` / `reference_finalize` variants that today measure 0 only
  because no corpus row hits them.
- Smallest blast radius of the options that actually cover the measured population: one
  function, no new purposes, no fingerprint churn, no seam adoption, no flag-OFF change.
- It preserves the Plan 5 C1 separation — the compiler stays plan-driven, the contract stays
  lifecycle-driven, and the merge remains the single place they meet.
- The fail-closed path already exists: if the contract cannot be placed the merge returns
  `phase_contract_unplaceable`, so a genuinely impossible lifecycle still refuses rather than
  silently repairing.

Why E as framing: calling this a **migration** (not a patch) is what forces the A6 question —
*which other stages exist only in dispatch-v2?* — to be answered before v2 is retired.

Rejections:

- **B** — re-couples the compiler to lifecycle scheduling, which is precisely the split Plan 5 C1
  made and Plan 3 A0 measured the cost of; and it creates a second inserter.
- **C** — does not fix the measured rows (a vetoed plan stays vetoed), while churning every SPL
  fingerprint and moving Plan 6's baselines.
- **D** — widest coverage and genuinely attractive for the bypass paths, but it is the highest
  duplicate-execution risk, changes flag-OFF behaviour unless carefully gated, and reaches into
  the seam that C3 deliberately left unadopted. If the bypass paths turn out to need it, that is
  an A5/A6 decision with its own evidence — not a side effect of this fix.

Explicitly **not** proposed: widening `knowledge_recall` so the SPL step is not vetoed. The
routing disagreement (an `spl_generation_only` intent routed to a knowledge skill) is a real
question, but the locked decisions forbid widening a skill contract to satisfy it, and A2 is
about lifecycle ownership, not routing.

## Decision required

Choose one: **A** / **B** / **C** / **D** / **E** (or A-with-E framing as recommended).

Not implemented: A3 is blocked until this is recorded. T4 stays ON, dispatch-v2 stays OFF, the
T4 timeout stays 2.0 s, and no query-ID or keyword fix is on the table.
