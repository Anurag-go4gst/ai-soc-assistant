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
    assert envelope["ec_prior_investigation"]["independent_of_s1_session"] is True
    assert PRIMARY_ATTACKER_IP in envelope["analyst"]["assessment"]


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
    assert sent["ec_workflow_state"] == "AWAITING_FIREWALL_TEAM_CONFIRMATION"
    assert sent["ec_session_state"]["awaiting_external"] is True
    email = next(item for item in sent["ec_actions"] if item["kind"] == "email_send")
    assert email["state"] == "EXECUTED"
    assert email["production_side_effect"] is False
    assert email["receipt"]["production_side_effect"] is False

    reply = client.post(
        f"/demo/scenarios/{S3_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "ingest_firewall_reply", "session_id": session_id},
    ).json()
    evidence_types = {item["source_type"] for item in reply["source_evidence"]}
    assert "email_mcp_fixture" in evidence_types
    assert "whitelisted" in str(reply["source_evidence"]).lower()
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


def test_s3_no_production_actions_or_live_email() -> None:
    from app.demo.fixtures.s3 import pack as s3_pack

    source = inspect.getsource(s3_pack)
    assert "routes_actions" not in source
    assert "/api/actions" not in source
    assert "smtplib" not in source
    assert "call_tool" not in source
