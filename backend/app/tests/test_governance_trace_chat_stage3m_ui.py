"""Stage 3M-UI: Shared governance_trace on /chat and Experience Center."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.governance.trace_panels import (
    FAILED_LOGIN_SCENARIO_ID,
    MITRE_MAPPING_AUTH_ALERT_SEVERITY_PARITY_GAP,
)
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import assert_governed_spl_review_posture
from app.tests.test_chat_routing import FakeTelemetry, fake_plan_workflow


def _visible_answer(response) -> str:
    return json.dumps(
        {
            "message": response.message,
            "analyst_summary": response.analyst_summary,
            "analyst_response": response.analyst_response.model_dump() if response.analyst_response else None,
        }
    )


def test_failed_login_demo_governance_trace_mirrors_experience_center() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.governance_trace is not None
    assert response.experience_center_governance is not None
    assert response.governance_trace.model_dump() == response.experience_center_governance.model_dump()


def test_failed_login_curated_severity_unchanged_on_governance_trace() -> None:
    response = run_demo_scenario_fixture(FAILED_LOGIN_SCENARIO_ID)
    gov = response.governance_trace
    visible = _visible_answer(response)

    assert response.analyst_response is not None
    assert response.analyst_response.severity_label == "P2 High"
    assert gov is not None
    assert gov.severity is not None
    assert gov.severity.why_severity_title == "Why P2 High?"
    assert "account compromise not confirmed" in gov.severity.why_not_higher
    assert "confirmed account compromise" not in visible.lower()
    assert gov.skills_operations.intent_skill == "attack_discovery"
    assert response.selected_skill == "attack_discovery"
    assert response.route_plan_shadow is None


def test_chat_includes_governance_trace_without_demo_mode(monkeypatch) -> None:
    telemetry = FakeTelemetry()

    def fake_route_skill(query: str, trace_id: str, **kwargs: Any) -> dict:
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

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))

    assert response.demo_mode is False
    assert response.governance_trace is not None
    assert response.governance_trace.skills_operations.intent_skill == response.selected_skill == "attack_discovery"
    assert response.execution is not None
    assert response.execution.executed_spl is None
    assert_governed_spl_review_posture(response)


def test_chat_governance_severity_uses_policy_not_curated_failed_login_bullets(monkeypatch) -> None:
    telemetry = FakeTelemetry()

    monkeypatch.setattr(
        "app.api.routes_chat.route_skill",
        lambda query, trace_id, **kwargs: {
            "skill": "attack_discovery",
            "tool_plan": ["route_only", "attack_discovery"],
            "confidence": 0.91,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        },
    )
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)

    response = chat(ChatRequest(message="Top source IPs by failed login count in the last hour."))
    sev = response.governance_trace.severity if response.governance_trace else None

    assert sev is not None
    assert sev.why_severity_title != "Why P2 High?"
    assert "high failed-login volume" not in sev.why_severity
    assert "APP-01 target" not in sev.why_severity


def test_chat_governance_trace_does_not_change_selected_skill_or_route_plan_shadow(monkeypatch) -> None:
    telemetry = FakeTelemetry()

    monkeypatch.setattr(
        "app.api.routes_chat.route_skill",
        lambda query, trace_id, **kwargs: {
            "skill": "spl_generation",
            "tool_plan": ["route_only", "spl_generation"],
            "confidence": 0.80,
            "comparison": {"match": True, "skill_match": True, "tool_plan_match": True},
        },
    )
    monkeypatch.setattr("app.api.routes_chat.plan_workflow", fake_plan_workflow)
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: telemetry)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: telemetry)

    response = chat(ChatRequest(message="Create SPL for failed logins."))

    assert response.selected_skill == "spl_generation"
    assert response.route_plan_shadow is not None
    assert response.route_plan_shadow.enabled is True
    assert response.governance_trace is not None


@pytest.mark.known_parity_gap(MITRE_MAPPING_AUTH_ALERT_SEVERITY_PARITY_GAP)
def test_mitre_mapping_auth_alert_severity_parity_gap_documented() -> None:
    """Follow-up: align analyst_response.severity_label with severity_decision for this demo."""
    response = run_demo_scenario_fixture("mitre_mapping_auth_alert")
    assert response.analyst_response is not None
    assert response.analyst_response.severity_label == "P2 High"
    assert response.severity_decision is not None
    assert response.severity_decision.severity_label == "P3 Medium"
    assert response.governance_trace is not None
    assert response.governance_trace.severity is not None
    assert response.governance_trace.severity.severity_label == "P3 Medium"
