"""Plan 2 C1-E5 — failure, skip, fallback and finalization for execution-driven order.

Multi-step execution must fail closed without losing the evidence it already
has, without repeating a side effect, and without retrying anything uncertain.
Statuses are pure functions of the outcomes, so replaying a turn is stable.
"""

from __future__ import annotations

import pytest

from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_plan_execution import build_execution_contract
from app.planner.resource_plan_execution_outcomes import (
    HARD_FAILURE_OUTCOMES,
    ExecutionOutcome,
    StepDisposition,
    finalization_decision,
    reconcile_execution,
)


def _step(step_id: str, purpose: str, **kwargs) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=f"resource:{purpose}", purpose=purpose, **kwargs)


def _contract(*steps: PlanStep):
    return build_execution_contract(ResourcePlan(steps=list(steps)))


def _spl_mcp():
    return _contract(
        _step("rag", "knowledge_retrieval"),
        _step("spl", "spl_artifact"),
        _step("mcp", "mcp_execution"),
    )


# --- outcome matrix -----------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (ExecutionOutcome.OK, StepDisposition.COMPLETED),
        (ExecutionOutcome.EMPTY, StepDisposition.COMPLETED_EMPTY),
        (ExecutionOutcome.FAILED, StepDisposition.FAILED),
        (ExecutionOutcome.TIMEOUT, StepDisposition.FAILED),
        (ExecutionOutcome.DENIED, StepDisposition.BLOCKED),
        (ExecutionOutcome.UNCERTAIN, StepDisposition.UNCERTAIN),
    ],
)
def test_each_outcome_maps_to_one_disposition(
    outcome: ExecutionOutcome, expected: StepDisposition
) -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": outcome})
    assert result.dispositions["spl"] == expected


def test_hard_failures_are_declared_not_inferred() -> None:
    assert HARD_FAILURE_OUTCOMES == frozenset(
        {ExecutionOutcome.FAILED, ExecutionOutcome.TIMEOUT, ExecutionOutcome.DENIED}
    )


# --- propagation --------------------------------------------------------------


def test_failed_dependency_skips_its_dependents_without_running_them() -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": ExecutionOutcome.FAILED})
    assert result.dispositions["mcp"] == StepDisposition.SKIPPED
    assert result.skip_reasons["mcp"] == "dependency_failed:spl"
    assert "mcp" not in result.runnable_step_ids


def test_independent_step_still_runs_after_an_unrelated_failure() -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": ExecutionOutcome.FAILED})
    assert result.dispositions["rag"] == StepDisposition.PENDING
    assert "rag" in result.runnable_step_ids


def test_empty_dependency_is_not_a_failure_for_its_dependents() -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": ExecutionOutcome.EMPTY})
    assert result.dispositions["mcp"] == StepDisposition.PENDING


def test_composition_blocked_step_stays_blocked_and_blocks_downstream() -> None:
    contract = _contract(
        _step("spl", "spl_artifact", status="blocked_policy", status_reason="skill_contract"),
        _step("mcp", "mcp_execution"),
    )
    result = reconcile_execution(contract, {})
    assert result.dispositions["spl"] == StepDisposition.BLOCKED
    assert result.skip_reasons["spl"] == "skill_contract"
    # Composition-time blocking already propagated in the contract, so the
    # dependent arrives non-executable and keeps that provenance rather than
    # being reclassified as a runtime skip.
    assert result.dispositions["mcp"] == StepDisposition.BLOCKED
    assert result.skip_reasons["mcp"] == "dependency_blocked:spl"


# --- no automatic retry of uncertain or side-effecting work -------------------


def test_uncertain_side_effect_is_never_retried_and_stops_for_review() -> None:
    result = reconcile_execution(_spl_mcp(), {"mcp": ExecutionOutcome.UNCERTAIN})
    assert result.dispositions["mcp"] == StepDisposition.UNCERTAIN
    assert result.retry_step_ids == []
    assert result.requires_human_review is True
    assert result.stop_reason == "uncertain_side_effect"


def test_failed_side_effecting_step_is_never_retried() -> None:
    result = reconcile_execution(_spl_mcp(), {"mcp": ExecutionOutcome.FAILED})
    assert result.retry_step_ids == []


