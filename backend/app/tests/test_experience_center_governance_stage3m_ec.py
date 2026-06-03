"""Stage 3M-EC: Experience Center governance panels (demo trace metadata only)."""

from __future__ import annotations

import json

from app.api.routes_scenarios import run_demo_scenario_fixture


def _run(scenario_id: str):
    return run_demo_scenario_fixture(scenario_id)


def _visible_answer(response) -> str:
    payload = {
        "message": response.message,
        "analyst_summary": response.analyst_summary,
        "analyst_response": response.analyst_response.model_dump() if response.analyst_response else None,
    }
    return json.dumps(payload)


def test_failed_login_governance_panels_and_answer_unchanged() -> None:
    response = _run("failed_login_spike_app01")
    visible = _visible_answer(response)
    gov = response.governance_trace or response.experience_center_governance

    assert response.analyst_response is not None
    assert response.analyst_response.severity_label == "P2 High"
    assert "confirmed account compromise" not in visible.lower()
    assert "account compromise not confirmed" in json.dumps(gov.severity.model_dump())
    assert "T1110.001" in visible
    assert "Supported" in visible

    assert gov is not None
    assert gov.mcp_envelope is not None
    assert gov.mcp_envelope.available is True
    assert gov.mcp_envelope.origin == "fixture"
    assert gov.mcp_envelope.schema_confirmed is False
    assert gov.mcp_envelope.schema_confirmed_reason == "fixture_adapter"
    assert gov.mcp_envelope.executed_spl is None

    assert gov.severity is not None
    assert gov.severity.why_severity_title == "Why P2 High?"
    assert "high failed-login volume" in gov.severity.why_severity
    assert "multiple source IPs" in gov.severity.why_severity
    assert "no confirmed successful login after failures" in gov.severity.why_not_higher
    assert gov.severity.priority_note is not None
    assert "Action priority is not the same as incident severity" in gov.severity.priority_note

    assert gov.skills_operations.intent_skill == "attack_discovery"
    assert gov.skills_operations.legacy_router_skill == "attack_discovery"
    assert gov.skills_operations.runtime_operation is None
    assert "not evaluated in demo fixture" in gov.skills_operations.runtime_operation_note

    stage_ids = {stage.stage_id for stage in gov.skills_operations.pipeline_stages}
    assert stage_ids == {
        "query_understanding",
        "workflow_planning",
        "spl_template",
        "spl_validation",
        "mcp_execution_gate",
        "source_evidence",
        "mitre_mapping",
        "severity_decision",
        "context_sufficiency",
        "action_capability",
        "llm_synthesis_planned",
        "answer_guard_planned",
    }

    assert "live MCP/Splunk execution" in gov.completion_status.gated_wip
    assert "legacy intent routing" in gov.completion_status.completed


def test_demo_route_plan_shadow_and_skill_unchanged() -> None:
    response = _run("failed_login_spike_app01")
    assert response.selected_skill == "attack_discovery"
    assert response.route_plan_shadow is None


def test_experience_center_control_plane_trace_uses_captured_hf_and_known_mcp_basis() -> None:
    response = _run("new_source_ip_logins")

    assert response.query_to_intent is not None
    assert response.evidence_plan is not None
    assert response.route_adjudication is not None
    assert response.llm_plan_validation is not None
    assert response.mitre_decision is not None
    assert response.control_plane_trace is not None
    assert response.response_mode is not None
    assert response.synthesis_mode == "captured_huggingface_governed_output"
    assert response.route_adjudication["llm_suggested_route"] is None

    provenance = response.control_plane_trace["experience_center_provenance"]
    assert provenance["llm_output_basis"] == "captured_huggingface_foundation_sec_output"
    assert provenance["mcp_output_basis"] == "assumed_happy_path_fixture_from_known_mcp_tools"
    assert provenance["live_llm_called"] is False
    assert provenance["live_mcp_called"] is False
    assert provenance["future_state_preview"] is False
    assert provenance["hallucinated_mcp_output"] is False

    serialized = json.dumps(response.control_plane_trace).lower()
    assert "future-state preview" not in serialized
    assert "future state preview" not in serialized

    mcp_trace = response.control_plane_trace["mcp_execution"]
    assert mcp_trace["status"] == "fixture_evidence_packaged"
    assert mcp_trace["execution_intent"] == "known_mcp_happy_path_fixture"
    assert mcp_trace["tool_selection_status"] == "fixture_evidence_packaged"
    assert mcp_trace["selected_mcp_server"] == "splunk"


def test_all_demo_scenarios_expose_governance_metadata() -> None:
    from app.api.routes_scenarios import list_demo_scenario_fixtures

    for item in list_demo_scenario_fixtures()["scenarios"]:
        response = _run(item["scenario_id"])
        assert response.governance_trace is not None
        assert response.experience_center_governance is not None
        assert response.control_plane_trace is not None
        assert response.governance_trace.skills_operations.intent_skill == response.selected_skill
        assert response.governance_trace.completion_status.completed
        assert response.governance_trace.completion_status.gated_wip


def test_lockout_demo_envelope_when_mock_execution_path() -> None:
    response = _run("account_lockouts_over_time_spl")
    gov = response.governance_trace or response.experience_center_governance
    assert gov is not None
    assert gov.mcp_envelope is not None
    assert gov.mcp_envelope.available is True
    assert gov.mcp_envelope.origin == "fixture"
