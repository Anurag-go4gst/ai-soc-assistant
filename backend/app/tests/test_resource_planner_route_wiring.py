"""Item 13 — `/chat` route wiring to RP hierarchy when orchestration flag is on."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.evals.sentinel_eval import load_sentinel_rows, sentinel_runtime
from app.graph.chat_workflow import run_chat_via_langgraph
from app.graph.resource_planner_graph import (
    GOVERNANCE_NODE_NAMES,
    _rp_graph_invoke_scope,
    guard_rp_imperative_fallback,
    rp_graph_invoke_active,
    run_chat_via_resource_planner_graph,
    run_resource_planner_graph,
)
from app.schemas.requests import ChatRequest

REF_QUERY = "What is AML.T0043?"
OT_QUERY = "How should I investigate unusual outbound traffic from an OT host overnight?"


def _install_chat_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "skill": "knowledge_recall",
            "tool_plan": ["route_only", "knowledge_recall"],
            "confidence": 0.95,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr(
        "app.chat.pipeline.retrieve_soc_kb",
        lambda **kwargs: {
            "retrieval_status": "collected",
            "chunks": [{"doc_id": "atlas-aml-t0043", "title": "AML.T0043"}],
            "required_sources": kwargs.get("required_sources") or [],
        },
    )


def _decision_log_nodes(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    records = payload.get("decision_log")
    if not isinstance(records, list):
        return []
    return [str(item.get("node") or "") for item in records if isinstance(item, dict)]


def _enable_cp_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", lambda **kwargs: {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "atlas-aml-t0043", "title": "AML.T0043"}],
        "required_sources": kwargs.get("required_sources") or [],
    })


def test_routes_chat_uses_resource_planner_graph_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_chat_mocks(monkeypatch)
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)

    response = chat(ChatRequest(message=REF_QUERY))

    assert response.selected_skill == "knowledge_recall"
    assert "resource_planner_hierarchy (parity mode)" in (response.note or "").lower()
    state = run_resource_planner_graph(ChatRequest(message=REF_QUERY))
    state_nodes = _decision_log_nodes({"decision_log": state.get("decision_log")})
    trace_nodes = _decision_log_nodes(response.control_plane_trace)
    assert trace_nodes == state_nodes
    for node in GOVERNANCE_NODE_NAMES:
        assert node in trace_nodes, node


def test_policy_veto_blocks_mcp_before_finalize(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = run_chat_via_resource_planner_graph(ChatRequest(message=OT_QUERY))
    evidence = response.evidence_plan or {}
    assert evidence.get("mcp_allowed") is False
    execution = response.execution.model_dump() if hasattr(response.execution, "model_dump") else response.execution
    assert execution.get("status") in {"skipped", "blocked", "requires_human_review"}
    trace_nodes = _decision_log_nodes(response.control_plane_trace)
    assert trace_nodes.index("policy_veto") < trace_nodes.index("finalize")
    assert trace_nodes.index("finalize") < trace_nodes.index("validate_final_answer")


@pytest.mark.parametrize("row", load_sentinel_rows()[:3], ids=lambda row: row["key"])
def test_resource_planner_graph_matches_linear_langgraph_core_fields(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, Any],
) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    message = row["question"]
    with sentinel_runtime():
        linear = run_chat_via_langgraph(ChatRequest(message=message))
        rp = run_chat_via_resource_planner_graph(ChatRequest(message=message))

    assert rp.selected_skill == linear.selected_skill
    assert rp.tool_plan == linear.tool_plan
    assert rp.execution.status == linear.execution.status


def test_rp_fallback_uses_imperative_entrypoint_without_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_build(request: ChatRequest, **kwargs: object) -> object:
        captured["entrypoint"] = str(kwargs.get("entrypoint") or "")
        from app.schemas.responses import PlaceholderResponse

        return PlaceholderResponse(
            trace_id="trace-rp-fallback",
            message="fallback",
            note="imperative fallback",
            user_query=request.message,
        )

    monkeypatch.setattr(
        "app.graph.resource_planner_graph.build_live_chat_response",
        _fake_build,
    )
    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_resource_planner_graph",
        lambda *args, **kwargs: {"response": None},
    )

    run_chat_via_resource_planner_graph(ChatRequest(message=REF_QUERY))

    assert captured.get("entrypoint") == "rp_fallback"


def test_imperative_rp_fallback_entrypoint_does_not_reenter_rp_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(
        "app.chat.pipeline.retrieve_soc_kb",
        lambda **kwargs: {
            "retrieval_status": "collected",
            "chunks": [{"doc_id": "atlas-aml-t0043", "title": "AML.T0043"}],
            "required_sources": kwargs.get("required_sources") or [],
        },
    )

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("RP graph must not run during rp_fallback imperative path")

    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_chat_via_resource_planner_graph",
        _boom,
    )

    from app.chat.pipeline import build_live_chat_response

    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=REF_QUERY), entrypoint="rp_fallback")

    assert response.message


def test_rp_graph_invoke_depth_is_context_local() -> None:
    assert rp_graph_invoke_active() is False
    with _rp_graph_invoke_scope():
        assert rp_graph_invoke_active() is True
    assert rp_graph_invoke_active() is False


def test_guard_rp_imperative_fallback_raises_when_invoke_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    with _rp_graph_invoke_scope():
        with pytest.raises(RuntimeError, match="must not recurse"):
            guard_rp_imperative_fallback("rp_fallback")


def test_guard_rp_imperative_fallback_allows_after_invoke_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    with _rp_graph_invoke_scope():
        pass
    guard_rp_imperative_fallback("rp_fallback")
