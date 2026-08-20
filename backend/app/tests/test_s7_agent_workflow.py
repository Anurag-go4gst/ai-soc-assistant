"""S7 conflicting OT evidence agent workflow — EC fixture only, not production /chat."""

from __future__ import annotations

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_agent.registry import get_agent_profile, has_agent_profile
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s7.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S7_SCENARIO_ID
from app.demo.fixtures.s7.pack import S7_QUERY


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def _inv_ids() -> list[str]:
    return [step["id"] for step in INVESTIGATION_STEP_DEFS if step.get("default_selected", True)]


def _rem_ids() -> list[str]:
    return [step["id"] for step in REMEDIATION_STEP_DEFS]


def test_s7_agent_profile_is_registered() -> None:
    assert has_agent_profile(S7_SCENARIO_ID)
    profile = get_agent_profile(S7_SCENARIO_ID)
    assert profile is not None
    assert profile.scenario_id == S7_SCENARIO_ID


def test_s7_agent_plan_ready_on_initial_turn() -> None:
    envelope = run_experience_center_turn(S7_SCENARIO_ID, session_id="s7-agent-plan").model_dump()
    workflow = envelope["ec_agent_workflow"]
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert workflow["investigation_plan"]["editable"] is True
    assert len(workflow["investigation_plan"]["steps"]) >= 6
    assert workflow.get("investigation_results") is None
    narrative = (workflow.get("opening_narrative") or "").lower()
    assert "splunk and mcp tools and rag guidelines" in narrative
    assert "retired" in narrative
    assert "ot" in narrative
    assert "physical inspection" not in narrative
    assert "interview relevant personnel" not in narrative
    assert S7_QUERY.split()[0]
    assert envelope["ec_investigation_outcome"]["forced_incident"] is False
    assert envelope["ec_investigation_outcome"]["disposition"] == "unresolved_conflict"
    assert envelope["production_side_effect"] is False
    assert envelope["ec_provenance"]["live_llm_called"] is False
    assert envelope["ec_provenance"]["live_mcp_called"] is False


def test_s7_investigation_tools_do_not_invent_cmdb_mcp() -> None:
    investigation_tools = {tool for step in INVESTIGATION_STEP_DEFS for tool in (step.get("tools") or [])}
    assert "Splunk MCP" in investigation_tools
    assert "CMDB MCP" not in investigation_tools
    assert any("simulated" in tool.lower() for tool in investigation_tools)
    rem_blob = " ".join(tool for step in REMEDIATION_STEP_DEFS for tool in (step.get("tools") or [])).lower()
    assert "mcp" not in rem_blob


def test_s7_run_investigation_path_a_does_not_force_incident() -> None:
    session_id = "s7-agent-inv"
    run_experience_center_turn(S7_SCENARIO_ID, session_id=session_id)
    after = run_experience_center_turn(
        S7_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    ).model_dump()
    assert after["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    workflow = after["ec_agent_workflow"]
    assert workflow["hil_prompt"] is None
    assert workflow.get("next_step_cta")
    conclusion = (workflow.get("investigation_conclusion") or {}).get("headline", "").lower()
    assert "active" in conclusion
    assert "stale" in conclusion or "cmdb" in conclusion
    assert "false alarm" in conclusion or "real concern" in conclusion
    results = {step["id"]: step for step in workflow["investigation_results"]["steps"]}
    assert results["replay_splunk"]["status"] == "COMPLETE"
    assert results["ot_inventory"]["status"] == "COMPLETE"
    inventory = results["ot_inventory"]["finding"]["headline_finding"].lower()
    assert "active" in inventory
    assert after["ec_investigation_outcome"]["forced_incident"] is False
    assert after["ec_path"] == "A"
    kinds = {item["kind"] for item in after["ec_actions"]}
    assert "ticket_create" not in kinds
    applied = after["ec_session_state"]["applied_follow_up_ids"]
    assert "check_ot_inventory" in applied
    assert "confirm_stale_identity" not in applied
    blob = " ".join([workflow.get("opening_narrative") or "", conclusion, inventory]).lower()
    assert "physical inspection" not in blob
    assert "interview relevant personnel" not in blob
    assert "interview the it and ot teams" not in blob


def test_s7_full_agent_lifecycle_to_complete() -> None:
    session_id = "s7-agent-full"
    run_experience_center_turn(S7_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S7_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    )
    ready = run_experience_center_turn(
        S7_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_remediation_plan",
    ).model_dump()
    assert ready["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert ready["ec_agent_workflow"]["remediation_plan"]["visible"] is True

    final = run_experience_center_turn(
        S7_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_remediation",
        agent_payload={"selected_step_ids": _rem_ids()},
    ).model_dump()
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"] is not None
    headline = final["ec_agent_workflow"]["final_summary"]["headline"].lower()
    assert "active" in headline or "stale" in headline or "incident" in headline
    assert final["ec_path"] == "A"
    kinds = {item["kind"]: item["state"] for item in final["ec_actions"]}
    assert kinds.get("ticket_create") == "EXECUTED"
    assert "email_send" in kinds
    assert final["production_side_effect"] is False
    assert final["ec_provenance"]["live_mcp_called"] is False
    closure = str(final["ec_investigation_outcome"].get("closure_summary") or "").lower()
    assert "path a" in closure or "active" in closure or "stale" in closure
