"""S2 prompt-injection agent workflow — EC fixture only, not production /chat."""

from __future__ import annotations

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_agent.registry import get_agent_profile, has_agent_profile
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s2.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S2_SCENARIO_ID
from app.demo.fixtures.s2.pack import S2_QUERY


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def _inv_ids() -> list[str]:
    return [step["id"] for step in INVESTIGATION_STEP_DEFS]


def _rem_ids() -> list[str]:
    return [step["id"] for step in REMEDIATION_STEP_DEFS]


def test_s2_agent_profile_is_registered() -> None:
    assert has_agent_profile(S2_SCENARIO_ID)
    profile = get_agent_profile(S2_SCENARIO_ID)
    assert profile is not None
    assert profile.scenario_id == S2_SCENARIO_ID


def test_s2_agent_plan_ready_on_initial_turn() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-agent-plan").model_dump()
    workflow = envelope["ec_agent_workflow"]
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert workflow["investigation_plan"]["editable"] is True
    assert len(workflow["investigation_plan"]["steps"]) >= 8
    assert workflow.get("investigation_results") is None
    narrative = (workflow.get("opening_narrative") or "").lower()
    assert "splunk and mcp tools and rag guidelines" in narrative
    assert "customer-facing ai assistant" in narrative
    assert "collecting and analyzing logs" in narrative
    assert "index=your_ai_logs" not in narrative
    assert S2_QUERY.split()[0]  # scenario query still registered
    assert envelope["production_side_effect"] is False
    assert envelope["ec_provenance"]["live_llm_called"] is False
    assert envelope["ec_provenance"]["live_mcp_called"] is False


def test_s2_investigation_tools_are_only_onboarded_connectors() -> None:
    """Investigation may name Splunk MCP + SOC-KB only. No invented IAM/DLP/CMDB MCP."""
    investigation_tools = {tool for step in INVESTIGATION_STEP_DEFS for tool in (step.get("tools") or [])}
    assert investigation_tools == {"Splunk MCP", "SOC-KB"}
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-tool-labels").model_dump()
    plan_tools = {
        tool
        for step in envelope["ec_agent_workflow"]["investigation_plan"]["steps"]
        for tool in (step.get("tools") or [])
    }
    assert plan_tools == {"Splunk MCP", "SOC-KB"}
    rem_blob = " ".join(tool for step in REMEDIATION_STEP_DEFS for tool in (step.get("tools") or [])).lower()
    assert "mcp" not in rem_blob


def test_s2_run_investigation_answers_three_questions_without_hil() -> None:
    session_id = "s2-agent-inv"
    run_experience_center_turn(S2_SCENARIO_ID, session_id=session_id)
    after = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    ).model_dump()
    assert after["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    workflow = after["ec_agent_workflow"]
    assert workflow["hil_prompt"] is None
    assert workflow.get("next_step_cta")
    conclusion = (workflow.get("investigation_conclusion") or {}).get("headline", "").lower()
    assert "prompt injection" in conclusion
    assert "blocked" in conclusion
    assert "not confirmed" in conclusion
    results = {step["id"]: step for step in workflow["investigation_results"]["steps"]}
    assert results["replay_detection"]["status"] == "COMPLETE"
    assert "3" in (results["replay_detection"].get("finding") or {}).get("headline_finding", "")
    tool = results["tool_authorization"]["finding"]["headline_finding"].lower()
    assert "export_customer_records" in tool
    assert "denied" in tool or "blocked" in tool or "not executed" in tool
    data = results["data_source_audit"]["finding"]["headline_finding"].lower()
    assert "not confirmed" in data or "no unauthorized" in data
    applied = after["ec_session_state"]["applied_follow_up_ids"]
    assert "check_dlp" in applied
    assert "review_existing_detection" in applied
    blob = " ".join(
        [
            workflow.get("opening_narrative") or "",
            conclusion,
            tool,
        ]
    ).lower()
    assert "index=your_ai_logs" not in blob
    assert "machine learning toolkit" not in blob


def test_s2_full_agent_lifecycle_to_complete() -> None:
    session_id = "s2-agent-full"
    run_experience_center_turn(S2_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    )
    ready = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_remediation_plan",
    ).model_dump()
    assert ready["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert ready["ec_agent_workflow"]["remediation_plan"]["visible"] is True

    final = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_remediation",
        agent_payload={"selected_step_ids": _rem_ids()},
    ).model_dump()
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"] is not None
    headline = final["ec_agent_workflow"]["final_summary"]["headline"].lower()
    assert "blocked" in headline
    assert "not confirmed" in headline or "breach" in headline
    outcome = final["ec_investigation_outcome"]
    assert "not confirmed" in str(outcome.get("closure_summary") or "").lower()
    kinds = {item["kind"]: item["state"] for item in final["ec_actions"]}
    assert kinds.get("iam_disable") in {"EXECUTED", "VERIFIED"}
    assert kinds.get("ticket_create") == "EXECUTED"
    assert "email_send" in kinds
    assert final["production_side_effect"] is False
    assert final["ec_provenance"]["live_mcp_called"] is False
    assert (final.get("spl_validation") or {}).get("execution_eligible") is False
