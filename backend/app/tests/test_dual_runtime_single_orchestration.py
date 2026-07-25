"""AST and graph-transition guards for dual-runtime single orchestration (plan item 33)."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.chat.contracts.canonical_planning_outcome import (
    clarification_outcome,
    failure_outcome,
    policy_blocked_outcome,
)
from app.graph.resource_planner_graph import (
    _rp_dispatch_route,
    resource_planner_graph_edges,
    rp_node_bootstrap,
)

_SPL_EXECUTION_NODES = frozenset(
    {"workflow_spl", "spl_validate", "spl_source_resolve", "mcp_execution_gate", "composed_dispatch"}
)

_FORBIDDEN_DIRECT_PLANNING_CALLS = frozenset(
    {
        "graph_node_lane_and_canonical_planning",
        "graph_node_route_resolution",
        "graph_node_route_contract",
        "_graph_node_planning_decision_from_canonical",
        "graph_node_evidence_planning",
    }
)


def _callable_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _function_call_names(func: Callable[..., Any]) -> set[str]:
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _callable_name(node.func)
            if name:
                names.add(name)
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    names.add(arg.id)
    return names


def _function_has_call(func: Callable[..., Any], name: str) -> bool:
    return name in _function_call_names(func)


_IMPERATIVE_ENTRY_FORBIDDEN = _FORBIDDEN_DIRECT_PLANNING_CALLS - {"graph_node_evidence_planning"}


def _assert_no_forbidden_direct_planning(
    func: Callable[..., Any],
    *,
    entrypoint: str,
    forbidden: frozenset[str] = _FORBIDDEN_DIRECT_PLANNING_CALLS,
) -> None:
    calls = _function_call_names(func)
    violations = sorted(calls & forbidden)
    assert not violations, f"{entrypoint} must not call planning nodes directly: {violations}"


def _state_with_outcome(status: str) -> dict[str, Any]:
    if status == "clarification_required":
        outcome = clarification_outcome(
            canonical_input={"routing": {"processing_lane": "guided"}},
            question="Which host should I scope this investigation to?",
            unresolved_fields=["host"],
            handoff_id="handoff:test",
            handoff_version=1,
            reason="missing_host",
        )
    elif status == "policy_blocked":
        outcome = policy_blocked_outcome(
            canonical_input={"routing": {"processing_lane": "guided"}},
            policy_reason="unsafe_action_blocked",
        )
    else:
        outcome = failure_outcome(
            status,  # type: ignore[arg-type]
            category=status,
            reason=f"test_{status}",
            canonical_input={"routing": {"processing_lane": "guided"}},
        )
    return {"canonical_planning_outcome": outcome.model_dump()}


def test_run_live_chat_pipeline_calls_run_canonical_planning() -> None:
    from app.chat.pipeline import _run_live_chat_pipeline

    assert _function_has_call(_run_live_chat_pipeline, "run_canonical_planning")
    _assert_no_forbidden_direct_planning(
        _run_live_chat_pipeline,
        entrypoint="_run_live_chat_pipeline",
        forbidden=_IMPERATIVE_ENTRY_FORBIDDEN,
    )


def test_rp_node_bootstrap_calls_run_canonical_planning() -> None:
    assert _function_has_call(rp_node_bootstrap, "run_canonical_planning")
    _assert_no_forbidden_direct_planning(rp_node_bootstrap, entrypoint="rp_node_bootstrap")


def test_shadow_planning_calls_run_canonical_planning_not_legacy_evidence() -> None:
    from app.graph.planner_led_shadow_graph import shadow_node_planning

    calls = _function_call_names(shadow_node_planning)
    assert "run_canonical_planning" in calls
    assert "graph_node_evidence_planning" not in calls


def _bad_entrypoint_duplicate_fork(state: dict[str, Any]) -> dict[str, Any]:
    return graph_node_lane_and_canonical_planning(state)  # noqa: F821


def test_negative_control_detector_catches_duplicate_planning_fork() -> None:
    """Evidence: guard logic rejects a reintroduced direct planning fork."""
    calls = _function_call_names(_bad_entrypoint_duplicate_fork)
    assert "graph_node_lane_and_canonical_planning" in calls
    assert calls & _FORBIDDEN_DIRECT_PLANNING_CALLS


@pytest.mark.parametrize(
    "status",
    [
        "clarification_required",
        "policy_blocked",
        "planning_failed",
        "resolution_failed",
        "persistence_failed",
    ],
)
def test_non_planned_canonical_status_routes_to_finalize_short_circuit(status: str) -> None:
    route = _rp_dispatch_route(_state_with_outcome(status))
    assert route == "non_planned_finalize"


def test_non_planned_finalize_skips_spl_and_execution_edges() -> None:
    edges = resource_planner_graph_edges()
    assert ("non_planned_finalize", "finalize") in edges
    for target in _SPL_EXECUTION_NODES:
        assert ("non_planned_finalize", target) not in edges


def test_planned_status_may_still_reach_workflow_or_composed_dispatch() -> None:
    state = {
        "canonical_planning_outcome": {
            "status": "planned",
            "canonical_input": {"routing": {}},
            "evidence_plan": {"answer_mode": "hybrid", "resource_plan": {"provenance": {"committed": True}}},
            "resource_plan": {"provenance": {"committed": True}},
        },
        "evidence_plan": {"answer_mode": "hybrid", "resource_plan": {"steps": []}},
    }
    route = _rp_dispatch_route(state)
    assert route in {"workflow_spl", "composed_dispatch", "rag_only"}


def test_module_paths_exist() -> None:
    repo = Path(__file__).resolve().parents[2]
    assert (repo / "app" / "chat" / "canonical_planning_orchestrator.py").is_file()
    assert (repo / "app" / "graph" / "resource_planner_graph.py").is_file()
