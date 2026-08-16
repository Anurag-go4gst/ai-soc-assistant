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
from app.demo.scenarios import list_demo_scenarios, run_demo_scenario
from app.main import app
from app.schemas.responses import PlaceholderResponse


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s2_listed() -> None:
    assert S2_SCENARIO_ID in {item["scenario_id"] for item in list_demo_scenarios()}


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
        if follow_up_id == "disable_integration_credential":
            disable = next(item for item in body["ec_actions"] if item["kind"] == "iam_disable")
            assert disable["state"] == "APPROVAL_REQUIRED"
            with pytest.raises(ValueError, match="ec_action_not_executable"):
                execute_action(disable["action_id"])
            assert disable["production_side_effect"] is False


def test_s2_pack_does_not_import_production_actions() -> None:
    from app.demo.fixtures.s2 import pack as s2_pack

    source = inspect.getsource(s2_pack)
    assert "routes_actions" not in source
    assert "call_tool" not in source
    assert "evaluate_mcp_execution" not in source
