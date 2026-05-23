from __future__ import annotations

import json
from typing import Any

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


def test_chat_query_endpoint_calls_route_skill(monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_route_skill(query: str, trace_id: str) -> dict[str, Any]:
        calls.append({"query": query, "trace_id": trace_id})
        return {
            "skill": "attack_discovery",
            "tool_plan": ["route_only", "attack_discovery"],
            "confidence": 0.91,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert calls == [{"query": "Top source IPs by failed login count in the last hour.", "trace_id": response.trace_id}]
    assert response.user_query == "Top source IPs by failed login count in the last hour."
    assert response.selected_skill == "attack_discovery"
    assert response.tool_plan == ["route_only", "attack_discovery"]
    assert response.confidence == 0.91
    assert response.disagreement is False
    assert response.message == "Routing complete. SPL/MCP execution is not enabled yet."
    assert response.workflow_plan is not None
    assert response.workflow_plan.status == "not_started"
    assert response.workflow_plan.execution_enabled is False


def test_chat_response_reports_routing_disagreement(monkeypatch) -> None:
    telemetry = FakeTelemetry()

    def fake_llm_shadow(query: str, llm_connector: Any | None = None) -> dict[str, Any]:
        return {
            "skill": "alert_summary",
            "tool_plan": ["route_only", "alert_summary"],
            "confidence": 0.74,
            "reasons": ["forced disagreement for chat route test"],
        }

    monkeypatch.setattr("app.routing.skill_router.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.routing.skill_router.route_skill_llm_shadow", fake_llm_shadow)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.disagreement is True
    assert response.disagreement_reason == "skill_mismatch"
    assert telemetry.disagreements
    assert telemetry.disagreements[0]["trace_id"] == response.trace_id
    assert telemetry.disagreements[0]["selected"]["skill"] == "attack_discovery"


def test_chat_does_not_attempt_mcp_spl_generation_or_splunk_write(monkeypatch) -> None:
    def fake_route_skill(query: str, trace_id: str) -> dict[str, Any]:
        return {
            "skill": "spl_generation",
            "tool_plan": ["route_only", "spl_generation"],
            "confidence": 0.80,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    response = chat(ChatRequest(message="Create SPL for failed logins."))

    assert response.selected_skill == "spl_generation"
    assert "no SPL generation, MCP execution, RAG retrieval, or synthesis was run" in response.note
    assert "Splunk" not in response.model_dump_json()


def test_chat_response_does_not_expose_secrets(monkeypatch) -> None:
    def fake_route_skill(query: str, trace_id: str) -> dict[str, Any]:
        return {
            "skill": "knowledge_recall",
            "tool_plan": ["needs_clarification"],
            "confidence": 0.40,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    text = json.dumps(chat(ChatRequest(message="test")).model_dump()).lower()

    for forbidden in ("password", "secret", "token", "credential", "raw_prompt"):
        assert forbidden not in text


class FakeTelemetry:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []
        self.disagreements: list[dict[str, Any]] = []

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        self.decisions.append({"trace_id": trace_id, **fields})

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        self.disagreements.append({"trace_id": trace_id, **fields})


def fake_plan_workflow(selected_skill: str, tool_plan: list[str], query: str, trace_id: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "skill": selected_skill,
        "tool_plan": tool_plan,
        "status": "not_started",
        "execution_enabled": False,
        "steps": [
            {
                "order": 1,
                "name": "test workflow plan",
                "status": "not_started",
                "required_connectors": [],
                "safety_gates": ["no_execution"],
            }
        ],
        "required_connectors": [],
        "safety_gates": ["no_execution"],
        "message": "Workflow plan created. No SPL/MCP/RAG execution has started.",
    }
