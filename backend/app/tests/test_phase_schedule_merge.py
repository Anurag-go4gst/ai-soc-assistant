"""Plan 5 C1 — one deterministic merge into one dependency-valid schedule.

The load-bearing property, from the measured B5 regression: capability
satisfaction is a property of the whole governed schedule, not of the routed
skill.
"""

from __future__ import annotations

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.planner.phase_contract import resolve_and_freeze
from app.planner.phase_policy import PhasePolicyInputs
from app.planner.phase_schedule_merge import (
    evaluate_capability_satisfaction,
    merge_schedule,
)
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import StepExecutionSpec
from app.planner.resource_plan_execution_scheduler import ScheduleInputs

INPUTS = ScheduleInputs(blocked_step_ids=frozenset(), has_workflow_plan=False)


def _contract(**overrides) -> ResolvedQueryContract:
    payload = {
        "normalized_goal": "goal",
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "ambiguity_state": "unambiguous",
        "qualification_tier": "T1",
        "qualification_source": "exact_105",
        "required_capabilities": {"spl", "mcp"},
    }
    payload.update(overrides)
    return ResolvedQueryContract(**payload)


def _step(step_id: str, purpose: str, **kwargs) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=f"r.{step_id}", purpose=purpose, **kwargs)


def _merge(contract, plan, *, inputs: ScheduleInputs = INPUTS, policy_inputs=None):
    phase_contract = resolve_and_freeze(contract, plan, policy_inputs)
    return merge_schedule(contract, plan, phase_contract, inputs)


# --- the interleaved shape ----------------------------------------------------


