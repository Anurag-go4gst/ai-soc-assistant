# Plan 7 A3 — implement Option A

Decision implemented: **`P7_SPL_LIFECYCLE_OWNERSHIP` = Option A** — the PhaseContract lifecycle
is honoured independently of merge reachability.

```
ResourcePlan compilation result  +  PhaseContract mandatory lifecycle obligations
                                 ↓
                    final governed schedule / downgrade

A resource-plan downgrade may remove unavailable resource work.
It may not silently remove applicable mandatory lifecycle work.
```

## What changed

`backend/app/planner/phase_schedule_merge.py::merge_schedule` — 1 function, ~20 lines.

Before, the compiler downgrade returned immediately, discarding a resolved PhaseContract unread:

```python
compiled, downgrade = compile_execution_schedule(plan, inputs)
if compiled is None:
    return None, downgrade
```

Now the contract is applied to a possibly-empty compiled base, and the existing
`_apply_phase_contract` → `validate_schedule_order` → `phase_contract.validate_schedule` chain
runs unchanged on the result.

Plus `MergedSchedule.resource_downgrade` (provenance, not authority) and its passthrough in
`planner/executor.py` trace. No other file changed.

## Trigger — structural, no special cases

The lifecycle path is taken when **all** of:

1. `compile_execution_schedule` returned a downgrade, **and**
2. `execution_contract_or_downgrade(plan)` still yields a **valid** contract, **and**
3. `phase_contract.hook_bound_mandatory` is non-empty.

No query ID, no intent, no capability name, no `spl_postprocessor` special-case appears in the
condition or the code.

**Deliberate narrowing found during implementation.** The first version keyed only on (1) and
(3). The existing suite caught it: `test_absent_plan_downgrades_to_the_fixed_schedule`,
`test_unsupported_purpose_downgrades`, `test_side_effecting_step_may_not_declare_a_retry` and
`test_cyclic_plan_is_rejected_not_scheduled` all failed, because that version turned **safety
refusals** into schedules. Condition (2) restores fail-closed behaviour: an invalid or unsafe
plan — dependency cycle, unsupported purpose, side-effecting step declaring a retry, no plan at
all — still refuses. Those tests were **not** edited; the fix was narrowed to satisfy them.

## Required properties

| # | Property | Evidence |
|---|---|---|
| 1 | compiler may still downgrade | `test_compiler_downgrades_when_no_purpose_maps_to_a_hook` — `no_schedulable_step` unchanged; compiler untouched |
| 2 | mandatory lifecycle honoured despite downgrade | `test_mandatory_lifecycle_phase_survives_compiler_downgrade` |
| 3 | schedule validation still runs | unchanged call chain; `phase_contract_unplaceable` / `phase_contract_violation` paths intact and still covered |
| 4 | benign downgrades stay benign | `test_clarification_lane_downgrade_stays_benign`, `test_narration_only_run_with_no_owed_lifecycle_stays_benign`, `test_missing_plan_with_no_owed_lifecycle_still_downgrades` |
| 5 | no duplicate lifecycle phases | `test_successful_merge_is_unchanged_and_gains_no_duplicate_phase`, `test_lifecycle_only_schedule_has_no_duplicate_hooks` |
| 6 | ordering deterministic + PhasePolicy-owned | `test_multiple_mandatory_phases_all_survive_in_registry_order` — registry constraints asserted, sequence pinned, repeat run identical |
| 7 | flag-OFF byte-identical | `executor.py:247` returns before any execution-contract code when `ai_soc_resource_plan_execution_enabled` is false — by construction, not by agreement |

PhasePolicy applicability rules were **not** changed. Required capabilities were **not** widened.
dispatch-v2 was **not** re-enabled. T4 stayed ON at 2.0 s. Live capability enforcement stayed OFF.

## Test coverage

`backend/app/tests/test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py` — **15 passed**
(strict-xfail markers removed because the invariant now holds).

| Coverage | Test |
|---|---|
| affected `workflow_spl` / SPL lifecycle case | `test_mandatory_lifecycle_phase_survives_compiler_downgrade` |
| latent non-SPL phases (`execution`, `reference_finalize`) | `test_invariant_is_not_specific_to_spl_postprocessor` (parametrised) |
| multiple mandatory phases + ordering | `test_multiple_mandatory_phases_all_survive_in_registry_order` |
| inline mandatory phase representation | `test_inline_mandatory_phase_is_represented_not_scheduled` |
| benign clarification-lane downgrade (A1 M2) | `test_clarification_lane_downgrade_stays_benign` |
| benign narration-only downgrade (A1 M3) | `test_narration_only_run_with_no_owed_lifecycle_stays_benign` |
| normal successful merge unchanged | `test_successful_merge_is_unchanged_and_gains_no_duplicate_phase` |
| no duplicate insertion | two tests above |
| safety refusals still fail closed | `test_absent_plan_still_fails_closed_even_when_lifecycle_is_owed`, `test_side_effecting_retry_still_fails_closed_even_when_lifecycle_is_owed`, `test_unsupported_purpose_still_fails_closed_even_when_lifecycle_is_owed` |

## Population after the fix

Re-running the A1 sweep unchanged (`scripts/eval_plan7_a1_population.py --corpus all`):

| | Before A3 | After A3 |
|---|---|---|
| Rows swept | 175 | 175 |
| **Affected** | **5** | **0** |
| Rows merged | 158 | **163** |
| `empty_resource_plan` (benign) | 11 | 11 |
| `no_schedulable_step` (compiler verdict) | 6 | 6 |
| Errors | 0 | 0 |

The compiler verdicts are unchanged — as intended, A3 did not touch resource compilation. What
changed is that five of those downgrades now still produce a governed lifecycle schedule, and the
twelve benign ones still do not.

## Gates

| Gate | Result |
|---|---|
| Targeted pytest (A0/A3 file) | **15 passed** |
| Merge/contract/seam suites | **65 passed** |
| Planner/dispatch/executor/phase/seam slice | **997 passed** |
| A1 population after fix | **0 affected / 175** |
| `/invariant-check` | **7/7 PASS** |
| Flag-OFF | byte-identical by construction (`executor.py:247`) |
| Query-ID special cases | **none** |
| Keyword heuristics | **none** |
| Skill widening | **none** |

## Open observation carried to A4

The lifecycle-only schedule orders `workflow_spl → spl_source_resolve → spl_postprocessor →
execution`, whereas a compiled merge orders `workflow_spl → spl_postprocessor →
spl_source_resolve → execution`. Both satisfy the registry, which deliberately leaves those two
phases mutually unordered (each is only `after=("workflow_spl",)`); the difference comes from
earliest-valid-index insertion over registry order. This is **pre-existing** `_apply_phase_contract`
behaviour that was simply never reachable with an empty base before A3. It is pinned by test and
**flagged for A4** to confirm on the real posture that resolving source slots before deterministic
post-processing is behaviourally correct — it is not silently assumed here.
