"""Experience Center governance panels."""

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
        "llm_narration_visibility",
        "answer_governance",
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


def test_ec_failed_login_resource_planner_selects_splunk_search_tool() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert gov is not None
    assert gov.resource_planner is not None
    assert gov.resource_planner["selected_capability"] == "auth_failed_login_spike"
    assert "MCP tool: mcp:splunk.search" in gov.resource_planner["selected_resources"]
    assert any("selected MCP tool is splunk.search" in item for item in gov.resource_planner["resource_decision"])


def test_ec_mcp_call_is_fixture_not_live_execution() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert gov is not None
    assert gov.mcp_tool_selection is not None
    assert gov.mcp_tool_selection["mcp_server"] == "splunk"
    assert gov.mcp_tool_selection["mcp_tool"] == "search"
    assert gov.mcp_tool_selection["execution_gate"] == "live MCP gate closed"
    assert response.execution is not None
    assert response.execution.status != "executed"
    assert response.execution.executed_spl is None


def test_ec_mcp_result_becomes_source_evidence() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert gov is not None
    assert gov.mcp_fixture_result is not None
    assert gov.mcp_fixture_result["rows_returned"] == 3
    assert gov.mcp_fixture_result["total_failed_login_events"] == 101
    assert gov.source_evidence_panel is not None
    assert gov.source_evidence_panel["evidence_id"] == "ev-splunk-failed-app01"
    assert gov.source_evidence_panel["source_type"] == "splunk_mcp"
    assert gov.source_evidence_panel["collection_status"] == "collected"


def test_ec_final_answer_uses_evidence_contract() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance
    visible = _visible_answer(response)

    assert gov is not None
    assert gov.answer_contract_panel is not None
    assert "APP-01 has 101 failed-login events in the last 60 minutes." in gov.answer_contract_panel["confirmed_facts"]
    assert "compromise" in visible.lower()
    assert "confirmed compromise" not in visible.lower()
    assert "compromise not confirmed" in visible.lower()


def test_ec_model_signal_is_advisory_only() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert gov is not None
    assert gov.model_signal_panel is not None
    assert gov.model_signal_panel["signal"] == "advisory"
    assert any("LLM does not decide MITRE" in item for item in gov.model_signal_panel["statements"])
    assert response.foundation_sec_governance is not None
    assert response.foundation_sec_governance.live_llm_called is False


def test_ec_shows_scorecard_and_narration_after_ws3() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert response.answer_scorecard is not None
    assert response.answer_scorecard["verdict"] == "pass"
    assert "route honored" in response.answer_scorecard["key_checks_passed"]
    assert response.narration_visibility is not None
    assert response.narration_visibility["llm_narration"] == "advisory model signal"
    assert gov is not None
    assert gov.answer_scorecard_panel is not None
    assert gov.narration_visibility_panel is not None


def test_ec_no_old_stage_labels() -> None:
    response = _run("failed_login_spike_app01")
    text = json.dumps(response.model_dump())

    for label in ("Stage 3C", "Stage 3K", "Stage 3L", "Stage 3M", "LLM synthesis planned"):
        assert label not in text


def test_ec_resource_planner_appears_before_mcp_search_result() -> None:
    response = _run("failed_login_spike_app01")
    gov = response.governance_trace or response.experience_center_governance

    assert gov is not None
    assert gov.progress_labels.index("Resource planning") < gov.progress_labels.index("Calling MCP search")


def test_ec_priority_action_labels_are_colon_formatted() -> None:
    response = _run("failed_login_spike_app01")
    assert response.analyst_response is not None

    actions = response.analyst_response.recommended_actions
    assert any(item.startswith("P1: Run") for item in actions)
    assert any(item.startswith("P1: Check") for item in actions)
    assert any(item.startswith("P2: Validate") for item in actions)
    assert any(item.startswith("P3: Document") for item in actions)
    assert not any(item.startswith(("P1Run", "P1Check", "P2Validate", "P3Document")) for item in actions)


def test_ec_no_live_mcp_execution_claim() -> None:
    response = _run("failed_login_spike_app01")
    text = json.dumps(response.model_dump()).lower()

    assert "live splunk search executed" not in text
    assert "connected to splunk" not in text
    assert "live mcp execution" not in _visible_answer(response).lower()
    assert response.execution is not None
    assert response.execution.status != "executed"


def test_ec_no_raw_github_skill_markdown() -> None:
    response = _run("failed_login_spike_app01")
    text = json.dumps(response.model_dump())

    assert "SKILL.md" not in text
    assert "github.com" not in text.lower()
