"""S2 AI application security — EC fixture pack, not production /chat."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_actions import execute_action
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s2.pack import S2_FOLLOWUP_IDS, S2_SCENARIO_ID
from app.demo.scenarios import list_experience_center_scenarios, run_demo_scenario
from app.main import app
from app.schemas.responses import PlaceholderResponse


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s2_listed() -> None:
    assert S2_SCENARIO_ID in {item["scenario_id"] for item in list_experience_center_scenarios()}


def test_s2_placeholder_compatible() -> None:
    payload = run_demo_scenario(S2_SCENARIO_ID)
    assert PlaceholderResponse(**payload).demo_mode is True


def test_s2_prompt_injection_confirmed_blocked_tool_not_a_breach() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-d1").model_dump()
    outcome = envelope["ec_investigation_outcome"]
    blob = " ".join(outcome["confirmed"]).lower()
    assert "prompt-injection" in blob or "prompt injection" in blob
    assert "export_customer_records" in blob
    assert "blocked" in blob
    unconfirmed = " ".join(outcome["unconfirmed"]).lower()
    assert "successful unauthorized tool execution" in unconfirmed
    assert "restricted customer-data access" in unconfirmed
    assert "credential compromise" in unconfirmed
    assert "session hijack" in unconfirmed
    missing = " ".join(outcome["missing_evidence"]).lower()
    assert "dlp" in missing
    assert envelope["production_side_effect"] is False
    assert envelope["ec_provenance"]["live_llm_called"] is False
    assert envelope["ec_provenance"]["live_mcp_called"] is False
    assessment = envelope["analyst"]["assessment"].lower()
    assert "attack attempted" in assessment
    assert "breach not confirmed" in assessment


def test_s2_follow_ups_advance_and_credential_disable_requires_approval(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s2-follow"
    run_experience_center_turn(S2_SCENARIO_ID, session_id=session_id)
    previous = 0
    for follow_up_id in (
        "check_dlp",
        "check_tool_call_history",
        "check_identity",
        "check_data_source",
        "show_ai_security_policy",
        "create_ai_incident_ticket",
        "disable_integration_credential",
        "notify_app_security",
    ):
        assert follow_up_id in S2_FOLLOWUP_IDS
        response = client.post(
            f"/demo/scenarios/{S2_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ec_session_state"]["turn"] == previous + 1
        previous = body["ec_session_state"]["turn"]
        assert body["production_side_effect"] is False
        if follow_up_id == "check_dlp":
            statuses = {item["id"]: item["status"] for item in body["ec_evidence_state"]}
            assert statuses["dlp"] == "OBTAINED"
        if follow_up_id == "show_ai_security_policy":
            ids = {item["evidence_id"] for item in body["source_evidence"]}
            assert "ev-s2-policy" in ids
            assert not any("policy" in item.lower() for item in body["ec_investigation_outcome"]["missing_evidence"])
        if follow_up_id == "disable_integration_credential":
            disable = next(item for item in body["ec_actions"] if item["kind"] == "iam_disable")
            assert disable["state"] == "APPROVAL_REQUIRED"
            with pytest.raises(ValueError, match="ec_action_not_executable"):
                execute_action(disable["action_id"])
        if follow_up_id == "notify_app_security":
            email = next(item for item in body["ec_actions"] if item["kind"] == "email_send")
            assert email["state"] == "APPROVAL_REQUIRED"
            assert body["ec_email"]["logical_recipient"] == "APPSEC_TEAM"
            assert body["ec_email"]["not_transmitted"] is True
            assert email["production_side_effect"] is False


def test_s2_pack_does_not_import_production_actions() -> None:
    from app.demo.fixtures.s2 import pack as s2_pack

    source = inspect.getsource(s2_pack)
    assert "routes_actions" not in source
    assert "call_tool" not in source
    assert "evaluate_mcp_execution" not in source


def test_s2_credential_verify_requires_execute_and_closure_keeps_breach_unconfirmed() -> None:
    from app.demo import ec_actions

    session_id = "s2-ops-close"
    run_experience_center_turn(S2_SCENARIO_ID, session_id=session_id)
    disabled = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="disable_integration_credential",
    )
    disable = next(item for item in disabled.ec_actions if item.kind == "iam_disable")
    try:
        ec_actions.verify_action(disable.action_id)
        raise AssertionError("verify must not succeed before execute")
    except ValueError as exc:
        assert "ec_action_not_verifiable" in str(exc)
    executed = ec_actions.execute_action(ec_actions.approve_action(disable.action_id).action_id)
    verified = ec_actions.verify_action(executed.action_id)
    assert verified.state == "VERIFIED"
    assert verified.verify_result
    assert verified.verify_result.get("credential_state") == "disabled"
    closed = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="generate_closure_summary",
    )
    outcome = closed.model_dump()["ec_investigation_outcome"]
    assert "not confirmed" in outcome["closure_summary"].lower()
    assert "blocked" in outcome["closure_summary"].lower()


def test_s2_initial_journey_is_siem_first_reuse_blocked_not_confirmed() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-journey")
    journey = envelope.ec_execution_journey
    assert journey is not None
    assert len(journey.stages) == 10
    titles = [stage.title.lower() for stage in journey.stages]
    blob = " | ".join(titles)
    assert "checking existing siem coverage" in blob
    assert "executing approved detection" in blob
    assert "validating governed spl" in blob
    assert "governed llm" in blob
    assert "blocked" in blob or "authorization" in blob
    assert "failed" not in blob
    dlp = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-journey", follow_up_id="check_dlp")
    assert dlp.ec_execution_journey.header == "Continuing investigation"
    assert dlp.ec_execution_journey.follow_up_id == "check_dlp"
