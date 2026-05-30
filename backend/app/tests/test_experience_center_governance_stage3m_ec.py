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
    gov = response.experience_center_governance

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


def test_all_demo_scenarios_expose_governance_metadata() -> None:
    from app.api.routes_scenarios import list_demo_scenario_fixtures

    for item in list_demo_scenario_fixtures()["scenarios"]:
        response = _run(item["scenario_id"])
        assert response.experience_center_governance is not None
        assert response.experience_center_governance.skills_operations.intent_skill == response.selected_skill
        assert response.experience_center_governance.completion_status.completed
        assert response.experience_center_governance.completion_status.gated_wip


def test_lockout_demo_envelope_when_mock_execution_path() -> None:
    response = _run("account_lockouts_over_time_spl")
    gov = response.experience_center_governance
    assert gov is not None
    assert gov.mcp_envelope is not None
    assert gov.mcp_envelope.available is True
    assert gov.mcp_envelope.origin == "fixture"
