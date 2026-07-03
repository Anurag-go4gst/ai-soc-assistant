"""Item 3.2 — deterministic recipe selection from the promoted plan.

`select_recipe_for_plan` maps validated resource-plan purposes + answer shape
to at most one governed recipe id. The LLM never names a recipe directly.
"""

from __future__ import annotations

from app.planner.recipe_registry import get_recipe, select_recipe_for_plan, validate_recipe


def test_no_mcp_purposes_selects_none() -> None:
    assert select_recipe_for_plan(
        resource_plan_purposes={"knowledge_retrieval", "narration"},
        answer_shape="hunt",
        mcp_allowed=True,
    ) is None


def test_hunt_shape_with_grant_selects_hunt_baseline() -> None:
    assert select_recipe_for_plan(
        resource_plan_purposes={"mcp_execution"},
        answer_shape="hunt",
        mcp_allowed=True,
    ) == "hunt_baseline"


def test_hunt_shape_without_any_grant_selects_none() -> None:
    assert select_recipe_for_plan(
        resource_plan_purposes={"mcp_execution"},
        answer_shape="hunt",
        mcp_allowed=False,
        discovery_allowed=False,
    ) is None


def test_unknown_shape_selects_none() -> None:
    assert select_recipe_for_plan(
        resource_plan_purposes={"mcp_execution", "mcp_discovery"},
        answer_shape="baselining",
        mcp_allowed=True,
    ) is None


def test_discovery_only_grant_still_selects_hunt_baseline() -> None:
    assert select_recipe_for_plan(
        resource_plan_purposes={"mcp_discovery"},
        answer_shape="hunt",
        mcp_allowed=False,
        discovery_allowed=True,
    ) == "hunt_baseline"


def test_hunt_baseline_recipe_is_governance_valid() -> None:
    recipe = get_recipe("hunt_baseline")
    assert recipe is not None
    assert validate_recipe(recipe) == []
    assert recipe.max_calls == 2
    assert [c.call_id for c in recipe.calls] == ["c1_discovery", "c2_bounded_search"]
    search_call = recipe.call_by_id("c2_bounded_search")
    assert search_call is not None
    assert search_call.requires_hil is True
    assert search_call.on_empty == "hil"
