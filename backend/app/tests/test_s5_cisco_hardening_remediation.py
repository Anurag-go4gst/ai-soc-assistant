"""S5 Cisco R-17 hardening remediation — EC fixture pack, not production /chat."""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s5.pack import S5_DEVICE, S5_SCENARIO_ID
from app.main import app


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s5_initial_version_14_and_policy_not_production_cisco() -> None:
    envelope = run_experience_center_turn(S5_SCENARIO_ID, session_id="s5-e1").model_dump()
    assert envelope["ec_cisco"]["current_version"] == 14
    assert envelope["ec_cisco"]["provenance"] == "simulated_mcp"
    assert envelope["ec_policy_source"] == "ec_scenario_policy"
    assert envelope["ec_remediation_policy"]["splunk_not_device_management"] is True
    assert envelope["ec_resource_composition"]
    assert envelope["ec_investigation_scope"]["scope_note"]
    verify_ids = {item["follow_up_id"] for item in envelope["ec_followups"]}
    assert "verify_version" not in verify_ids
    assert envelope["production_side_effect"] is False


def test_s5_state_machine_14_to_15(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s5-machine"
    run_experience_center_turn(S5_SCENARIO_ID, session_id=session_id)
    for follow_up_id in (
        "show_hardening_policy",
        "check_current_version",
        "check_maintenance_window",
        "create_change_ticket",
        "request_network_approval",
        "approve_upgrade",
        "execute_upgrade",
        "verify_version",
        "update_incident",
        "generate_closure_summary",
    ):
        response = client.post(
            f"/demo/scenarios/{S5_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        if follow_up_id == "show_hardening_policy":
            assert body["ec_projection"]["phase_contract"]["provenance"]["kind"] == "ec_scenario_policy"
            assert "not production" in str(body["source_evidence"]).lower() or body["ec_policy_source"] == "ec_scenario_policy"
        if follow_up_id == "request_network_approval":
            email = next(item for item in body["ec_actions"] if item["kind"] == "email_send")
            assert email["state"] == "APPROVAL_REQUIRED"
            assert body["ec_email"]["logical_recipient"] == "NETWORK_TEAM"
            assert email["production_side_effect"] is False
        if follow_up_id == "approve_upgrade":
            upgrade = next(item for item in body["ec_actions"] if item["kind"] == "cisco_upgrade")
            assert upgrade["state"] == "APPROVED"
        if follow_up_id == "execute_upgrade":
            upgrade = next(item for item in body["ec_actions"] if item["kind"] == "cisco_upgrade")
            assert upgrade["state"] == "EXECUTED"
            assert upgrade["production_side_effect"] is False
        if follow_up_id == "verify_version":
            upgrade = next(item for item in body["ec_actions"] if item["kind"] == "cisco_upgrade")
            assert upgrade["state"] == "VERIFIED"
            assert upgrade["verify_result"]["current_version"] == 15
            assert body["ec_cisco"]["current_version"] == 15
            assert body["ec_investigation_outcome"]["remediation_status"] == "verified"
            assert body["ec_investigation_outcome"].get("verified_version") == 15
    assert S5_DEVICE in str(body)


def test_s5_execute_upgrade_journey_includes_hil_stage() -> None:
    from app.demo.ec_journeys import journey_for

    journey = journey_for(S5_SCENARIO_ID, ["execute_upgrade"])
    assert journey is not None
    assert any(stage.semantic_type == "hil" for stage in journey.stages)


def test_s5_no_production_cisco_connector() -> None:
    from app.demo.fixtures.s5 import pack as s5_pack

    source = inspect.getsource(s5_pack)
    assert "routes_actions" not in source
    assert "call_tool" not in source
    assert "netmiko" not in source
    assert "napalm" not in source


def test_s5_initial_journey_titles_disclose_version_14_as_fixture_replay() -> None:
    from app.demo.ec_journeys import S5_INITIAL_TITLES

    envelope = run_experience_center_turn(S5_SCENARIO_ID, session_id="s5-journey")
    titles = tuple(stage.title for stage in envelope.ec_execution_journey.stages)
    assert titles == S5_INITIAL_TITLES
    version_stage = next(stage for stage in envelope.ec_execution_journey.stages if stage.title == "Version 14 identified")
    assert "14" in " ".join(version_stage.activity)
    assert version_stage.outcome_change == "current_version=14"
