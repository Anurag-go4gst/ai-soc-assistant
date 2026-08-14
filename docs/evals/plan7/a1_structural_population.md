# Plan 7 A1 — structural population of lost mandatory lifecycle work

Method: `scripts/eval_plan7_a1_population.py`. For every corpus query it builds the same
`ResolvedQueryContract`, routes deterministically, composes the `ResourcePlan` with the routed
skill's contract, resolves the `PhaseContract`, then runs the **real** compiler and the **real**
merge. No LLM call, no MCP call, no HTTP turn. Posture modelled: dispatch-v2 **OFF**
(`pre_spl_discovery_enabled=False`) — the posture under audit.

JSON: `docs/evals/plan7/a1_structural_population.json`.

Counted condition — all four must hold:

1. the PhaseContract declares an applicable **mandatory** lifecycle phase with a hook,
2. the compiler returns a downgrade,
3. the merge therefore never applies the PhaseContract,
4. with dispatch-v2 OFF, nothing else owns that work.

## Population

| Corpus | Rows swept | Affected |
|---|---|---|
| Plan 6 VPS corpus | 20 | **1** |
| 105 goldens | 105 | **4** |
| Cisco power-grid 50 | 50 | **0** |
| **Total** | **175** | **5** |

Compiler verdicts across all 175 rows: **158** compiled and merged cleanly, **11**
`empty_resource_plan`, **6** `no_schedulable_step`.

## Classification by mechanism

### M1 — skill-contract veto empties the plan (**5 rows — the defect**)

| Row | Corpus | Routed skill | Intent family | Plan purposes | Mandatory phases lost |
|---|---|---|---|---|---|
| `p6.live_posture.d1_003` | plan6 | `knowledge_recall` | `spl_generation_only` | `narration` | `workflow_spl`, `spl_postprocessor`, `spl_source_resolve`, `execution` |
| `q0.q055` | golden 105 | `knowledge_recall` | `spl_generation_only` | `narration` | same four |
| `q0.q094` | golden 105 | `knowledge_recall` | `spl_generation_only` | `narration` | same four |
| `q0.q095` | golden 105 | `knowledge_recall` | `spl_generation_only` | `narration` | same four |
| `q0.q103` | golden 105 | `knowledge_recall` | `spl_generation_only` | `narration` | same four |

One mechanism, not five cases. The contract owes SPL (`intent_family=spl_generation_only`,
`required_capabilities=['spl']`), but the routed skill's capability contract **vetoes the
`spl_artifact` step during composition** (`composer.py`, `_skill_permits`). The surviving plan
carries only `narration`, which maps to no hook, so `_compile_hooks` returns `[]` →
`no_schedulable_step` → `merge_schedule` returns at line 205 → `_apply_phase_contract` and
`phase_contract.validate_schedule` (which fails closed on a missing mandatory phase) never run.

**The loss is not limited to `spl_postprocessor`.** All four hook-backed mandatory phases go
together, including **`execution`** — the phase that owns the MCP gate, HIL and RBAC. On these
rows the contract's guarantee about that phase is discarded, not merely one validation step.
(The predicate fallback still runs an `execution` hook, so the gate itself is not bypassed; what
is lost is the contract's authority over it.)

### M2 — no lifecycle owed (**11 rows — benign, not the defect**)

`empty_resource_plan` on clarification-lane turns: `p6.clarify`, `p6.unsafe`, the 8 residual T4
paraphrases, and `q0.q045`. `phase_policy` returns an empty resolution for
`clarification_required` / `policy_blocked`, so the run owes **no** lifecycle and nothing can be
lost. Correct behaviour.

### M3 — narration-only plan with no mandatory lifecycle (**1 row — benign**)

`p6.alert.summary`: `no_schedulable_step` with `mandatory=[]`. `alert_summary` is an
evidence-summary/no-SPL family, so the compiler having nothing to schedule is the right answer.

### No fourth mechanism observed

**0 rows** where the merge produced a schedule that dropped a mandatory phase — when
`_apply_phase_contract` runs it does its job. The defect is exclusively the early return.
**0 rows** where an inline-only mandatory phase (`mitre_finalize`, `cve_adapter`) was owed on a
downgraded turn, so inline phases are untouched by this specific mechanism — but they are lost
by the *same* early return whenever a future contract owes them alongside a downgrade, since the
return is phase-agnostic (pinned by
`test_plan7_a0_mandatory_phase_survives_no_schedulable_step.py::test_defect_is_not_specific_to_spl_postprocessor`).

## Limitations — stated, not smoothed over

1. **The sweep routes deterministically; the runtime routes through the full adjudication
   chain.** On `p6.multi.knowledge_spl_mcp` the sweep routes `knowledge_recall` and composes
   `mcp_execution + narration`, which *does* compile — yet the runtime (P0.4, trace
   `4e048382…`) routed `spl_generation` and downgraded to `no_schedulable_step`, losing
   `spl_postprocessor`. So that row is a **runtime-confirmed** member of the same population
   whose exact composition the offline sweep does not reproduce. **Measured population is
   therefore 5 offline + 1 runtime-only = 6 distinct rows**, and the offline figure is a
   **lower bound**, not a ceiling.
2. The sweep models `blocked_step_ids=∅` and `has_workflow_plan=False`. A runtime turn with
   blocked steps can reach the same downgrade from a different starting plan.
3. Composition is authority-gated; the sweep enters `resource_plan_authority()` explicitly to
   use the same composer the runtime uses. It commits nothing and mutates no state.
4. Cisco 50 shows **0** affected rows — those questions route to SPL-capable skills, so no veto
   empties the plan. This is evidence about that corpus, not proof the mechanism is rare.

## What this means for A2

The deterministic applicability condition is now precise and **contains no query identity**:

> A run is affected when its PhaseContract declares ≥1 hook-backed mandatory phase **and**
> `compile_execution_schedule` returns any downgrade — because `merge_schedule` discards the
> contract before applying it.

The dominant upstream trigger is a **routed skill whose capability contract vetoes the very step
the contract's required capabilities demand** — an `spl_generation_only` intent routed to
`knowledge_recall`. Whether that routing disagreement is itself a defect is a separate question;
it must not be "fixed" by widening `knowledge_recall`, which the plan's locked decisions forbid.
A2 decides ownership of the lifecycle phase, not the routing.
