"""S4 zero-day / no SOAR playbook — EC fixture pack, not production /chat."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_actions import execute_action
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s4.pack import S4_ADVISORY_ID, S4_SCENARIO_ID
from app.main import app


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s4_no_soar_playbook_and_honest_exposure() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-d3").model_dump()
    assert envelope["ec_soar_playbook"] == "not_available"
    assert any("No threat-specific SOAR playbook" in item for item in envelope["ec_projection"]["resource_plan"]["items"])
    statuses = {item["id"]: item["status"] for item in envelope["ec_evidence_state"]}
    assert statuses["soar"] == "NOT_AVAILABLE"
    outcome = envelope["ec_investigation_outcome"]
    assert outcome["exposure"] == "PARTIAL"
    assert outcome["exposure_validation"] == "REQUIRES_VALIDATION"
    assert "compromised" in outcome["vulnerable_vs_compromised"].lower()
    assert S4_ADVISORY_ID in str(envelope)
    assert envelope["production_side_effect"] is False
    assert envelope["ec_provenance"]["live_mcp_called"] is False


def test_s4_versions_update_exposure_and_hardening_hil(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s4-follow"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    for follow_up_id in (
        "show_advisory",
        "list_affected_assets",
        "check_gateway_versions",
        "search_exploitation_indicators",
        "show_hardening_guidance",
        "apply_temporary_control",
    ):
        response = client.post(
            f"/demo/scenarios/{S4_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
    body = response.json()
    outcome = body["ec_investigation_outcome"]
    assert outcome["exposure_validation"] == "VERSION_EVIDENCE_APPLIED"
    confirmed = " ".join(outcome["confirmed"]).lower()
    assert "vpn-gw-01" in confirmed
    assert "not running an affected version" in confirmed
    assert "exploitation not confirmed" in confirmed
    assert "compromised" not in confirmed or "not confirmed" in " ".join(outcome["unconfirmed"]).lower()
    control = next(item for item in body["ec_actions"] if "temporary" in item["label"].lower() or item["kind"] == "firewall_block")
    assert control["state"] == "APPROVAL_REQUIRED"
    with pytest.raises(ValueError, match="ec_action_not_executable"):
        execute_action(control["action_id"])
    assert "ec_scenario_policy" in str(body["source_evidence"])

    notified = client.post(
        f"/demo/scenarios/{S4_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "notify_network_team", "session_id": session_id},
    ).json()
    email = next(item for item in notified["ec_actions"] if item["kind"] == "email_send")
    assert email["state"] == "APPROVAL_REQUIRED"
    assert notified["ec_email"]["logical_recipient"] == "NETWORK_TEAM"


def test_s4_pack_isolation() -> None:
    from app.demo.fixtures.s4 import pack as s4_pack

    source = inspect.getsource(s4_pack)
    assert "routes_actions" not in source
    assert "call_tool" not in source
    assert "pipeline.py" not in source


def test_s4_no_playbook_stage_is_complete_context_not_failed() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-journey")
    stage = next(item for item in envelope.ec_execution_journey.stages if item.title == "No predefined SOAR playbook available")
    assert stage.semantic_type != "failed"
    assert "not a failed stage" in " ".join(stage.activity).lower()
