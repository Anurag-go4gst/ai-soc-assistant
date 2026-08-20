"""S1 governed Splunk investigation — EC fixture pack, not production /chat."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import UnknownFollowUpError, run_experience_center_turn
from app.demo.fixtures.s1.pack import S1_FOLLOWUP_IDS, S1_QUERY, S1_SCENARIO_ID
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.scenarios import list_experience_center_scenarios, run_demo_scenario
from app.main import app
from app.safeguards.spl_validator import validate_spl
from app.schemas.responses import PlaceholderResponse


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s1_listed_in_demo_scenarios() -> None:
    ids = {item["scenario_id"] for item in list_experience_center_scenarios()}
    assert S1_SCENARIO_ID in ids


def test_s1_initial_journey_titles_are_locked() -> None:
    from app.demo.ec_journeys import S1_INITIAL_TITLES

    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-journey")
    assert envelope.ec_execution_journey is not None
    titles = tuple(stage.title for stage in envelope.ec_execution_journey.stages)
    assert titles == S1_INITIAL_TITLES
    blob = " ".join(titles).lower()
    assert "tls handshake" not in blob
    assert "bearer auth" not in blob
    playable = sum(
        stage.duration_ms_hint or 0
        for stage in envelope.ec_execution_journey.stages
        if stage.semantic_type not in {"wait", "hil"}
    )
    assert 8000 <= playable <= 12000
    ids = {item["scenario_id"] for item in list_experience_center_scenarios()}
    assert S1_SCENARIO_ID in ids


def test_s1_run_demo_scenario_still_placeholder_compatible() -> None:
    payload = run_demo_scenario(S1_SCENARIO_ID)
    response = PlaceholderResponse(**payload)
    assert response.demo_mode is True
    assert "index=*" not in str(payload.get("candidate_spl"))
    assert payload["candidate_spl"]["execution_eligible"] is False


def test_s1_initial_query_asks_last_30_days_not_suspicious_ioc() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-c1")
    dumped = envelope.model_dump()
    assert dumped["analyst"]["finding_title"]
    policy = dumped["ec_search_governance_policy"]
    assert policy["user_supplied_time_range"] is True
    assert "last 30 days" in S1_QUERY.lower()
    assert "suspicious" not in S1_QUERY.lower()
    assert dumped["ec_spl_governance"]["time_range_supplied"] is True
    outcome = dumped["ec_investigation_outcome"]
    assert outcome["disposition"] == "needs_monitoring"
    blob = " ".join(outcome["confirmed"]).lower()
    assert "newly observed" in blob
    assert dumped["analyst"]["finding_title"] == (
        f"Newly observed IP {PRIMARY_ATTACKER_IP} — malicious use not confirmed"
    )


def test_s1_search_governance_is_30_plus_30() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-policy")
    policy = envelope.model_dump()["ec_search_governance_policy"]
    assert policy["policy_id"] == "ec_search_governance_policy"
    assert policy["provenance"] == "ec_scenario_policy"
    assert policy["coverage_days"] == 60
    assert policy["split"] == "30+30"
    assert policy["not_production_spl_policy"] is True
    windows = policy["windows"]
    assert len(windows) == 2
    assert windows[0]["days"] == 30
    assert windows[1]["days"] == 30
    assert envelope.ec_projection.phase_contract.provenance.kind == "ec_scenario_policy"
    assert envelope.ec_projection.phase_contract.provenance.detail == "ec_search_governance_policy"


def test_s1_two_searches_pass_real_validate_spl_without_override() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-spl")
    dumped = envelope.model_dump()
    searches = dumped["ec_spl_governance"]["searches"]
    assert len(searches) == 2
    joined = "\n".join(item["candidate_spl"] for item in searches)
    assert "index=*" not in joined
    assert "index=pgcil_soc" in joined
    assert "sourcetype=pgcil:firewall" in joined
    assert dumped["ec_spl_governance"]["validation"]["override"] is False
    assert dumped["ec_spl_governance"]["validation"]["provenance"] == "production_validator_read_only"
    assert dumped["spl_validation"]["approved"] is True
    assert dumped["candidate_spl"]["execution_eligible"] is False
    profile = {
        "allowed_commands": ["search", "stats", "where", "sort", "head"],
        "allowed_indexes": ["pgcil_soc"],
        "allowed_sourcetypes": ["pgcil:firewall"],
    }
    for item in searches:
        live = validate_spl(item["candidate_spl"], template_profile=profile)
        assert live["approved"] is True, live["reject_reasons"]
        assert live["execution_eligible"] is False
        assert item["approved"] is True
        assert item["provenance"] == "production_validator_read_only"


def test_s1_evidence_merged_and_affected_systems() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-merge")
    dumped = envelope.model_dump()
    systems = {row["system"] for row in dumped["ec_affected_systems"]}
    assert systems == {"10.20.1.10", "10.20.4.55", "10.20.8.90"}
    evidence_ids = {item["evidence_id"] for item in dumped["source_evidence"]}
    assert "ev-s1-fw-search-1" in evidence_ids
    assert "ev-s1-fw-search-2" in evidence_ids
    assert dumped["ec_spl_governance"]["evidence_merge"]
    assert dumped["ec_provenance"]["simulated_mcp"] is True
    assert dumped["production_side_effect"] is False


def test_s1_what_we_found_segments_link_saved_search_and_mcp_searches() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-links")
    analyst = envelope.model_dump()["analyst"]
    assert analyst["what_we_found"].startswith("Splunk MCP connected.")
    segments = analyst["what_we_found_segments"]
    assert segments[0]["text"] == "Splunk MCP connected. "
    link_ids = [item["evidence_id"] for item in segments if item["type"] == "evidence_link"]
    assert link_ids == ["ev-s1-existing-search", "ev-s1-fw-search-1", "ev-s1-fw-search-2"]


def test_s1_outcome_confirmed_unconfirmed_missing_no_compromise_claim() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-outcome")
    outcome = envelope.model_dump()["ec_investigation_outcome"]
    assert outcome["disposition"] == "needs_monitoring"
    assert outcome["confirmed"]
    assert outcome["unconfirmed"]
    assert outcome["missing_evidence"]
    assert "account compromise" in " ".join(outcome["unconfirmed"]).lower()
    assert outcome["production_investigation_outcome_unused"] is True
    t1078 = next(item for item in outcome["mitre"] if item["technique_id"] == "T1078")
    assert t1078["status"] == "unconfirmed"
    t1110 = next(item for item in outcome["mitre"] if item["technique_id"] == "T1110.001")
    assert t1110["status"] == "candidate"
    assert "evidence_basis" in t1110


def test_s1_evidence_state_initial_vocabulary() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-state")
    statuses = {item["id"]: item["status"] for item in envelope.model_dump()["ec_evidence_state"]}
    assert statuses["siem_existing_search"] == "OBTAINED"
    assert statuses["splunk_fw_search_1"] == "OBTAINED"
    assert statuses["splunk_fw_search_2"] == "OBTAINED"
    assert statuses["auth_correlation"] == "OBTAINED"
    assert statuses["edr"] == "MISSING"
    assert statuses["iam_detail"] == "MISSING"
    assert statuses["threat_intel"] == "AVAILABLE_NOT_QUERIED"


def test_s1_unknown_follow_up_does_not_invent_scenario() -> None:
    try:
        run_experience_center_turn(
            S1_SCENARIO_ID,
            session_id="s1-unknown",
            follow_up_id="not_a_real_follow_up",
        )
        raise AssertionError("expected UnknownFollowUpError")
    except UnknownFollowUpError:
        pass


def test_s1_every_follow_up_advances_state_and_updates_evidence(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s1-followups"
    first = run_experience_center_turn(S1_SCENARIO_ID, session_id=session_id)
    assert first.ec_session_state.turn == 0
    previous_turn = 0
    for follow_up_id in (
        "check_successful_auth",
        "check_privileged_accounts",
        "check_endpoint_activity",
        "check_threat_intel",
        "compare_previous_incidents",
        "raise_mcp_monitoring",
        "prepare_firewall_block",
        "create_incident_ticket",
    ):
        assert follow_up_id in S1_FOLLOWUP_IDS
        response = client.post(
            f"/demo/scenarios/{S1_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scenario_id"] == S1_SCENARIO_ID
        assert body["ec_session_state"]["turn"] == previous_turn + 1
        previous_turn = body["ec_session_state"]["turn"]
        assert follow_up_id in body["ec_session_state"]["applied_follow_up_ids"]
        assert body["ec_provenance"]["live_llm_called"] is False
        assert body["ec_provenance"]["live_mcp_called"] is False
        assert body["production_side_effect"] is False
        statuses = {item["id"]: item["status"] for item in body["ec_evidence_state"]}
        if follow_up_id == "check_successful_auth":
            assert statuses["successful_auth"] == "OBTAINED"
        if follow_up_id == "check_privileged_accounts":
            assert statuses["privileged_identity"] == "OBTAINED"
        if follow_up_id == "check_endpoint_activity":
            assert statuses["edr"] == "OBTAINED"
            assert "no malicious" in str(body["ec_investigation_outcome"]).lower()
        if follow_up_id == "check_threat_intel":
            assert statuses["threat_intel"] == "OBTAINED"
            assert PRIMARY_ATTACKER_IP in str(body["ec_investigation_outcome"])
        if follow_up_id == "compare_previous_incidents":
            assert statuses["previous_incidents"] == "OBTAINED"
        if follow_up_id == "raise_mcp_monitoring":
            monitor = next(item for item in body["ec_actions"] if item["kind"] == "notify")
            assert monitor["state"] in {"PREPARED", "APPROVAL_REQUIRED"}
            assert monitor["production_side_effect"] is False
            assert "mcp" in str(monitor).lower() or "monitoring" in str(monitor).lower()
        if follow_up_id == "prepare_firewall_block":
            block = next(item for item in body["ec_actions"] if item["kind"] == "firewall_block")
            assert block["state"] in {"PREPARED", "APPROVAL_REQUIRED"}
            assert block["production_side_effect"] is False
        if follow_up_id == "create_incident_ticket":
            ticket = next(item for item in body["ec_actions"] if item["kind"] == "ticket_create")
            assert ticket["state"] in {"PREPARED", "APPROVAL_REQUIRED"}
            assert ticket["production_side_effect"] is False
            assert ticket.get("draft") is not None
            assert ticket["draft"].get("id") == "INC-2026-89412"


def test_s1_follow_up_never_imports_production_actions() -> None:
    import inspect

    from app.demo.fixtures.s1 import pack as s1_pack

    source = inspect.getsource(s1_pack)
    assert "routes_actions" not in source
    assert "evaluate_mcp_execution" not in source
    assert "call_tool" not in source


def test_s1_operational_email_is_hil_draft_not_auto_sent() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-ops-email")
    ids = {chip.follow_up_id for chip in envelope.ec_followups}
    assert "email_firewall_team" not in ids
    assert envelope.ec_agent_lifecycle == "PLAN_READY"

    emailed = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-ops-email",
        follow_up_id="email_firewall_team",
    )
    email = next(item for item in emailed.ec_actions if item.kind == "email_send")
    assert email.state == "APPROVAL_REQUIRED"
    assert email.production_side_effect is False
    dumped = emailed.model_dump()
    assert dumped["ec_email"]["logical_recipient"] == "FIREWALL_TEAM"
    assert dumped["ec_email"]["not_transmitted"] is True
    assert dumped["ec_email"]["status"] == "draft_pending_send"


def test_s1_firewall_is_not_auto_blocked_and_verify_requires_execute() -> None:
    from app.demo import ec_actions

    session_id = "s1-ops-fw"
    run_experience_center_turn(S1_SCENARIO_ID, session_id=session_id)
    prepared_env = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="prepare_firewall_block",
    )
    block = next(item for item in prepared_env.ec_actions if item.kind == "firewall_block")
    assert block.state in {"PREPARED", "APPROVAL_REQUIRED"}
    assert block.production_side_effect is False
    try:
        ec_actions.verify_action(block.action_id)
        raise AssertionError("verify must not succeed before execute")
    except ValueError as exc:
        assert "ec_action_not_verifiable" in str(exc)

    approved = ec_actions.approve_action(block.action_id)
    executed = ec_actions.execute_action(approved.action_id)
    assert executed.state == "EXECUTED"
    verified = ec_actions.verify_action(executed.action_id)
    assert verified.state == "VERIFIED"
    assert verified.verify_result
    assert verified.verify_result.get("indicator") == PRIMARY_ATTACKER_IP
    assert verified.production_side_effect is False


def test_s1_edr_follow_up_uses_stable_follow_up_id_journey() -> None:
    run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-edr-j")
    edr = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-edr-j",
        follow_up_id="check_endpoint_activity",
    )
    assert edr.ec_execution_journey.follow_up_id == "check_endpoint_activity"
    assert edr.ec_execution_journey.header == "Continuing investigation"
    titles = [stage.title for stage in edr.ec_execution_journey.stages]
    assert titles[0] == "Selecting EDR capability"
    assert "Updating InvestigationOutcome" in titles


def test_s1_firewall_action_journey_waits_at_hil() -> None:
    run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-fw-j")
    prepared = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-fw-j",
        follow_up_id="prepare_firewall_block",
    )
    types = [stage.semantic_type for stage in prepared.ec_execution_journey.stages]
    assert "hil" in types
    block = next(item for item in prepared.ec_actions if item.kind == "firewall_block")
    assert block.state in {"PREPARED", "APPROVAL_REQUIRED"}


def test_s1_update_incident_and_closure_summary() -> None:
    session_id = "s1-ops-close"
    run_experience_center_turn(S1_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_incident_ticket",
    )
    updated = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="update_incident",
    )
    ticket_update = next(item for item in updated.ec_actions if item.kind == "ticket_update")
    assert ticket_update.state in {"PREPARED", "APPROVAL_REQUIRED"}
    closed = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="generate_closure_summary",
    )
    outcome = closed.model_dump()["ec_investigation_outcome"]
    assert "closure_summary" in outcome
    assert "unconfirmed" in outcome["closure_summary"].lower() or "not confirmed" in outcome["closure_summary"].lower()
    statuses = {item["id"]: item["status"] for item in closed.ec_evidence_state}
    assert statuses["closure"] == "OBTAINED"


def test_s1_action_follow_ups_are_connector_journeys_not_initial() -> None:
    from app.demo.ec_journeys import S1_INITIAL_TITLES, journey_for

    run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-act-j")
    ticket = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-act-j",
        follow_up_id="create_incident_ticket",
    )
    titles = tuple(stage.title for stage in ticket.ec_execution_journey.stages)
    assert titles != S1_INITIAL_TITLES
    assert len(titles) < len(S1_INITIAL_TITLES)
    assert ticket.ec_execution_journey.kind == "action"
    assert ticket.ec_execution_journey.header == "Connecting to ITSM"
    updated = run_experience_center_turn(
        S1_SCENARIO_ID,
        session_id="s1-act-j",
        follow_up_id="update_incident",
    )
    assert updated.ec_execution_journey.kind == "action"
    assert updated.ec_execution_journey.header == "Connecting to ITSM"
    unknown = journey_for(S1_SCENARIO_ID, ["notify_soc_lead"])
    assert unknown is not None
    assert unknown.kind == "action"
    assert unknown.header == "Connecting to email transport"
    assert tuple(stage.title for stage in unknown.stages) != S1_INITIAL_TITLES
