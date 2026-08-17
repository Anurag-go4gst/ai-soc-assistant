"""S3 firewall-team coordination — EC fixture pack, not production /chat."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_actions import execute_action
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s3.pack import S3_SCENARIO_ID, _PROCESS_FIELDS
from app.demo.scenarios import run_demo_scenario
from app.main import app
from app.schemas.responses import PlaceholderResponse


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s3_independent_of_s1_and_placeholder_compatible() -> None:
    payload = run_demo_scenario(S3_SCENARIO_ID)
    assert PlaceholderResponse(**payload).demo_mode is True
    envelope = run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-solo").model_dump()
    prior = envelope["ec_prior_investigation"]
    assert prior["independent_of_s1_session"] is True
    assert prior["siem_evidence_reused"] is True
    assert prior["incident_id"] == envelope["ec_coordination_policy"]["prior_incident_id"]
    assert envelope["ec_coordination_policy"]["spl_generated"] is False
    assert envelope["candidate_spl"] is None
    assert envelope.get("ec_spl_governance") is None
    assert PRIMARY_ATTACKER_IP in envelope["analyst"]["assessment"]
    reuse = envelope["ec_evidence_reuse"]
    assert any(row["status"] == "REUSED" for row in reuse)
    statuses = {item["id"]: item["status"] for item in envelope["ec_evidence_state"]}
    assert statuses["siem_evidence"] == "REUSED"
    assert statuses["spl_search"] == "NOT_REQUIRED"


def test_s3_no_spl_generated_and_evidence_reuse_marked() -> None:
    envelope = run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-reuse").model_dump()
    evidence_ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert evidence_ids[0] == "ev-s3-prior-siem"
    assert envelope["source_evidence"][0]["reused"] is True
    assert "index=" not in str(envelope).lower() or "no new splunk" in envelope["analyst"]["assessment"].lower()
    readiness = envelope["ec_action_readiness"]
    assert any("block immediately" in row["action"].lower() and row["state"] == "NOT_RECOMMENDED_YET" for row in readiness)


def test_s3_whitelist_reply_changes_outcome_and_action_readiness(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s3-reassess"
    before = run_experience_center_turn(S3_SCENARIO_ID, session_id=session_id).model_dump()
    assert before["ec_investigation_outcome"]["disposition"] == "suspicious"
    reply = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "ingest_firewall_reply", "session_id": session_id},
    ).json()
    outcome = reply["ec_investigation_outcome"]
    assert outcome["disposition"] == "needs_reassessment"
    assert outcome["reassessment"]["blind_benign"] is False
    assert outcome["reassessment"]["blind_malicious"] is False
    readiness = reply["ec_action_readiness"]
    assert any("benign" in row["action"].lower() and row["state"] == "NOT_RECOMMENDED_YET" for row in readiness)
    assert any("block immediately" in row["action"].lower() and row["state"] == "NOT_RECOMMENDED_YET" for row in readiness)
    assert reply["ec_coordination_policy"]["team_response_changes_outcome"] is True
    assert reply["ec_execution_journey"]["follow_up_id"] == "ingest_firewall_reply"


def test_s3_email_loop_and_reassessment(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s3-loop"
    run_experience_center_turn(S3_SCENARIO_ID, session_id=session_id)

    process = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "show_firewall_process", "session_id": session_id},
    ).json()
    assert process["ec_workflow_state"] == "Process retrieved"
    for field in (
        "malicious_ip",
        "reason",
        "incident_reference",
        "severity",
        "affected_systems",
        "evidence_summary",
        "first_seen",
        "last_seen",
        "requested_block_duration",
        "business_impact",
        "requester",
        "required_approval",
        "rollback",
    ):
        assert field in _PROCESS_FIELDS
        assert field in process["ec_email"]["mandatory_fields"]

    client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "prepare_firewall_email", "session_id": session_id},
    )
    sent = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "send_firewall_email", "session_id": session_id},
    ).json()
    assert sent["ec_workflow_state"] == "Pending send"
    assert sent["ec_session_state"]["awaiting_external"] is False
    email = next(item for item in sent["ec_actions"] if item["kind"] == "email_send")
    assert email["state"] == "APPROVAL_REQUIRED"
    assert email["production_side_effect"] is False
    assert sent["ec_email"]["logical_recipient"] == "FIREWALL_TEAM"
    assert sent["ec_email"]["not_transmitted"] is True

    reply = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "ingest_firewall_reply", "session_id": session_id},
    ).json()
    evidence_types = {item["source_type"] for item in reply["source_evidence"]}
    assert "email_mcp_fixture" in evidence_types
    assert "whitelisted" in str(reply["source_evidence"]).lower()
    assert reply["ec_email"]["inbound_fixture_backed"] is True
    outcome = reply["ec_investigation_outcome"]
    assert outcome["disposition"] == "needs_reassessment"
    assert outcome["reassessment"]["blind_benign"] is False
    assert outcome["reassessment"]["blind_malicious"] is False
    assert reply["production_side_effect"] is False

    client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "remove_whitelist", "session_id": session_id},
    )
    client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "request_ip_block", "session_id": session_id},
    )
    body = run_experience_center_turn(S3_SCENARIO_ID, session_id=session_id).model_dump()
    block = next(item for item in body["ec_actions"] if item["kind"] == "firewall_block")
    remove = next(item for item in body["ec_actions"] if item["kind"] == "firewall_remove_whitelist")
    assert block["state"] == "APPROVAL_REQUIRED"
    assert remove["state"] == "APPROVAL_REQUIRED"
    with pytest.raises(ValueError, match="ec_action_not_executable"):
        execute_action(block["action_id"])

    closed = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "generate_closure_summary", "session_id": session_id},
    ).json()
    assert "closure_summary" in closed["ec_investigation_outcome"]
    assert "fixture-backed" in closed["ec_investigation_outcome"]["closure_summary"].lower()


def test_s3_no_production_actions_or_live_email() -> None:
    from app.demo.fixtures.s3 import pack as s3_pack

    source = inspect.getsource(s3_pack)
    assert "routes_actions" not in source
    assert "/api/actions" not in source
    assert "smtplib" not in source
    assert "call_tool" not in source


def test_s3_initial_journey_titles_and_send_waits() -> None:
    from app.demo.ec_journeys import S3_INITIAL_TITLES

    initial = run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-journey")
    assert tuple(stage.title for stage in initial.ec_execution_journey.stages) == S3_INITIAL_TITLES
    run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-journey", follow_up_id="show_firewall_process")
    run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-journey", follow_up_id="prepare_firewall_email")
    sent = run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-journey", follow_up_id="send_firewall_email")
    types = [stage.semantic_type for stage in sent.ec_execution_journey.stages]
    assert "wait" in types or "hil" in types
    assert sent.ec_execution_journey.follow_up_id == "send_firewall_email"


def test_s3_notify_soc_lead_prepares_email_draft(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s3-notify-lead"
    run_experience_center_turn(S3_SCENARIO_ID, session_id=session_id)
    client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "show_firewall_process", "session_id": session_id},
    )
    client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "ingest_firewall_reply", "session_id": session_id},
    )
    body = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "notify_soc_lead", "session_id": session_id},
    ).json()
    notify = next(
        (item for item in body["ec_actions"] if item["label"] == "Notify SOC lead"),
        None,
    )
    assert notify is not None
    assert notify["kind"] == "email_send"
    assert notify["state"] == "APPROVAL_REQUIRED"
    assert notify["draft"]["to"] == "SOC_LEAD"
    assert "Escalation" in notify["draft"]["subject"] or PRIMARY_ATTACKER_IP in notify["draft"]["subject"]
    assert PRIMARY_ATTACKER_IP in notify["draft"]["body"]
    assert body["ec_session_state"]["pending_action_id"] == notify["action_id"]
