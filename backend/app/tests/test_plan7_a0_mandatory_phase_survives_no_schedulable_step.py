"""Plan 7 A0/A3 — a compiler downgrade must not erase mandatory lifecycle work.

The invariant, architectural and not example-driven:

    When a PhaseContract declares an applicable mandatory lifecycle phase, that
    phase must remain represented/executable even when the ResourcePlan compiler
    has no schedulable resource step.

A0 wrote these as strict xfails against the defect; A3 (`P7_SPL_LIFECYCLE_OWNERSHIP`
= **Option A**) made them pass by honouring the PhaseContract independently of
merge reachability. No test names a query ID, an intent, or `spl_postprocessor`
specifically — the trigger under test is the structural condition:

    contract declares >= 1 hook-bound mandatory phase
      AND compile_execution_schedule returns any downgrade

Ownership split being pinned: `compile_execution_schedule` owns schedulable
*resource* work; `PhaseContract`/`PhasePolicy` owns mandatory *lifecycle* work. A
resource downgrade may drop unavailable resource work; it may not drop applicable
lifecycle work.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import resolve_and_freeze
from app.planner.phase_policy import PhasePolicyInputs
from app.planner.phase_schedule_merge import merge_schedule
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import StepExecutionSpec
from app.planner.resource_plan_execution_scheduler import (
    ScheduleInputs,
    compile_execution_schedule,
)

INPUTS = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)
POLICY = PhasePolicyInputs(has_workflow_plan=False, pre_spl_discovery_enabled=False)


def _contract(**overrides) -> ResolvedQueryContract:
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


def _narration_only_plan() -> ResourcePlan:
    """A structurally valid plan whose purposes map to no compiler hook.

    This is the A1 mechanism in miniature: the routed skill's capability contract
    vetoes the SPL step at composition, leaving lineage-only work behind.
    `narration` is a real, valid purpose — it contributes lineage, not work.
    """
    return ResourcePlan(steps=[PlanStep(step_id="n1", resource_id="r.n1", purpose="narration")])


def _merge(contract: ResolvedQueryContract, plan: ResourcePlan | None):
    phase_contract = resolve_and_freeze(contract, plan, POLICY)
    merged, reason = merge_schedule(contract, plan, phase_contract, INPUTS)
    return phase_contract, merged, reason


# --- preconditions ------------------------------------------------------------


def test_compiler_downgrades_when_no_purpose_maps_to_a_hook() -> None:
    """The compiler still refuses — A3 did not change resource compilation."""
    compiled, downgrade = compile_execution_schedule(_narration_only_plan(), INPUTS)

    assert compiled is None
    assert downgrade == "no_schedulable_step"


def test_phase_contract_declares_the_lifecycle_phase_mandatory() -> None:
    """The run genuinely owes lifecycle work the plan cannot schedule."""
    phase_contract = resolve_and_freeze(_contract(), _narration_only_plan(), POLICY)

    assert "spl_postprocessor" in phase_contract.hook_bound_mandatory


# --- the invariant ------------------------------------------------------------


def test_mandatory_lifecycle_phase_survives_compiler_downgrade() -> None:
    """THE invariant: owed lifecycle work is never silently dropped."""
    contract = _contract()
    plan = _narration_only_plan()
    phase_contract, merged, reason = _merge(contract, plan)

    assert merged is not None, f"merge refused with {reason!r} despite owed lifecycle"
    assert phase_contract.hook_bound_mandatory <= set(merged.hooks)
    assert "spl_postprocessor" in merged.hooks
    # The schedule is lifecycle-only, and says so.
    assert merged.resource_downgrade == "no_schedulable_step"
    # No plan step binds to a hook — the lifecycle runs, the vetoed resource work
    # does not come back. Waves still describe the (valid but unschedulable) plan.
    assert merged.step_hooks == {}


@pytest.mark.parametrize(
    ("overrides", "expected_phase"),
    [
        ({"required_capabilities": {"mcp"}}, "execution"),
        ({"required_capabilities": {"mcp"}, "answer_goal": "reference_lookup"}, "reference_finalize"),
    ],
)
def test_invariant_is_not_specific_to_spl_postprocessor(overrides, expected_phase) -> None:
    """The same protection covers lifecycle phases that have nothing to do with SPL."""
    contract = _contract(**overrides)
    phase_contract, merged, reason = _merge(contract, _narration_only_plan())

    assert expected_phase in phase_contract.hook_bound_mandatory
    assert merged is not None, f"merge refused with {reason!r}"
    assert expected_phase in merged.hooks


def test_multiple_mandatory_phases_all_survive_in_registry_order() -> None:
    """All owed phases appear, and ordering stays PhasePolicy-owned and deterministic."""
    phase_contract, merged, _ = _merge(_contract(), _narration_only_plan())

    assert merged is not None
    assert set(merged.hooks) == set(phase_contract.hook_bound_mandatory)

    # Ordering is registry-owned, so assert the constraints the registry states
    # rather than a hand-written sequence. `spl_postprocessor` and
    # `spl_source_resolve` are each only `after=("workflow_spl",)` — the registry
    # deliberately leaves them mutually unordered — so their relative order is
    # not asserted here.
    order = {hook: index for index, hook in enumerate(merged.hooks)}
    assert order["workflow_spl"] < order["spl_postprocessor"]
    assert order["workflow_spl"] < order["spl_source_resolve"]
    assert order["spl_postprocessor"] < order["execution"]
    assert order["spl_source_resolve"] < order["execution"]

    # Pinned so the sequence cannot drift silently: earliest-valid-index insertion
    # over registry order yields this exact schedule for a lifecycle-only run.
    assert list(merged.hooks) == [
        "workflow_spl",
        "spl_source_resolve",
        "spl_postprocessor",
        "execution",
    ]

    # Same inputs, same schedule — no incidental ordering.
    _, merged_again, _ = _merge(_contract(), _narration_only_plan())
    assert merged_again is not None
    assert merged_again.hooks == merged.hooks


def test_inline_mandatory_phase_is_represented_not_scheduled() -> None:
    """Inline phases run in `graph_node_context_finalize`, so they are reported, not scheduled."""
    contract = _contract(required_capabilities={"mcp"}, answer_goal="mitre_mapping")
    phase_contract, merged, _ = _merge(contract, _narration_only_plan())

    assert "mitre_finalize" in phase_contract.inline_mandatory
    assert merged is not None
    assert "mitre_finalize" in merged.inline_phases
    assert "mitre_finalize" not in merged.hooks


# --- benign downgrades stay benign -------------------------------------------


def test_clarification_lane_downgrade_stays_benign() -> None:
    """A clarification turn owes no lifecycle — it must not acquire one (A1 mechanism M2)."""
    contract = _contract(ambiguity_state="clarification_required", answer_goal="clarification")
    phase_contract, merged, reason = _merge(contract, _narration_only_plan())

    assert phase_contract.hook_bound_mandatory == frozenset()
    assert merged is None
    assert reason == "no_schedulable_step"


def test_narration_only_run_with_no_owed_lifecycle_stays_benign() -> None:
    """A1 mechanism M3: nothing schedulable *and* nothing owed still downgrades."""
    contract = _contract(
        required_capabilities=set(),
        intent_family="alert_summary",
        answer_goal="severity_assessment",
    )
    phase_contract, merged, reason = _merge(contract, _narration_only_plan())

    assert phase_contract.hook_bound_mandatory == frozenset()
    assert merged is None
    assert reason is not None


def test_missing_plan_with_no_owed_lifecycle_still_downgrades() -> None:
    """The guard is the owed lifecycle, not the presence of a plan."""
    contract = _contract(ambiguity_state="clarification_required", answer_goal="clarification")
    _, merged, reason = _merge(contract, None)

    assert merged is None
    assert reason == "no_resource_plan"


# --- safety refusals still fail closed ----------------------------------------
#
# Honouring the lifecycle must not resurrect a plan the merge rejected for
# safety. These are refusals, not missing resource work.


def test_absent_plan_still_fails_closed_even_when_lifecycle_is_owed() -> None:
    _, merged, reason = _merge(_contract(), None)

    assert merged is None
    assert reason == "no_resource_plan"


def test_side_effecting_retry_still_fails_closed_even_when_lifecycle_is_owed() -> None:
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="m1",
                resource_id="r.m1",
                purpose="mcp_execution",
                execution=StepExecutionSpec(max_attempts=2),
            )
        ]
    )
    phase_contract, merged, reason = _merge(_contract(), plan)

    assert phase_contract.hook_bound_mandatory, "precondition: lifecycle is owed"
    assert merged is None
    assert reason is not None and reason != "no_schedulable_step"


def test_unsupported_purpose_still_fails_closed_even_when_lifecycle_is_owed() -> None:
    plan = ResourcePlan(
        steps=[PlanStep(step_id="x1", resource_id="r.x1", purpose="teach_the_model_to_route")]
    )
    _, merged, reason = _merge(_contract(), plan)

    assert merged is None
    assert reason is not None and reason.startswith("unsupported_purpose")


# --- no duplication, no regression of the healthy path ------------------------


def test_successful_merge_is_unchanged_and_gains_no_duplicate_phase() -> None:
    """A plan that compiles keeps its schedule; the contract adds nothing twice."""
    plan = ResourcePlan(
        steps=[
            PlanStep(step_id="s1", resource_id="r.s1", purpose="spl_artifact"),
            PlanStep(
                step_id="m1",
                resource_id="r.m1",
                purpose="mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            ),
        ]
    )
    phase_contract, merged, _ = _merge(_contract(), plan)

    assert merged is not None
    assert merged.resource_downgrade is None
    assert merged.step_hooks, "a compiled schedule keeps its step bindings"
    assert len(merged.hooks) == len(set(merged.hooks)), f"duplicate hooks in {merged.hooks}"
    assert phase_contract.hook_bound_mandatory <= set(merged.hooks)


def test_lifecycle_only_schedule_has_no_duplicate_hooks() -> None:
    _, merged, _ = _merge(_contract(), _narration_only_plan())

    assert merged is not None
    assert len(merged.hooks) == len(set(merged.hooks))
    assert len(merged.inserted_phases) == len(set(merged.inserted_phases))
