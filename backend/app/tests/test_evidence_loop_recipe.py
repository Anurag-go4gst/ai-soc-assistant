"""Item 3.1 — O5c: recipe-aware HUB path in evidence_loop.py.

The chronology-driven assess_loop stays the default; these functions are the
NEW recipe-aware alternative, delegating scheduling to the pure O5b functions
(orchestration_scheduler.schedule_next) and translating outcomes into the
same LoopDecision route vocabulary the rest of the pipeline already dispatches
on — no existing routing code changes.
"""

from __future__ import annotations

from app.chat.evidence_loop import (
    MAX_MCP_HOPS,
    ROUTE_EXECUTE,
    ROUTE_EXHAUSTED,
    ROUTE_FINALIZE,
    ROUTE_HUMAN_REVIEW,
    assess_loop_with_recipe,
    classify_call_outcome,
    record_recipe_call,
)
from app.planner.recipe_registry import get_recipe


def test_broaden_recipe_two_call_flow_executes_first_then_second_on_empty() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    state: dict = {}

    first = assess_loop_with_recipe(state, recipe)
    assert first.route == ROUTE_EXECUTE
    assert first.next_tool == "c1_primary_search"

    patch = record_recipe_call(state, call_id="c1_primary_search", execution={"status": "executed", "result_count": 0})
    state = {**state, **patch}

    second = assess_loop_with_recipe(state, recipe)
    assert second.route == ROUTE_EXECUTE
    assert second.next_tool == "c2_broadened_search"


def test_broaden_recipe_finalizes_when_first_call_has_rows() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    state: dict = {}
    patch = record_recipe_call(state, call_id="c1_primary_search", execution={"status": "executed", "result_count": 3})
    state = {**state, **patch}
    decision = assess_loop_with_recipe(state, recipe)
    assert decision.route == ROUTE_FINALIZE


def test_hard_failure_fails_closed_no_further_scheduling() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    state: dict = {}
    patch = record_recipe_call(state, call_id="c1_primary_search", execution={"status": "failed"})
    state = {**state, **patch}
    decision = assess_loop_with_recipe(state, recipe)
    assert decision.route == ROUTE_HUMAN_REVIEW
    assert decision.reason.startswith("fail_closed:")


def test_pending_hil_execution_not_recorded_as_a_call() -> None:
    """A 'requires_human_review' execution means the call has not terminated
    yet — it must not be recorded as a resolved McpCallRecord."""
    outcome = classify_call_outcome({"status": "requires_human_review"})
    assert outcome is None
    patch = record_recipe_call({}, call_id="c1_primary_search", execution={"status": "requires_human_review"})
    assert patch == {}


def test_budget_exhausted_stops_before_recipe_max_calls() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe.max_calls == 2
    state = {"mcp_call_records": [], "mcp_hops_done": 0}
    # Manually simulate 2 completed calls to exhaust the recipe's own budget.
    p1 = record_recipe_call(state, call_id="c1_primary_search", execution={"status": "executed", "result_count": 0})
    state = {**state, **p1}
    p2 = record_recipe_call(state, call_id="c2_broadened_search", execution={"status": "executed", "result_count": 0})
    state = {**state, **p2}
    decision = assess_loop_with_recipe(state, recipe)
    assert decision.route in {ROUTE_FINALIZE, ROUTE_EXHAUSTED}


def test_global_hop_budget_never_raised_by_recipe() -> None:
    recipe = get_recipe("single_search")
    state = {"mcp_hops_done": MAX_MCP_HOPS}
    decision = assess_loop_with_recipe(state, recipe)
    assert decision.route == ROUTE_EXHAUSTED
    assert decision.proceed_with_available is True


def test_outcome_classification_ok_vs_empty_vs_blocked() -> None:
    assert classify_call_outcome({"status": "executed", "result_count": 5}) == "ok"
    assert classify_call_outcome({"status": "executed", "result_count": 0}) == "empty"
    assert classify_call_outcome({"status": "blocked"}) == "blocked"
    assert classify_call_outcome({"status": "skipped"}) == "failed"