def test_interleaved_knowledge_spl_mcp_plan_compiles_to_one_valid_schedule() -> None:
    """knowledge → mcp → knowledge → spl → validate → mcp → gap → spl → validate → mcp → synthesis."""
    plan = ResourcePlan(
        steps=[
            _step("k1", "knowledge_retrieval"),
            _step(
                "m1",
                "mcp_discovery",
                execution=StepExecutionSpec(depends_on=["k1"], max_attempts=1),
            ),
            _step(
                "k2",
                "knowledge_retrieval",
                execution=StepExecutionSpec(depends_on=["m1"], max_attempts=1),
            ),
            _step(
                "s1",
                "spl_artifact",
                execution=StepExecutionSpec(depends_on=["k2"], max_attempts=1),
            ),
            _step(
                "m2",
                "mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            ),
            _step(
                "g1",
                "context_sufficiency",
                execution=StepExecutionSpec(depends_on=["m2"], max_attempts=1),
            ),
            _step(
                "s2",
                "spl_artifact",
                execution=StepExecutionSpec(depends_on=["g1"], max_attempts=1),
            ),
            _step(
                "m3",
                "mcp_execution",
                execution=StepExecutionSpec(depends_on=["s2"], max_attempts=1),
            ),
            _step(
                "n1",
                "narration",
                execution=StepExecutionSpec(depends_on=["m3"], max_attempts=1),
            ),
        ]
    )
    merged, reason = _merge(_contract(), plan)
    assert reason is None and merged is not None

    hooks = list(merged.hooks)
    assert hooks.index("workflow_spl") < hooks.index("spl_postprocessor")
    assert hooks.index("spl_postprocessor") < hooks.index("execution")
    # Repetition lives in the plan, not in the hook vocabulary: two SPL steps and
    # three MCP steps, ordered by dependencies across the waves.
    flat = [step for wave in merged.waves for step in wave]
    assert flat.index("s1") < flat.index("m2") < flat.index("s2") < flat.index("m3")
    assert merged.capability.satisfied is True


def test_ordering_is_not_a_fixed_knowledge_spl_mcp_sequence() -> None:
    """An SPL-first plan and a knowledge-first plan both compile validly."""
    spl_first = ResourcePlan(
        steps=[
            _step("s1", "spl_artifact"),
            _step(
                "k1",
                "knowledge_retrieval",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            ),
        ]
    )
    merged, reason = _merge(_contract(required_capabilities={"spl"}), spl_first)
    assert reason is None and merged is not None
    flat = [step for wave in merged.waves for step in wave]
    assert flat.index("s1") < flat.index("k1")


# --- the C1 fix for the Plan 3 A0 stage drop ----------------------------------


def test_merge_reinserts_the_phase_the_compiler_cannot_schedule() -> None:
    """`spl_postprocessor` is absent from SCHEDULABLE_HOOKS — the contract puts it back."""
    from app.planner.resource_plan_execution_scheduler import (
        SCHEDULABLE_HOOKS,
        compile_execution_schedule,
    )

    plan = ResourcePlan(steps=[_step("s1", "spl_artifact"), _step("m1", "mcp_execution")])
    compiled, _ = compile_execution_schedule(plan, INPUTS)
    assert "spl_postprocessor" not in SCHEDULABLE_HOOKS
    assert "spl_postprocessor" not in compiled.hooks

    merged, reason = _merge(_contract(), plan)
    assert reason is None and merged is not None
    assert "spl_postprocessor" in merged.hooks
    assert "spl_postprocessor" in merged.inserted_phases
    assert merged.hooks.index("spl_postprocessor") < merged.hooks.index("execution")


def test_reference_finalize_is_inserted_only_when_the_contract_says_applicable() -> None:
    plan = ResourcePlan(steps=[_step("k1", "knowledge_retrieval")])

    without, _ = _merge(
        _contract(required_capabilities=set(), answer_goal="policy_citation"), plan
    )
    assert without is not None and "reference_finalize" not in without.hooks

    with_reference, _ = _merge(
        _contract(
            required_capabilities=set(),
            answer_goal="reference_lookup",
            intent_family="reference_knowledge",
        ),
        plan,
    )
    assert with_reference is not None and "reference_finalize" in with_reference.hooks


def test_inline_phases_are_reported_rather_than_dropped() -> None:
    plan = ResourcePlan(steps=[_step("k1", "knowledge_retrieval")])
    merged, _ = _merge(
        _contract(required_capabilities=set(), answer_goal="mitre_mapping"), plan
    )
    assert merged is not None
    assert "mitre_finalize" in merged.inline_phases
    assert "mitre_finalize" not in merged.hooks


# --- fail closed --------------------------------------------------------------


def test_cyclic_plan_is_rejected_not_scheduled() -> None:
    plan = ResourcePlan(
        steps=[
            _step("a", "spl_artifact", execution=StepExecutionSpec(depends_on=["b"])),
            _step("b", "mcp_execution", execution=StepExecutionSpec(depends_on=["a"])),
        ]
    )
    merged, reason = _merge(_contract(), plan)
    assert merged is None and reason


def test_absent_plan_downgrades_to_the_fixed_schedule() -> None:
    merged, reason = _merge(_contract(), None)
    assert merged is None and reason


def test_unsupported_purpose_downgrades() -> None:
    plan = ResourcePlan(steps=[_step("x1", "teach_the_model_to_route")])
    merged, reason = _merge(_contract(), plan)
    assert merged is None and reason


def test_side_effecting_step_may_not_declare_a_retry() -> None:
    plan = ResourcePlan(
        steps=[
            _step("s1", "spl_artifact"),
            _step(
                "m1",
                "mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=3),
            ),
        ]
    )
    merged, reason = _merge(_contract(), plan)
    assert merged is None and reason


def test_read_only_step_may_repeat_when_justified() -> None:
    plan = ResourcePlan(
        steps=[
            _step("k1", "knowledge_retrieval", execution=StepExecutionSpec(max_attempts=3)),
        ]
    )
    merged, reason = _merge(_contract(required_capabilities=set()), plan)
    assert reason is None and merged is not None


# --- schedule-level capability satisfaction (Plan 5 amendment 5) --------------


def test_spl_primary_schedule_satisfies_spl_and_mcp() -> None:
    """The exact case B5's route-level veto got wrong (`cisco.ot.029`)."""
    plan = ResourcePlan(
        steps=[
            _step("s1", "spl_artifact"),
            _step(
                "m1",
                "mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            ),
        ]
    )
    merged, reason = _merge(_contract(required_capabilities={"spl", "mcp"}), plan)
    assert reason is None and merged is not None
    assert merged.capability.satisfied is True
    assert merged.capability.granted >= {"spl", "mcp"}
    assert merged.capability.missing == frozenset()


def test_capability_shortfall_is_reported_not_vetoed_into_a_route_change() -> None:
    """Unsatisfied capability is a schedule fact. It changes no route here."""
    plan = ResourcePlan(steps=[_step("k1", "knowledge_retrieval")])
    contract = _contract(required_capabilities={"spl"})
    satisfaction = evaluate_capability_satisfaction(contract, plan, ["prepare_rag_only", "rag_early"])
    assert satisfaction.satisfied is False
    assert satisfaction.missing == {"spl"}
    assert satisfaction.prohibited_violated == frozenset()


def test_prohibited_capability_in_the_schedule_fails_satisfaction() -> None:
    plan = ResourcePlan(steps=[_step("s1", "spl_artifact")])
    contract = _contract(required_capabilities={"spl"}, prohibited_capabilities={"mcp"})
    satisfaction = evaluate_capability_satisfaction(contract, plan, ["workflow_spl", "execution"])
    assert satisfaction.prohibited_violated == {"mcp"}
    assert satisfaction.satisfied is False


def test_capability_evaluation_makes_no_model_call() -> None:
    import ast
    from pathlib import Path

    import app.planner.phase_schedule_merge as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not {m for m in imported if m.startswith(("app.llm", "app.config", "httpx"))}


@pytest.mark.parametrize("has_mcp_step", [True, False])
def test_every_merged_schedule_validates_against_its_own_contract(has_mcp_step: bool) -> None:
    steps = [_step("k1", "knowledge_retrieval"), _step("s1", "spl_artifact")]
    if has_mcp_step:
        steps.append(
            _step(
                "m1",
                "mcp_execution",
                execution=StepExecutionSpec(depends_on=["s1"], max_attempts=1),
            )
        )
    plan = ResourcePlan(steps=steps)
    contract = _contract()
    phase_contract = resolve_and_freeze(contract, plan, PhasePolicyInputs())
    merged, reason = merge_schedule(contract, plan, phase_contract, INPUTS)
    assert reason is None and merged is not None
    phase_contract.validate_schedule(list(merged.hooks))
