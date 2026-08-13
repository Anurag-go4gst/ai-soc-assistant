"""Plan 5 C4 — bounded refinement over the merged schedule.

No second refinement mechanism is introduced: these exercise the existing
`refinement_decision` seam and the existing guided round cap against a plan that
went through the C1 merge.
"""

from __future__ import annotations

from pathlib import Path

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.guided_hybrid_refinement import (
    MAX_GUIDED_INVESTIGATION_ROUNDS,
    should_run_refinement_pass,
)
from app.planner.phase_contract import resolve_and_freeze
from app.planner.phase_schedule_merge import merge_schedule
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import (
    StepExecutionSpec,
    execution_contract_or_downgrade,
)
from app.planner.resource_plan_execution_handoffs import refinement_decision
from app.planner.resource_plan_execution_scheduler import ScheduleInputs

INPUTS = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)


def _contract() -> ResolvedQueryContract:
    return ResolvedQueryContract(
        normalized_goal="hunt",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        required_capabilities={"spl", "mcp"},
    )


def _plan() -> ResourcePlan:
    return ResourcePlan(
        steps=[
            PlanStep(step_id="k1", resource_id="r.k1", purpose="knowledge_retrieval"),
            PlanStep(step_id="s1", resource_id="r.s1", purpose="spl_artifact"),
            PlanStep(
                step_id="m1",
                resource_id="r.m1",
                purpose="mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            ),
        ]
    )


def _merged_contract():
    contract, plan = _contract(), _plan()
    merged, reason = merge_schedule(contract, plan, resolve_and_freeze(contract, plan), INPUTS)
    assert reason is None and merged is not None
    execution_contract, downgrade = execution_contract_or_downgrade(plan)
    assert execution_contract is not None, downgrade
    return merged, execution_contract


def test_round_bound_is_checked_before_anything_else() -> None:
    """Cap first: new evidence and an open gap still cannot buy round 3."""
    _merged, execution_contract = _merged_contract()
    decision = refinement_decision(
        execution_contract,
        previous_produced_keys=set(),
        current_produced_keys={"soc_kb_retrieval"},
        rounds_used=MAX_GUIDED_INVESTIGATION_ROUNDS,
        max_rounds=MAX_GUIDED_INVESTIGATION_ROUNDS,
    )
    assert decision.refine is False
    assert decision.reason == "round_bound_reached"


def test_empty_evidence_buys_no_round() -> None:
    _merged, execution_contract = _merged_contract()
    decision = refinement_decision(
        execution_contract,
        previous_produced_keys=set(),
        current_produced_keys=set(),
        rounds_used=0,
        max_rounds=MAX_GUIDED_INVESTIGATION_ROUNDS,
    )
    assert decision.refine is False
    assert decision.reason == "no_new_evidence"


def test_new_evidence_alone_does_not_bypass_the_sufficiency_guard() -> None:
    """Growth plus *no remaining gap* terminates instead of spending a round."""
    _merged, execution_contract = _merged_contract()
    produced = {"soc_kb_retrieval", "candidate_spl", "spl_validation", "execution"}
    decision = refinement_decision(
        execution_contract,
        previous_produced_keys={"soc_kb_retrieval"},
        current_produced_keys=produced,
        rounds_used=0,
        max_rounds=MAX_GUIDED_INVESTIGATION_ROUNDS,
    )
    assert decision.refine is False
    assert decision.reason == "evidence_satisfied"


def test_new_evidence_with_an_open_gap_is_the_only_way_to_earn_a_round() -> None:
    _merged, execution_contract = _merged_contract()
    decision = refinement_decision(
        execution_contract,
        previous_produced_keys=set(),
        current_produced_keys={"soc_kb_retrieval"},
        rounds_used=0,
        max_rounds=MAX_GUIDED_INVESTIGATION_ROUNDS,
    )
    assert decision.refine is True
    assert decision.reason == "new_evidence_with_open_gap"
    assert decision.unresolved_gaps


def test_guided_cap_is_three_and_checked_against_the_same_bound() -> None:
    assert MAX_GUIDED_INVESTIGATION_ROUNDS == 3
    assert should_run_refinement_pass(refinement_round=1, refinement_recommended=True) is True
    assert should_run_refinement_pass(refinement_round=2, refinement_recommended=True) is False


def test_side_effecting_step_is_never_auto_repeated_in_a_merged_schedule() -> None:
    _merged, execution_contract = _merged_contract()
    mcp_step = execution_contract.step_by_id("m1")
    assert mcp_step is not None
    assert mcp_step.side_effecting is True
    assert mcp_step.max_attempts == 1


def test_no_second_refinement_mechanism_was_added() -> None:
    planner = Path(__file__).resolve().parents[1] / "planner"
    definers = [
        path.name
        for path in planner.glob("*.py")
        if "def refinement_decision(" in path.read_text(encoding="utf-8")
    ]
    assert definers == ["resource_plan_execution_handoffs.py"]
    for new_module in ("phase_schedule_merge.py", "phase_policy.py", "phase_contract.py"):
        source = (planner / new_module).read_text(encoding="utf-8")
        assert "refinement" not in source.lower()
