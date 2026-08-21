"""Independently falsifiable Resource Planner topology contract (plan item A0).

The documented edge set must not certify itself. Before this contract,
``resource_planner_graph_edges()`` returned ``get_graph() introspection |
documented``, so any invented documented edge became a member of the very set
the assertions checked. Here the four topology surfaces are kept separate:

* fixed edges from ``compiled.builder.edges``
* mapped conditional destinations from ``compiled.builder.branches[*].ends``
* dynamic delegate fan-out from invoking the ``Send`` contract directly
* the documented set, compared against the other three and never merged in

Reconciliation and reachability are pure functions so the mutation-negative
controls can inject a topology instead of rebuilding the ``lru_cache``d graph.
"""

from __future__ import annotations

import pytest

from app.graph.resource_planner_graph import (
    GRAPH_END_SENTINEL,
    GRAPH_START_SENTINEL,
    _SPECIALIST_NODE_NAMES,
    _documented_resource_planner_edges,
    reconcile_topology,
    resource_planner_dynamic_send_edges,
    resource_planner_dynamic_send_targets,
    resource_planner_fixed_edges,
    resource_planner_graph_edges,
    resource_planner_mapped_conditional_edges,
    resource_planner_registered_node_names,
    resource_planner_topology_reconciliation,
    resource_planner_unreachable_nodes,
    unreachable_nodes,
)

_DELEGATE = "resource_planner_delegate"
_MERGE = "resource_planner_merge"

# Nodes allowed to have no outbound edge other than the end sentinel.
_EXPLICIT_TERMINAL_NODES = {"validate_final_answer"}


def _runtime_edges() -> set[tuple[str, str]]:
    return (
        resource_planner_fixed_edges()
        | resource_planner_mapped_conditional_edges()
        | resource_planner_dynamic_send_edges()
    )


# --------------------------------------------------------------------------
# Truth sources stay separate and each carries its expected shape
# --------------------------------------------------------------------------


def test_fixed_edges_come_from_builder_and_carry_both_sentinels() -> None:
    fixed = resource_planner_fixed_edges()
    assert (GRAPH_START_SENTINEL, "bootstrap") in fixed
    assert ("validate_final_answer", GRAPH_END_SENTINEL) in fixed
    # The real head of the graph, which the documented set used to contradict.
    assert ("bootstrap", "route_resolution") in fixed
    assert ("route_resolution", _DELEGATE) in fixed
    for specialist in _SPECIALIST_NODE_NAMES:
        assert (specialist, _MERGE) in fixed


def test_mapped_conditional_destinations_are_exactly_the_declared_maps() -> None:
    assert resource_planner_mapped_conditional_edges() == {
        (_MERGE, "prepare_rag_only"),
        (_MERGE, "composed_dispatch"),
        (_MERGE, "workflow_spl"),
        (_MERGE, "non_planned_finalize"),
        ("rag_early", "spl_validate"),
        ("rag_early", "spl_source_resolve"),
        ("workflow_spl", "rag_early"),
        ("workflow_spl", "spl_source_resolve"),
        ("context_sufficiency", "plan_delta_reasoner"),
        ("context_sufficiency", "decide_facts"),
        ("plan_delta_reasoner", "composed_dispatch"),
        ("plan_delta_reasoner", "decide_facts"),
    }


def test_delegate_fan_out_sends_to_exactly_the_four_specialists() -> None:
    targets = resource_planner_dynamic_send_targets()
    assert targets == list(_SPECIALIST_NODE_NAMES)
    assert len(targets) == 4
    assert set(targets) == {
        "specialist_skill",
        "specialist_knowledge",
        "specialist_mcp",
        "specialist_spl",
    }


def test_every_specialist_fans_back_in_to_the_merge_node() -> None:
    fixed = resource_planner_fixed_edges()
    inbound_to_merge = {source for source, target in _runtime_edges() if target == _MERGE}
    assert inbound_to_merge == set(_SPECIALIST_NODE_NAMES)
    # Fan-in must be unconditional, not a branch that could route elsewhere.
    for specialist in _SPECIALIST_NODE_NAMES:
        assert (specialist, _MERGE) in fixed
    # Specialists must not chain to one another.
    ordered = list(_SPECIALIST_NODE_NAMES)
    for left, right in zip(ordered, ordered[1:]):
        assert (left, right) not in _runtime_edges()


# --------------------------------------------------------------------------
# Documented topology is checked against runtime, never merged into it
# --------------------------------------------------------------------------


def test_public_edge_accessor_is_runtime_derived_only() -> None:
    """``resource_planner_graph_edges()`` must not union in the documented set."""
    assert resource_planner_graph_edges() == _runtime_edges()


