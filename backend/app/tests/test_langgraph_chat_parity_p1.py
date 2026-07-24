from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.config import settings
from app.schemas.requests import ChatRequest


class FakeTelemetry:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.spl_validations: list[dict[str, Any]] = []

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        self.spl_validations.append({"trace_id": trace_id, **fields})

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": "mcp_execution", **fields})


def _install_chat_mocks(monkeypatch: pytest.MonkeyPatch) -> FakeTelemetry:
    telemetry = FakeTelemetry()

    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "skill": "attack_discovery",
            "tool_plan": ["route_only", "attack_discovery"],
            "confidence": 0.91,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    def fake_plan_workflow(**kwargs: Any) -> dict[str, Any]:
        from app.orchestration.workflow_planner import plan_workflow

        return plan_workflow(**kwargs)

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    return telemetry


def _approved(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("approved")
    return getattr(value, "approved", None)


def test_langgraph_flag_off_uses_imperative_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_chat_mocks(monkeypatch)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.selected_skill == "attack_discovery"
    assert "langgraph" not in (response.note or "").lower()


def test_langgraph_flag_on_matches_imperative_core_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_chat_mocks(monkeypatch)

    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    imperative = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    graph = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert graph.selected_skill == imperative.selected_skill
    assert graph.tool_plan == imperative.tool_plan
    assert graph.confidence == imperative.confidence
    assert graph.disagreement == imperative.disagreement
    assert graph.message == imperative.message
    assert _approved(graph.spl_validation) == _approved(imperative.spl_validation)
    assert graph.execution.status == imperative.execution.status
    assert graph.human_review.reason == imperative.human_review.reason
    graph_note = (graph.note or "").lower()
    assert "resource_planner_hierarchy" in graph_note
    assert "parity mode" not in graph_note


def test_langgraph_graph_compiles() -> None:
    from app.graph.chat_workflow import _compiled_chat_graph

    graph = _compiled_chat_graph()
    assert graph is not None
