"""O5a — recipe registry + MCP orchestration contract tests.

Contract-only: assert governed recipe shape, the HIL-approval execution gate,
and the candidate-SPL-never-executes invariant. No connector behaviour is
exercised here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.orchestration.mcp_orchestration import (
    CallBudget,
    McpOrchestration,
    approve_call,
    build_call_spec,
    can_execute_call,
    reject_call,
)
from app.planner.recipe_registry import (
    RecipeCall,
    evaluate_activation,
    get_recipe,
    load_recipe_registry,
    recipes_for_skill,
    validate_recipe,
)
from app.planner.resource_plan import PlanStepV2, ResourcePlanV2


# --- recipe registry shape ----------------------------------------------------


def test_registry_ships_three_governed_recipes() -> None:
    # hunt_baseline added item 3.2 (2026-07-03): discovery -> bounded search
    # -> on-empty broaden edge to HIL.
    registry = load_recipe_registry()
    assert set(registry) == {"single_search", "broaden_scope_on_empty", "hunt_baseline"}


def test_all_shipped_recipes_validate() -> None:
    for recipe in load_recipe_registry().values():
        assert validate_recipe(recipe) == []


def test_single_search_is_one_terminal_call() -> None:
    recipe = get_recipe("single_search")
    assert recipe is not None
    assert recipe.max_calls == 1
    assert len(recipe.calls) == 1
    assert recipe.calls[0].terminal is True
    assert recipe.calls[0].on_empty == "terminal"


def test_broaden_recipe_empty_triggers_llm_proposed_hil_call() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    assert recipe.max_calls == 2

    primary = recipe.call_by_id("c1_primary_search")
    broadened = recipe.call_by_id("c2_broadened_search")
    assert primary is not None and broadened is not None

    # Empty primary result is the deterministic trigger for the broadened call.
    assert primary.on_empty == "c2_broadened_search"
    assert broadened.activation_condition == "previous_empty"
    assert broadened.depends_on == ["c1_primary_search"]

    # Broadened query is LLM-proposed but advisory: full chain + HIL approval.
    assert broadened.spl_source == "llm_failover_candidate"
    assert broadened.requires_hil is True
    assert broadened.validation_chain == [
        "r5_relevance",
        "source_resolve",
        "validate_spl",
        "allowlist",
        "approval",
    ]
    # A still-empty broadened result is honest negative — never another retry.
    assert broadened.on_empty == "terminal"
    assert broadened.terminal is True


def test_recipes_for_skill_lookup() -> None:
    ids = {recipe.recipe_id for recipe in recipes_for_skill("spl_generation")}
    assert ids == {"single_search", "broaden_scope_on_empty"}
    assert recipes_for_skill("knowledge_recall") == []


def test_candidate_spl_is_never_an_executable_source() -> None:
    with pytest.raises(ValidationError):
        RecipeCall(
            call_id="x",
            purpose="bad",
            call_class="evidence_search",
            resource_capability="spl_search",
            spl_template_family="candidate_spl",
        )


def test_validate_recipe_flags_search_without_hil() -> None:
    recipe = get_recipe("single_search")
    assert recipe is not None
    recipe.calls[0].requires_hil = False
    problems = validate_recipe(recipe)
    assert any("HIL" in problem for problem in problems)


def test_validate_recipe_flags_dangling_edge() -> None:
    recipe = get_recipe("single_search")
    assert recipe is not None
    recipe.calls[0].on_empty = "does_not_exist"
    problems = validate_recipe(recipe)
    assert any("on_empty" in problem for problem in problems)


# --- activation ---------------------------------------------------------------


def test_activation_previous_empty_only_fires_on_empty() -> None:
    assert evaluate_activation("previous_empty", prior_outcome="empty", missing_keys=[]) is True
    assert evaluate_activation("previous_empty", prior_outcome="ok", missing_keys=[]) is False
    assert evaluate_activation("always", prior_outcome=None, missing_keys=[]) is True


# --- HIL-approval execution gate ----------------------------------------------


def test_search_call_blocked_until_hil_approves_then_executes() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    broadened = recipe.call_by_id("c2_broadened_search")
    assert broadened is not None

    spec = build_call_spec(
        broadened,
        sequence=2,
        server="splunk_local",
        tool="splunk_run_query",
        normalized_spl_hash="abc123",
    )
    assert spec.approval_state == "pending"

    allowed, reason = can_execute_call(spec)
    assert allowed is False
    assert reason == "hil_approval_pending"

    # If HIL approves, the call executes.
    approved = approve_call(spec, normalized_spl_hash="abc123")
    allowed, reason = can_execute_call(approved)
    assert allowed is True and reason is None


def test_hil_rejection_blocks_execution() -> None:
    recipe = get_recipe("single_search")
    assert recipe is not None
    spec = build_call_spec(
        recipe.calls[0], sequence=1, tool="splunk_run_query", normalized_spl_hash="h"
    )
    rejected = reject_call(spec)
    allowed, reason = can_execute_call(rejected)
    assert allowed is False
    assert reason == "hil_approval_rejected"


def test_search_call_needs_bound_spl_hash() -> None:
    recipe = get_recipe("single_search")
    assert recipe is not None
    spec = build_call_spec(recipe.calls[0], sequence=1, tool="splunk_run_query")
    approved = approve_call(spec)  # approve without binding a hash
    allowed, reason = can_execute_call(approved)
    assert allowed is False
    assert reason == "missing_normalized_spl_hash"


def test_call_budget_capacity() -> None:
    budget = CallBudget(max_calls=2, calls_started=1)
    assert budget.has_call_capacity() is True
    budget.calls_started = 2
    assert budget.has_call_capacity() is False


def test_orchestration_envelope_defaults() -> None:
    orch = McpOrchestration(orchestration_id="t1", recipe_id="single_search")
    assert orch.schema_version == "1"
    assert orch.status == "planned"
    assert orch.next_call is None


# --- ResourcePlanV2 additive contract -----------------------------------------


def test_resource_plan_v2_carries_dependencies_and_failover() -> None:
    plan = ResourcePlanV2(
        recipe_id="broaden_scope_on_empty",
        steps=[
            PlanStepV2(
                step_id="c1",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
                resource_capability="spl_search",
                produces_evidence_keys=["primary_search_rows"],
                on_empty="c2",
            ),
            PlanStepV2(
                step_id="c2",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
                depends_on=["c1"],
                activation_condition="previous_empty",
                resource_capability="spl_search",
            ),
        ],
    )
    assert plan.schema_version == "2"
    assert plan.step_by_id("c1").on_empty == "c2"
    assert plan.step_by_id("c2").activation_condition == "previous_empty"
