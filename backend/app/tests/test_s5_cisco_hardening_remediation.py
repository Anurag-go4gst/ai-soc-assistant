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


def test_s5_evidence_surfaces_agree(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s5-agree"
    run_experience_center_turn(S5_SCENARIO_ID, session_id=session_id)
    follow_ups = (
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
    )
    for follow_up_id in follow_ups:
        response = client.post(
            f"/demo/scenarios/{S5_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        missing = body["ec_investigation_outcome"]["missing_evidence"]
        state_by_label = {item["label"].lower(): item["status"] for item in body["ec_evidence_state"]}
        readiness = {row["action"]: row["state"] for row in body["ec_action_readiness"]}
        checks = [
            ("cisco.get_version", "cisco.get_version", "Confirm current version (cisco.get_version)"),
            ("policy", "enterprise hardening policy", "Review hardening policy"),
            ("change ticket", "change ticket", "Create change ticket"),
            ("maintenance", "maintenance", "Request network approval"),
        ]
        for missing_token, state_label, readiness_action in checks:
            in_missing = any(missing_token in item.lower() for item in missing)
            state_obtained = state_by_label.get(state_label.lower()) == "OBTAINED"
            readiness_obtained = readiness.get(readiness_action) in {"OBTAINED", "VERIFIED", "READY", "READY_FOR_REVIEW", "EXECUTED", "AWAITING_APPROVAL"}
            if in_missing:
                assert not state_obtained, (follow_up_id, missing_token, state_by_label)
                assert readiness.get(readiness_action) not in {"OBTAINED", "VERIFIED"}, (follow_up_id, readiness_action, readiness)
        if follow_up_id == "show_hardening_policy":
            policy_items = [item for item in body["source_evidence"] if item["evidence_id"] == "ev-s5-policy"]
            assert policy_items
            assert "version 14 must be upgraded to version 15" in str(policy_items[0]["preview_rows"])
        if follow_up_id == "generate_closure_summary":
            assert body["ec_investigation_outcome"]["closure_summary"]


def test_s5_policy_not_in_confirmed_before_show_hardening_policy() -> None:
    initial = run_experience_center_turn(S5_SCENARIO_ID, session_id="s5-policy-gate").model_dump()
    assert not any(item["evidence_id"] == "ev-s5-policy" for item in initial["source_evidence"])
    confirmed_blob = " ".join(initial["ec_investigation_outcome"]["confirmed"]).lower()
    assert "hardening policy applies" not in confirmed_blob
    after = run_experience_center_turn(
        S5_SCENARIO_ID,
        session_id="s5-policy-gate",
        follow_up_id="show_hardening_policy",
    ).model_dump()
    assert any(item["evidence_id"] == "ev-s5-policy" for item in after["source_evidence"])


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
