"""Item 13 — `/chat` route wiring to RP hierarchy when orchestration flag is on."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.evals.sentinel_eval import BASELINE_PATH, load_sentinel_rows, sentinel_runtime
from app.graph.resource_planner_graph import (
    GOVERNANCE_NODE_NAMES,
    _rp_graph_invoke_scope,
    guard_rp_imperative_fallback,
    rp_graph_invoke_active,
    run_chat_via_resource_planner_graph,
    run_resource_planner_graph,
)
from app.auth.session import require_auth
from app.main import app
from app.schemas.requests import ChatRequest
from fastapi.testclient import TestClient

REF_QUERY = "What is AML.T0043?"
_RP_DEFECT_MARKER = "RP_UNHANDLED_DEFECT_should_not_surface"
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
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", lambda **kwargs: {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "atlas-aml-t0043", "title": "AML.T0043"}],
        "required_sources": kwargs.get("required_sources") or [],
    })


def test_routes_chat_uses_resource_planner_graph_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_chat_mocks(monkeypatch)
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)

    response = chat(ChatRequest(message=REF_QUERY))

    assert response.selected_skill == "knowledge_recall"
    note = (response.note or "").lower()
    assert "resource_planner_hierarchy" in note
    assert "parity mode" not in note
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


def _sentinel_baseline_rows() -> dict[str, dict[str, Any]]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["rows"]


@pytest.mark.parametrize("row", load_sentinel_rows()[:3], ids=lambda row: row["key"])
def test_resource_planner_graph_sentinel_core_fields(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, Any],
) -> None:
    """Item 12b batch-1: RP graph regression against frozen sentinel baseline (no linear LangGraph oracle)."""
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    message = row["question"]
    expected = _sentinel_baseline_rows()[row["key"]]
    with sentinel_runtime():
        rp = run_chat_via_resource_planner_graph(ChatRequest(message=message))

    assert rp.selected_skill == expected["selected_skill"]
    assert rp.execution is not None
    assert rp.execution.status == expected["execution_status"]


def test_rp_none_response_uses_degraded_facade_without_imperative_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imperative_calls: list[str] = []

    def _imperative_must_not_run(*args: object, **kwargs: object) -> object:
        imperative_calls.append("called")
        raise AssertionError("legacy imperative pipeline must not run on RP response=None")

    monkeypatch.setattr(
        "app.chat.pipeline._run_live_chat_pipeline",
        _imperative_must_not_run,
    )
    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_resource_planner_graph",
        lambda *args, **kwargs: {"response": None, "trace_id": "trace-rp-none"},
    )

    response = run_chat_via_resource_planner_graph(ChatRequest(message=REF_QUERY))

    assert imperative_calls == []
    assert response.planning_decision.get("path_type") == "rp_degraded_facade"
    assert response.execution is None
    assert response.candidate_spl is None
    assert "degraded facade" in (response.note or "").lower()


def test_rp_fallback_entrypoint_returns_degraded_facade_without_imperative_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("legacy imperative pipeline must not run for rp_fallback entrypoint")

    monkeypatch.setattr("app.chat.pipeline._run_live_chat_pipeline", _boom)
    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_chat_via_resource_planner_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("RP graph must not run during rp_fallback facade")
        ),
    )

    from app.chat.pipeline import build_live_chat_response

    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=REF_QUERY), entrypoint="rp_fallback")

    assert response.planning_decision.get("path_type") == "rp_degraded_facade"
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


def test_rp_default_unhandled_exception_fails_loud_without_imperative_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exception policy (item 11): RP defects fail loud; no imperative catch-and-fallback."""

    imperative_calls: list[str] = []

    def _imperative_must_not_run(*args: object, **kwargs: object) -> object:
        imperative_calls.append("called")
        raise AssertionError("imperative fallback must not run on RP exception")

    def _rp_graph_defect(*args: object, **kwargs: object) -> object:
        raise RuntimeError(_RP_DEFECT_MARKER)

    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.build_live_chat_response", _imperative_must_not_run)
    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_resource_planner_graph",
        _rp_graph_defect,
    )

    app.dependency_overrides[require_auth] = lambda: {"username": "analyst", "role": "demo_analyst"}
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/chat", json={"message": REF_QUERY})
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 500
    body = response.json()
    assert body.get("trace_id")
    assert body.get("error_code") == "internal_error"
    assert _RP_DEFECT_MARKER not in response.text
    assert imperative_calls == []
