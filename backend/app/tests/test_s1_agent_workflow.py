"""S1 newly observed IP agent workflow — EC fixture only, not production /chat."""

from __future__ import annotations

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_agent.registry import get_agent_profile, has_agent_profile
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.fixtures.s1.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S1_SCENARIO_ID
from app.demo.fixtures.s1.pack import S1_QUERY


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def _inv_ids() -> list[str]:
    return [step["id"] for step in INVESTIGATION_STEP_DEFS if step.get("default_selected", True)]


def _rem_ids() -> list[str]:
    return [step["id"] for step in REMEDIATION_STEP_DEFS]


def test_s1_agent_profile_is_registered() -> None:
    assert has_agent_profile(S1_SCENARIO_ID)
    profile = get_agent_profile(S1_SCENARIO_ID)
    assert profile is not None
    assert profile.scenario_id == S1_SCENARIO_ID


def test_s1_agent_plan_ready_on_initial_turn() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-agent-plan").model_dump()
    workflow = envelope["ec_agent_workflow"]
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert envelope["analyst"]["finding_title"] == (
        f"Newly observed IP {PRIMARY_ATTACKER_IP} — malicious use not confirmed"
    )
    assert workflow["investigation_plan"]["editable"] is True
    assert workflow.get("investigation_results") is None
    assert workflow.get("investigation_conclusion") is None
    narrative = (workflow.get("opening_narrative") or "").lower()
    assert "splunk and mcp tools and rag guidelines" in narrative
    assert "suspicious" not in narrative
    assert "last 30 days" in narrative
    assert PRIMARY_ATTACKER_IP in (workflow.get("opening_narrative") or "")
    assert "index=your_" not in narrative
    assert "suspicious" not in S1_QUERY.lower()
    assert envelope["production_side_effect"] is False
    assert envelope["ec_provenance"]["live_llm_called"] is False
    assert envelope["ec_provenance"]["live_mcp_called"] is False


def test_s1_investigation_tools_are_honest() -> None:
    """Default investigation names Splunk MCP + SOC-KB only. No invented firewall-write MCP."""
    default_tools = {
        tool
        for step in INVESTIGATION_STEP_DEFS
        if step.get("default_selected", True)
        for tool in (step.get("tools") or [])
    }
    assert default_tools == {"Splunk MCP", "SOC-KB"}
    rem_blob = " ".join(tool for step in REMEDIATION_STEP_DEFS for tool in (step.get("tools") or [])).lower()
    assert "simulated" not in rem_blob
    assert "splunk mcp" in rem_blob