def test_read_only_failure_is_not_auto_retried_either_without_declared_attempts() -> None:
    result = reconcile_execution(_spl_mcp(), {"rag": ExecutionOutcome.FAILED})
    assert result.retry_step_ids == []


# --- fallback targets ---------------------------------------------------------


def test_hil_fallback_target_requests_human_review() -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": ExecutionOutcome.FAILED})
    assert result.requires_human_review is True
    assert result.fallback_targets["spl"] == "hil"


def test_terminal_fallback_target_stops_without_human_review() -> None:
    from app.planner.resource_plan_execution import StepExecutionSpec

    contract = _contract(
        _step(
            "rag",
            "knowledge_retrieval",
            execution=StepExecutionSpec(on_failure="terminal"),
        )
    )
    result = reconcile_execution(contract, {"rag": ExecutionOutcome.FAILED})
    assert result.fallback_targets["rag"] == "terminal"
    assert result.requires_human_review is False


def test_denied_outcome_blocks_and_requests_review() -> None:
    result = reconcile_execution(_spl_mcp(), {"mcp": ExecutionOutcome.DENIED})
    assert result.dispositions["mcp"] == StepDisposition.BLOCKED
    assert result.requires_human_review is True


# --- finalization -------------------------------------------------------------


def test_finalization_runs_once_even_with_failures() -> None:
    result = reconcile_execution(_spl_mcp(), {"spl": ExecutionOutcome.FAILED})
    decision = finalization_decision(result, already_finalized=False)
    assert decision.finalize is True
    second = finalization_decision(result, already_finalized=True)
    assert second.finalize is False
    assert second.reason == "already_finalized"


def test_partial_evidence_finalizes_with_declared_limitations() -> None:
    result = reconcile_execution(
        _spl_mcp(), {"rag": ExecutionOutcome.OK, "spl": ExecutionOutcome.FAILED}
    )
    decision = finalization_decision(result, already_finalized=False)
    assert decision.finalize is True
    assert decision.limitations == ["step_failed:spl", "step_skipped:mcp"]
    assert decision.partial is True


def test_complete_run_finalizes_without_limitations() -> None:
    result = reconcile_execution(
        _spl_mcp(),
        {
            "rag": ExecutionOutcome.OK,
            "spl": ExecutionOutcome.OK,
            "mcp": ExecutionOutcome.OK,
        },
    )
    decision = finalization_decision(result, already_finalized=False)
    assert decision.partial is False
    assert decision.limitations == []


def test_empty_evidence_finalizes_honestly_rather_than_claiming_results() -> None:
    result = reconcile_execution(
        _spl_mcp(),
        {"rag": ExecutionOutcome.EMPTY, "spl": ExecutionOutcome.OK, "mcp": ExecutionOutcome.EMPTY},
    )
    decision = finalization_decision(result, already_finalized=False)
    assert decision.finalize is True
    assert decision.limitations == ["step_returned_no_results:rag", "step_returned_no_results:mcp"]


# --- determinism / rollback ---------------------------------------------------


def test_reconciliation_is_idempotent_for_identical_outcomes() -> None:
    outcomes = {"rag": ExecutionOutcome.OK, "spl": ExecutionOutcome.FAILED}
    first = reconcile_execution(_spl_mcp(), outcomes)
    second = reconcile_execution(_spl_mcp(), outcomes)
    assert first == second


def test_absent_contract_rolls_back_to_the_fixed_schedule_contract() -> None:
    result = reconcile_execution(None, {"spl": ExecutionOutcome.FAILED})
    assert result.dispositions == {}
    assert result.stop_reason == "no_execution_contract"
    assert result.requires_human_review is False


def test_outcome_module_is_pure() -> None:
    import ast
    import inspect

    from app.planner import resource_plan_execution_outcomes

    tree = ast.parse(inspect.getsource(resource_plan_execution_outcomes))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in ("app.config", "app.connectors", "app.mcp", "app.llm", "httpx", "requests"):
        assert not any(name.startswith(forbidden) for name in imported), forbidden
