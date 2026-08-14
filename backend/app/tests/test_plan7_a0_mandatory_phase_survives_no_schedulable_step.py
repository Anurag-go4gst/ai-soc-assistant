"""Plan 7 A0 — failing-first structural test.

The invariant under test is architectural, not example-driven:

    When a PhaseContract declares an applicable mandatory lifecycle phase, that
    phase must remain represented/executable even when the ResourcePlan compiler
    has no schedulable resource step.

Measured on the VPS in Plan 6 (Arm C: exec ON, dispatch-v2 OFF):
``p6.multi.knowledge_spl_mcp`` and ``p6.live_posture.d1_003`` compile to
``no_schedulable_step`` and therefore lose ``spl_postprocessor`` — work that
dispatch-v2's projected schedule supplies today. These tests must never name
those rows: the defect is the early return in ``merge_schedule``, and the fix
has to hold for every structurally equivalent case.

Mechanism (`phase_schedule_merge.merge_schedule`):

    compiled, downgrade = compile_execution_schedule(plan, inputs)
    if compiled is None:
        return None, downgrade          # <-- returns BEFORE _apply_phase_contract

``spl_postprocessor`` is deliberately excluded from ``SCHEDULABLE_HOOKS``
(`resource_plan_execution_scheduler`), so the merge is its only re-inserter. With
dispatch-v2 OFF and the compiler downgraded, no owner remains.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import resolve_and_freeze
from app.planner.phase_policy import PhasePolicyInputs
from app.planner.phase_schedule_merge import merge_schedule
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution_scheduler import (
    ScheduleInputs,
    compile_execution_schedule,
)

INPUTS = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)
POLICY = PhasePolicyInputs(has_workflow_plan=False, pre_spl_discovery_enabled=False)


def _contract(**overrides) -> ResolvedQueryContract:
    """A contract that owes SPL lifecycle work via `required_capabilities`.

    `phase_policy` marks `spl_postprocessor` mandatory when `spl` is required —
    it does not require the plan to carry a schedulable `spl_artifact` step.
    That divergence is the whole point of this test.
    """
    payload = {
        "normalized_goal": "goal",
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "ambiguity_state": "unambiguous",
        "qualification_tier": "T2",
        "qualification_source": "deterministic_qualification",
        "required_capabilities": {"spl"},
    }
    payload.update(overrides)
    return ResolvedQueryContract(**payload)


def _plan_without_schedulable_steps() -> ResourcePlan:
    """A structurally valid plan whose purposes map to no compiler hook.

    `narration` contributes lineage, not work — a real and valid plan shape per
    `_PURPOSE_HOOKS`. It is used here only to construct the downgrade; nothing in
    the assertions depends on this particular purpose.
    """
    return ResourcePlan(steps=[PlanStep(step_id="n1", resource_id="r.n1", purpose="narration")])


def test_compiler_downgrades_when_no_purpose_maps_to_a_hook() -> None:
    """Precondition: this shape really does produce `no_schedulable_step`."""
    compiled, downgrade = compile_execution_schedule(_plan_without_schedulable_steps(), INPUTS)

    assert compiled is None
    assert downgrade == "no_schedulable_step"


def test_phase_contract_declares_the_lifecycle_phase_mandatory() -> None:
    """Precondition: the run genuinely owes `spl_postprocessor`."""
    phase_contract = resolve_and_freeze(
        _contract(), _plan_without_schedulable_steps(), POLICY
    )

    owed = {phase.name for phase in phase_contract.phases if phase.mandatory}
    assert "spl_postprocessor" in owed


@pytest.mark.xfail(
    reason=(
        "Plan 7 A0 defect: merge_schedule returns on the compiler downgrade before "
        "_apply_phase_contract runs, so a contracted mandatory lifecycle phase has no "
        "owner once dispatch-v2 is OFF. Remove this marker with the A3 fix."
    ),
    strict=True,
)
def test_mandatory_lifecycle_phase_survives_compiler_downgrade() -> None:
    """THE invariant: a mandatory contracted phase is never silently dropped.

    Either the merge produces a schedule that still represents the owed phase, or
    it must fail closed with a reason that names the unmet lifecycle obligation —
    what it must not do is return a bare compiler downgrade that leaves the work
    with no owner.
    """
    contract = _contract()
    plan = _plan_without_schedulable_steps()
    phase_contract = resolve_and_freeze(contract, plan, POLICY)
    owed_mandatory = {phase.name for phase in phase_contract.phases if phase.mandatory}

    merged, reason = merge_schedule(contract, plan, phase_contract, INPUTS)

    if merged is not None:
        assert owed_mandatory <= set(merged.hooks) | set(merged.inline_phases), (
            f"merged schedule {merged.hooks} drops mandatory phases "
            f"{sorted(owed_mandatory - (set(merged.hooks) | set(merged.inline_phases)))}"
        )
        return

    assert reason not in {"no_schedulable_step", None}, (
        "merge refused with a bare compiler downgrade; a run owing "
        f"{sorted(owed_mandatory)} must not be reported as merely having nothing to schedule"
    )


@pytest.mark.xfail(
    reason=(
        "Plan 7 A0 defect: the early return is phase-agnostic, so every mandatory "
        "lifecycle phase — not only spl_postprocessor — is lost on this branch. "
        "Remove this marker with the A3 fix."
    ),
    strict=True,
)
def test_defect_is_not_specific_to_spl_postprocessor() -> None:
    """The early return drops whatever the contract owed, whatever that is."""
    contract = _contract(answer_goal="mitre_mapping", required_capabilities={"knowledge"})
    plan = _plan_without_schedulable_steps()
    phase_contract = resolve_and_freeze(contract, plan, POLICY)
    owed_mandatory = {phase.name for phase in phase_contract.phases if phase.mandatory}

    if not owed_mandatory:
        pytest.skip("no mandatory lifecycle owed for this contract shape")

    merged, reason = merge_schedule(contract, plan, phase_contract, INPUTS)

    assert merged is not None or reason not in {"no_schedulable_step", None}, (
        f"run owing {sorted(owed_mandatory)} was dropped via the compiler downgrade"
    )