def test_documented_topology_equals_runtime_topology() -> None:
    reconciliation = resource_planner_topology_reconciliation()
    assert reconciliation.documented_only == frozenset(), sorted(reconciliation.documented_only)
    assert reconciliation.runtime_only == frozenset(), sorted(reconciliation.runtime_only)
    assert reconciliation.is_consistent


def test_documented_set_carries_no_sentinel_edges() -> None:
    documented = _documented_resource_planner_edges()
    for source, target in documented:
        assert GRAPH_START_SENTINEL not in (source, target)
        assert GRAPH_END_SENTINEL not in (source, target)


# --------------------------------------------------------------------------
# Reachability
# --------------------------------------------------------------------------


def test_no_registered_node_is_orphaned() -> None:
    assert resource_planner_unreachable_nodes() == set()


def test_every_node_has_an_outbound_edge_or_is_explicitly_terminal() -> None:
    edges = _runtime_edges()
    sources = {source for source, _ in edges}
    for node in resource_planner_registered_node_names():
        if node in sources:
            continue
        assert node in _EXPLICIT_TERMINAL_NODES, f"{node} is a dead end and not declared terminal"
    # Declared terminals must actually terminate at the end sentinel.
    for node in _EXPLICIT_TERMINAL_NODES:
        assert (node, GRAPH_END_SENTINEL) in edges


def test_route_setup_is_not_registered() -> None:
    assert "route_setup" not in resource_planner_registered_node_names()


# --------------------------------------------------------------------------
# Mutation-negative controls — each proves the contract can fail
# --------------------------------------------------------------------------


def _live_topology() -> dict[str, set[tuple[str, str]]]:
    return {
        "fixed": resource_planner_fixed_edges(),
        "mapped": resource_planner_mapped_conditional_edges(),
        "dynamic": resource_planner_dynamic_send_edges(),
        "documented": _documented_resource_planner_edges(),
    }


def test_mutation_invented_documented_edge_is_rejected() -> None:
    topology = _live_topology()
    topology["documented"] = topology["documented"] | {("bootstrap", "route_setup")}
    result = reconcile_topology(**topology)
    assert not result.is_consistent
    assert ("bootstrap", "route_setup") in result.documented_only


def test_mutation_missing_documented_edge_is_rejected() -> None:
    topology = _live_topology()
    topology["documented"] = topology["documented"] - {("bootstrap", "route_resolution")}
    result = reconcile_topology(**topology)
    assert not result.is_consistent
    assert ("bootstrap", "route_resolution") in result.runtime_only


def test_mutation_removed_send_is_rejected() -> None:
    topology = _live_topology()
    topology["dynamic"] = topology["dynamic"] - {(_DELEGATE, "specialist_spl")}
    result = reconcile_topology(**topology)
    assert not result.is_consistent
    assert (_DELEGATE, "specialist_spl") in result.documented_only


def test_mutation_retargeted_send_is_rejected() -> None:
    topology = _live_topology()
    topology["dynamic"] = (topology["dynamic"] - {(_DELEGATE, "specialist_mcp")}) | {
        (_DELEGATE, "specialist_impostor")
    }
    result = reconcile_topology(**topology)
    assert not result.is_consistent
    assert (_DELEGATE, "specialist_impostor") in result.runtime_only
    assert (_DELEGATE, "specialist_mcp") in result.documented_only


def test_mutation_removed_fan_in_is_rejected() -> None:
    topology = _live_topology()
    topology["fixed"] = topology["fixed"] - {("specialist_knowledge", _MERGE)}
    result = reconcile_topology(**topology)
    assert not result.is_consistent
    assert ("specialist_knowledge", _MERGE) in result.documented_only


def test_mutation_injected_orphan_is_detected() -> None:
    nodes = resource_planner_registered_node_names() | {"orphan_node"}
    assert unreachable_nodes(nodes=nodes, edges=_runtime_edges()) == {"orphan_node"}


def test_mutation_severed_edge_orphans_its_whole_subtree() -> None:
    edges = _runtime_edges() - {("bootstrap", "route_resolution")}
    orphaned = unreachable_nodes(nodes=resource_planner_registered_node_names(), edges=edges)
    assert "route_resolution" in orphaned
    assert _DELEGATE in orphaned
    assert "bootstrap" not in orphaned


@pytest.mark.parametrize("sentinel", [GRAPH_START_SENTINEL, GRAPH_END_SENTINEL])
def test_reconciliation_normalizes_sentinels_on_both_sides(sentinel: str) -> None:
    """A sentinel edge on either side must not create a spurious mismatch."""
    topology = _live_topology()
    topology["documented"] = topology["documented"] | {(sentinel, "bootstrap")}
    assert reconcile_topology(**topology).is_consistent
