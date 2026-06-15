"""O5b — scheduler/reconcile pure-function tests (fixture-only).

Proves the two required paths (plan implementation order #2): metadata-MCP can
run before SPL when it is an explicit prerequisite, and Search-A -> Search-B
fires only on the predeclared empty edge. No connector is touched; outcomes are
scripted fixtures.
"""

from __future__ import annotations

from app.orchestration.mcp_orchestration import CallBudget, CallOutcome, McpCallRecord
from app.planner.orchestration_scheduler import (
    outcome_edge,
    schedule_next,
    unresolved_evidence_keys,
)
from app.planner.recipe_registry import (
    Recipe,
    RecipeCall,
    get_recipe,
    validate_recipe,
)

_SEARCH_CHAIN = ["r5_relevance", "source_resolve", "validate_spl", "allowlist", "approval"]


def _record(call_id: str, sequence: int, outcome: CallOutcome) -> McpCallRecord:
    return McpCallRecord(call_id=call_id, sequence=sequence, outcome=outcome)


def _drive(recipe: Recipe, scripted: dict[str, CallOutcome], max_calls: int) -> list[str]:
    """Run the scheduler loop against scripted outcomes; return executed order.

    Asserts at most one call is scheduled per visit (one connector call per
    executor-node visit, plan A.14).
    """
    records: list[McpCallRecord] = []
    budget = CallBudget(max_calls=max_calls)
    order: list[str] = []
    for _ in range(max_calls + 2):  # bounded; loop must terminate on its own
        decision = schedule_next(recipe, records, budget)
        if decision.action == "stop":
            break
        assert decision.call_id is not None
        order.append(decision.call_id)
        budget.calls_started += 1
        records.append(
            _record(decision.call_id, len(records) + 1, scripted[decision.call_id])
        )
        budget.calls_completed += 1
    return order


# --- metadata-before-SPL prerequisite -----------------------------------------


def _metadata_then_search_recipe() -> Recipe:
    return Recipe(
        recipe_id="metadata_then_search",
        eligible_skills=["spl_generation"],
        max_calls=2,
        calls=[
            RecipeCall(
                call_id="d1_discover",
                purpose="Discover indexes/sourcetypes before SPL.",
                call_class="metadata_discovery",
                activation_condition="always",
                resource_capability="index_metadata",
                produces_evidence_keys=["source_profile"],
                requires_hil=False,
                on_empty="terminal",
            ),
            RecipeCall(
                call_id="s1_search",
                purpose="Search once the source profile is known.",
                call_class="evidence_search",
                depends_on=["d1_discover"],
                activation_condition="previous_ok",
                resource_capability="spl_search",
                spl_source="template_family",
                produces_evidence_keys=["search_rows"],
                requires_hil=True,
                validation_chain=list(_SEARCH_CHAIN),
                terminal=True,
            ),
        ],
    )


def test_metadata_recipe_validates() -> None:
    assert validate_recipe(_metadata_then_search_recipe()) == []


def test_metadata_runs_before_search() -> None:
    recipe = _metadata_then_search_recipe()
    order = _drive(recipe, {"d1_discover": "ok", "s1_search": "ok"}, max_calls=2)
    assert order == ["d1_discover", "s1_search"]


def test_search_blocked_until_metadata_ok() -> None:
    recipe = _metadata_then_search_recipe()
    # Discovery fails -> search never activates (previous_ok unmet), fail closed.
    order = _drive(recipe, {"d1_discover": "failed", "s1_search": "ok"}, max_calls=2)
    assert order == ["d1_discover"]


# --- Search-A -> Search-B (broaden_scope_on_empty) ----------------------------


def test_broaden_fires_only_on_empty_primary() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None

    # Primary returns rows -> no broadened call.
    order_ok = _drive(
        recipe,
        {"c1_primary_search": "ok", "c2_broadened_search": "ok"},
        max_calls=2,
    )
    assert order_ok == ["c1_primary_search"]

    # Primary empty -> broadened call fires (Search-A -> Search-B).
    order_empty = _drive(
        recipe,
        {"c1_primary_search": "empty", "c2_broadened_search": "ok"},
        max_calls=2,
    )
    assert order_empty == ["c1_primary_search", "c2_broadened_search"]


def test_broaden_does_not_retry_after_second_empty() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    order = _drive(
        recipe,
        {"c1_primary_search": "empty", "c2_broadened_search": "empty"},
        max_calls=2,
    )
    # No third call: a still-empty broadened result is terminal honest negative.
    assert order == ["c1_primary_search", "c2_broadened_search"]


# --- budget + fail-closed -----------------------------------------------------


def test_budget_caps_the_loop() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    budget = CallBudget(max_calls=1)
    records = [_record("c1_primary_search", 1, "empty")]
    budget.calls_started = 1
    decision = schedule_next(recipe, records, budget)
    # c2 is ready (previous_empty) but the budget is spent.
    assert decision.action == "stop"
    assert decision.stop_reason == "budget_exhausted"


def test_hard_failure_fails_closed() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    records = [_record("c1_primary_search", 1, "denied")]
    decision = schedule_next(recipe, records, CallBudget(max_calls=2))
    assert decision.action == "stop"
    assert decision.stop_reason == "fail_closed:denied"


def test_unresolved_keys_tracked() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    # Empty resolves the key as honest negative evidence.
    keys = unresolved_evidence_keys(recipe, [_record("c1_primary_search", 1, "empty")])
    assert "primary_search_rows" not in keys
    assert "broadened_search_rows" in keys


# --- outcome edges ------------------------------------------------------------


def test_outcome_edge_mapping() -> None:
    recipe = get_recipe("broaden_scope_on_empty")
    assert recipe is not None
    primary = recipe.call_by_id("c1_primary_search")
    assert primary is not None
    assert outcome_edge(primary, "empty") == "c2_broadened_search"
    assert outcome_edge(primary, "denied") == "hil"
    assert outcome_edge(primary, "timeout") == "hil"
    assert outcome_edge(primary, "partial") == "hil"
