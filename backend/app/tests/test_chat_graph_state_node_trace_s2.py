"""S2 — formal ChatPipelineState v2 fields and node_trace schema."""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.chat.node_trace import NodeTraceRecord, validate_node_trace
from app.chat.pipeline_state_v2 import (
    build_execution_decision,
    project_chat_pipeline_state_v2,
    resolve_planning_or_analytic_skill,
)
from app.chat.pipeline_visibility import build_pipeline_node_trace
from app.graph.chat_workflow import run_chat_via_langgraph
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.telemetry_mode", "none")
    monkeypatch.setattr("app.config.settings.ai_soc_telemetry_sink", "none")
    monkeypatch.setattr(
        "app.config.settings.database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )


def test_node_trace_record_schema_requires_core_fields() -> None:
    record = NodeTraceRecord(
        node_name="routing_live_skill_selection",
        input_summary={"query_present": True},
        output_summary={"selected_skill": "attack_discovery"},
        decision_reason="deterministic_routing",
        guardrail_status="passed",
        human_review_required=False,
    )
    assert record.node_name == "routing_live_skill_selection"


def test_validate_node_trace_rejects_empty_node_name() -> None:
    with pytest.raises(Exception):
        NodeTraceRecord.model_validate(
            {
                "node_name": "",
                "input_summary": {},
                "output_summary": {},
                "decision_reason": "x",
                "guardrail_status": "passed",
            }
        )


def test_build_pipeline_node_trace_records_validate() -> None:
    records = build_pipeline_node_trace(
        state={"request": object(), "routed": {"skill": "attack_discovery"}},
        selected_use_case_id="auth_failed_login_spike",
        mitre_decision=None,
        spl_validation=None,
        candidate_spl=None,
        execution={"status": "blocked"},
        human_review={"required": True, "review_type": "spl_review"},
        answer_guard={"enabled": False, "guard_status": "disabled"},
        final_answer_validation={"guard_status": "passed"},
        answer_contract=None,
        severity_decision=None,
    )
    validated = validate_node_trace(records)
    assert validated
    assert {row.node_name for row in validated} >= {
        "routing_live_skill_selection",
        "execution_hil_decision",
        "answer_guard",
        "final_answer_validation",
    }


def test_project_chat_pipeline_state_v2_derives_execution_decision() -> None:
    projection = project_chat_pipeline_state_v2(
        {"routed": {"skill": "attack_discovery"}},
        visibility={"spl_template_status": "active", "mitre_evidence_status": {"T1078": "candidate"}, "node_trace": []},
        final_answer_validation={"guard_status": "passed"},
        execution={"status": "blocked", "block_reason": "mcp_disabled"},
        human_review={"required": True, "review_type": "spl_review"},
        use_case_id=None,
    )
    assert projection["live_execution_skill"] == "attack_discovery"
    assert projection["spl_template_status"] == "active"
    assert projection["execution_decision"]["human_review_required"] is True


def test_resolve_planning_skill_from_route_authority_compare() -> None:
    state = {
        "route_plan_shadow": {
            "route_authority_compare": {"planning_primary_skill": "sequence_match"},
        }
    }
    assert resolve_planning_or_analytic_skill(state) == "sequence_match"


def test_live_chat_response_includes_node_trace_and_v2_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    response = chat(
        ChatRequest(
            message=(
                "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
                "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
                "I can review—but not execute"
            )
        )
    )
    assert response.selected_skill
    assert response.node_trace
    assert response.mitre_evidence_status is not None
    assert response.spl_template_status == "active"


def test_langgraph_wrapper_emits_same_node_trace_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", True)
    imperative = chat(
        ChatRequest(
            message=(
                "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
                "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
                "I can review—but not execute"
            )
        )
    )
    langgraph = run_chat_via_langgraph(
        ChatRequest(
            message=(
                "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
                "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
                "I can review—but not execute"
            )
        )
    )
    imperative_names = {row.get("node_name") for row in (imperative.node_trace or [])}
    langgraph_names = {row.get("node_name") for row in (langgraph.node_trace or [])}
    for expected in (
        "spl_template_status",
        "spl_validation",
        "execution_hil_decision",
        "mitre_evidence_status",
        "answer_guard",
        "final_answer_validation",
    ):
        assert expected in imperative_names
        assert expected in langgraph_names
    assert imperative.selected_skill == langgraph.selected_skill
