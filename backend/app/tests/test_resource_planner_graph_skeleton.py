"""Resource Planner LangGraph skeleton — topology and governance node coverage."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.graph.resource_planner_graph import (
    GOVERNANCE_NODE_NAMES,
    _compiled_resource_planner_graph,
    resource_planner_governance_inbound_targets,
    resource_planner_graph_node_names,
    run_resource_planner_graph,
)
from app.schemas.requests import ChatRequest


def _fake_retrieve(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "sop-failed-login", "title": "Failed Login SOP"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


def test_resource_planner_graph_compiles() -> None:
    graph = _compiled_resource_planner_graph()
    assert graph is not None


def test_resource_planner_graph_exposes_governance_nodes() -> None:
    nodes = resource_planner_graph_node_names()
    for name in GOVERNANCE_NODE_NAMES:
        assert name in nodes, name
    assert "resource_planner_merge" in nodes
    assert "specialist_skill" in nodes


def test_resource_planner_governance_nodes_are_reachable() -> None:
    inbound = resource_planner_governance_inbound_targets()
    for name in GOVERNANCE_NODE_NAMES:
        assert inbound[name], f"{name} has no inbound edges"
    assert inbound["validate_final_answer"] == {"finalize"}
    assert inbound["finalize"] == {"policy_veto"}


def test_resource_planner_validate_final_answer_node_invokes_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> Any:
        calls.append(kwargs)
        from app.chat.final_answer_validator import validate_final_answer as real_validate

        return real_validate(**kwargs)

    monkeypatch.setattr("app.graph.resource_planner_graph.validate_final_answer", _capture)
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)

    run_resource_planner_graph(ChatRequest(message="What is AML.T0043?"))

    assert calls, "validate_final_answer must run as a wired graph node"


def test_resource_planner_graph_invoke_visits_governance_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)

    state = run_resource_planner_graph(ChatRequest(message="What is AML.T0043?"))
    visited = state.get("rp_graph_trace", {}).get("visited_nodes") or []
    assert visited[0] == "bootstrap"
    assert "resource_planner_merge" in visited
    for node in GOVERNANCE_NODE_NAMES:
        assert node in visited, node
    log = state.get("decision_log") or []
    assert len(log) >= len(visited)
    assert state.get("work_bundle") is not None or state.get("planner_iteration") is not None


def test_resource_planner_graph_requires_no_new_env_flag() -> None:
    assert not hasattr(settings, "ai_soc_resource_planner_graph_enabled")
