from __future__ import annotations

import json
from typing import Any

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _offline_chat_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(
        "app.config.settings.database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )


def test_chat_clear_command_short_circuits_routing(monkeypatch) -> None:
    called: list[bool] = []

    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        called.append(True)
        return {
            "skill": "attack_discovery",
            "tool_plan": ["route_only"],
            "confidence": 0.5,
            "comparison": {"match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)

    response = chat(ChatRequest(message="/clear"))

    assert called == []
    assert response.note == "client_command:/clear"
    assert response.message == "Chat cleared. Ask your next question when ready."


def test_chat_query_endpoint_calls_route_skill(monkeypatch) -> None:
    calls: list[dict[str, str]] = []
    telemetry = FakeTelemetry()

    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"query": query, "trace_id": trace_id})
        return {
            "skill": "attack_discovery",
            "tool_plan": ["route_only", "attack_discovery"],
            "confidence": 0.91,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)

    query = (
        "Investigate alert ALT-2024-0891 for 148 failed login attempts for user alice "
        "from src 10.0.0.8 against host dc1 in the last hour and generate governed SPL for review."
    )
    response = chat(ChatRequest(message=query))

    assert calls == [{"query": query, "trace_id": response.trace_id}]
    assert response.user_query == query
    assert response.selected_skill == "attack_discovery"
    assert response.tool_plan == ["route_only", "attack_discovery"]
    assert response.confidence == 0.91
    assert response.disagreement is False
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
    assert response.workflow_plan is not None
    assert response.workflow_plan.status == "not_started"
    assert response.workflow_plan.execution_enabled is False
    assert response.candidate_spl is not None
    assert "index=pgcil_soc" in response.candidate_spl.candidate_spl
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert telemetry.steps[0]["step_name"] == "candidate_spl_generated"
    assert telemetry.spl_validations[0]["approved"] is True
    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.execution.status in {"requires_human_review", "skipped"}
    assert response.execution.execution_status_label in {"not_executed", "review_required", None}


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
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.disagreement is True
    assert response.disagreement_reason == "skill_mismatch"
    assert telemetry.disagreements
    assert telemetry.disagreements[0]["trace_id"] == response.trace_id
    assert telemetry.disagreements[0]["selected"]["skill"] == "attack_discovery"


def test_chat_generates_and_validates_spl_without_mcp_or_splunk_write(monkeypatch) -> None:
    telemetry = FakeTelemetry()

    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "skill": "spl_generation",
            "tool_plan": ["route_only", "spl_generation"],
            "confidence": 0.80,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)
    response = chat(
        ChatRequest(
            message=(
                "Create governed SPL for failed login spike: user alice, source 10.0.0.8, "
                "host dc1, fail_count 148, last hour."
            )
        )
    )

    assert response.selected_skill == "spl_generation"
    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True
    assert "No MCP execution" in response.note
    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert response.execution.execution_status_label in {"not_executed", "review_required", None}
    assert not hasattr(telemetry, "splunk_write")
    # Governance notes may mention gated Splunk execution; the user-facing message must not imply execution.
    payload = response.model_dump()
    assert "Splunk" not in (payload.get("message") or "")


def test_chat_response_does_not_expose_secrets(monkeypatch) -> None:
    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "skill": "knowledge_recall",
            "tool_plan": ["needs_clarification"],
            "confidence": 0.40,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        }

    monkeypatch.setattr("app.api.routes_chat.route_skill", fake_route_skill)
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: FakeTelemetry())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    text = json.dumps(chat(ChatRequest(message="test")).model_dump()).lower()

    for forbidden in ("password", "secret", "token", "credential", "raw_prompt"):
        assert forbidden not in text


class FakeTelemetry:
    def __init__(self) -> None:
        self.decisions: list[dict[str, Any]] = []
        self.disagreements: list[dict[str, Any]] = []
        self.steps: list[dict[str, Any]] = []
        self.spl_validations: list[dict[str, Any]] = []
        self.mcp_executions: list[dict[str, Any]] = []

    def record_routing_decision(self, trace_id: str, **fields: Any) -> None:
        self.decisions.append({"trace_id": trace_id, **fields})

    def record_routing_disagreement(self, trace_id: str, **fields: Any) -> None:
        self.disagreements.append({"trace_id": trace_id, **fields})

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})

    def record_spl_validation(self, trace_id: str, **fields: Any) -> None:
        self.spl_validations.append({"trace_id": trace_id, **fields})

    def record_mcp_execution(self, trace_id: str, **fields: Any) -> None:
        self.mcp_executions.append({"trace_id": trace_id, **fields})


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