def test_s1_run_investigation_concludes_new_mcp_not_malicious() -> None:
    session_id = "s1-agent-inv"
    run_experience_center_turn(S1_SCENARIO_ID, session_id=session_id)
    after = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    ).model_dump()
    assert after["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    workflow = after["ec_agent_workflow"]
    assert workflow["hil_prompt"] is None
    offer = workflow.get("remediation_offer") or {}
    assert offer.get("yes_follow_up_id") == "create_remediation_plan"
    assert offer.get("no_follow_up_id") == "decline_remediation_plan"
    assert offer.get("yes_label", "").lower().startswith("yes")
    conclusion = (workflow.get("investigation_conclusion") or {}).get("headline", "").lower()
    assert "permitted" in conclusion or "allowed" in conclusion or "newly observed" in conclusion
    assert "not confirmed" in conclusion
    points = " ".join((workflow.get("investigation_conclusion") or {}).get("narrative_points") or []).lower()
    assert "what happened" in points
    assert "sop" in points
    assert "agent assessment" in points
    assert "not evidence" not in points
    assert "require validation" not in points
    assert "lateral movement" not in points
    assert "3 allowed" in points or "three permitted" in points
    results = {step["id"]: step for step in workflow["investigation_results"]["steps"]}
    result_ids = [step["id"] for step in workflow["investigation_results"]["steps"]]
    assert result_ids[:4] == ["mcp_identity", "requested_30d", "permitted_sessions", "novelty_window"]
    assert result_ids[-2:] == ["evaluate_notable", "retrieve_sop"]
    assert results["evaluate_notable"]["status"] == "COMPLETE"
    assert results["evaluate_notable"]["title"] == "Assess existing Splunk detection coverage"
    notable = (results["evaluate_notable"].get("finding") or {}).get("headline_finding", "").lower()
    assert "no alert" in notable
    assert "ioc" in notable
    assert results["retrieve_sop"]["status"] == "COMPLETE"
    assert results["permitted_sessions"]["added_by_agent"] is True
    reason = (results["permitted_sessions"].get("reason") or "").lower()
    finding = ((results["permitted_sessions"].get("finding") or {}).get("headline_finding") or "").lower()
    assert "jump host" in reason
    assert "remain unexplained" in finding or "authentication is not attributable" in finding
    assert "require validation" not in reason and "require validation" not in finding
    identity = (results["mcp_identity"].get("finding") or {}).get("headline_finding", "").lower()
    assert "mcp" in identity
    novelty = (results["novelty_window"].get("finding") or {}).get("headline_finding", "").lower()
    assert "empty" in novelty or "newly observed" in novelty
    applied = after["ec_session_state"]["applied_follow_up_ids"]
    assert "review_existing_notable" in applied
    assert "check_threat_intel" in applied
    assert "retrieve_sop" in applied
    assert "investigate_permitted_sessions" in applied
    assert "check_successful_auth" in applied
    ti = (results["threat_intel"].get("finding") or {}).get("headline_finding", "").lower()
    assert "not present in local ioc" in ti
    metrics = {
        item["label"]: item["value"]
        for item in (workflow.get("investigation_summary") or {}).get("metrics") or []
    }
    assert metrics.get("Existing IOC detection") == "No alert"
    assert metrics.get("Permitted sessions") == "3 on jump host"
    assert metrics.get("Local TI") == "Unlisted"
    assert metrics.get("Identity") == "Registered MCP endpoint"
    assert metrics.get("Malicious use") == "Not confirmed"
    assert metrics.get("SOP") == "14-day monitoring"
    unresolved = " ".join(workflow.get("unconfirmed") or []).lower()
    assert "expected mcp business traffic" in unresolved
    assert "attributed to this ip" in unresolved
    assert "malicious use is occurring" in unresolved
    assert "lateral movement" not in unresolved
    sources = " ".join(
        f"{item.get('source_type', '')} {item.get('source_name', '')}"
        for item in after.get("source_evidence") or []
    ).lower()
    assert "agilus" not in sources
    assert "splunk" in sources
    headline = (workflow.get("investigation_conclusion") or {}).get("headline", "").lower()
    assert "registered mcp endpoint" in headline
    assert "remain unexplained" in headline
    blob = " ".join([workflow.get("opening_narrative") or "", conclusion, notable]).lower()
    assert "suspicious ip" not in blob
    assert after["ec_provenance"]["live_llm_called"] is False
    assert after["ec_status_summary"].startswith("P2 High")
    assert "malicious use unconfirmed" in after["ec_status_summary"].lower()
    assert workflow.get("executive_summary")
    assert any("MEDIUM" in item for item in workflow["executive_summary"])
    assert all(
        chip.get("follow_up_id") != "generate_executive_summary"
        for chip in after.get("ec_followups") or []
    )
    spl = ((results["requested_30d"].get("finding") or {}).get("details") or {}).get("normalized_spl") or ""
    assert "index=pgcil_soc" in spl
    assert "earliest=-30d" in spl
    assert ((results["requested_30d"].get("finding") or {}).get("details") or {}).get("request")
    assert ((results["requested_30d"].get("finding") or {}).get("details") or {}).get("response")


def test_s1_full_agent_lifecycle_to_complete() -> None:
    session_id = "s1-agent-full"
    run_experience_center_turn(S1_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    )
    ready = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_remediation_plan",
    ).model_dump()
    assert ready["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert ready["ec_agent_workflow"]["remediation_plan"]["visible"] is True
    rem_ids = {step["id"] for step in ready["ec_agent_workflow"]["remediation_plan"]["steps"]}
    rem_titles = " ".join(step["title"] for step in ready["ec_agent_workflow"]["remediation_plan"]["steps"]).lower()
    assert rem_ids == {
        "generate_spl",
        "validate_spl",
        "deploy_monitoring",
        "verify_monitoring",
        "monitor_14d",
        "create_incident",
        "notify_firewall",
        "prepare_block",
        "update_ticket",
    }
    assert "14-day" in rem_titles or "14 day" in rem_titles
    assert "10.20.1.10" in rem_titles
    assert "svc_jump_ops" in rem_titles
    assert "raise_monitoring" not in rem_ids
    assert "monitor_residual" not in rem_ids
    conclusion_points = " ".join(
        (ready["ec_agent_workflow"].get("remediation_conclusion") or {}).get("narrative_points") or []
    ).lower()
    assert "not required" in conclusion_points or "threshold" in conclusion_points
    rem_findings = ready["ec_agent_workflow"]["remediation_results"]["steps"]
    generate = next(step for step in rem_findings if step["id"] == "generate_spl")
    assert "index=pgcil_soc" in (generate["finding"]["details"]["normalized_spl"] or "")
    notify = next(step for step in rem_findings if step["id"] == "notify_firewall")
    assert notify["finding"]["details"]["email_draft"]["subject"]
    incident = next(step for step in rem_findings if step["id"] == "create_incident")
    assert incident["finding"]["details"]["ticket_detail"]["ticket_id"] == "INC-2026-89412"

    inv_only = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-agent-no-rem",
    )
    after_inv = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-agent-no-rem",
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": _inv_ids()},
    ).model_dump()
    declined = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-agent-no-rem",
        follow_up_id="decline_remediation_plan",
    ).model_dump()
    assert declined["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    assert declined["ec_agent_workflow"].get("remediation_plan", {}).get("visible") is not True
    kinds_declined = {item["kind"] for item in declined.get("ec_actions") or []}
    assert "notify" not in kinds_declined
    del inv_only, after_inv

    final = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_remediation",
        agent_payload={"selected_step_ids": _rem_ids()},
    ).model_dump()
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"] is not None
    headline = final["ec_agent_workflow"]["final_summary"]["headline"].lower()
    assert "query executed" in headline or "baseline" in headline
    assert "not confirmed" in headline
    assert final["ec_agent_workflow"]["final_summary"]["title"] == "RESPONSE COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"]["risk_from"] == "MEDIUM"
    assert final["ec_agent_workflow"]["final_summary"]["risk_to"] == "MEDIUM"
    assert final["ec_agent_workflow"].get("executive_summary")
    rem_blob = " ".join(
        str((step.get("finding") or {}).get("headline_finding") or "")
        for step in final["ec_agent_workflow"]["remediation_results"]["steps"]
    ).lower()
    assert "draft" not in rem_blob
    assert "simulated" not in rem_blob
    assert "prepared" not in rem_blob
    statuses = {step["id"]: step["status"] for step in final["ec_agent_workflow"]["remediation_results"]["steps"]}
    assert statuses["monitor_14d"] == "ACTIVE"
    assert statuses["create_incident"] == "CREATED"
    assert statuses["notify_firewall"] == "SENT"
    assert statuses["prepare_block"] == "NOT_REQUIRED"
    assert statuses["deploy_monitoring"] == "EXECUTED"
    kinds = {item["kind"]: item["state"] for item in final["ec_actions"]}
    assert kinds.get("notify") in {"EXECUTED", "VERIFIED"}
    assert kinds.get("ticket_create") == "EXECUTED"
    assert kinds.get("ticket_update") == "EXECUTED"
    assert kinds.get("email_send") == "EXECUTED"
    assert kinds.get("firewall_block") in {"PREPARED", "APPROVAL_REQUIRED"}
    assert final["production_side_effect"] is False
    assert final["ec_provenance"]["live_mcp_called"] is False
    assert (final.get("spl_validation") or {}).get("execution_eligible") is False
