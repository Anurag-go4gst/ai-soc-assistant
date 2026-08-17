"""S6 investigation continuity — seven sequential turns, EC session only."""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s6.pack import S6_SCENARIO_ID
from app.demo.scenarios import _ALIAS_INDEX
from app.main import app


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s6_continuity_policy_no_identical_siem_rerun() -> None:
    envelope = run_experience_center_turn(S6_SCENARIO_ID, session_id="s6-policy").model_dump()
    policy = envelope["ec_continuity_policy"]
    assert policy["identical_siem_rerun_for_animation"] is False
    assert policy["destructive_remediation"] is False
    assert envelope["ec_evidence_reuse"]
    assert envelope["ec_action_readiness"]
    ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    scoped = run_experience_center_turn(
        S6_SCENARIO_ID,
        session_id="s6-policy",
        follow_up_id="scope_service_accounts",
    ).model_dump()
    assert ids == [item["evidence_id"] for item in scoped["source_evidence"][:1]]


def test_s6_seven_turns_session_stable_applicability(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s6-continuity"
    first = run_experience_center_turn(S6_SCENARIO_ID, session_id=session_id).model_dump()
    assert first["ec_session_state"]["session_id"] == session_id
    assert first["ec_session_state"]["turn"] == 0
    assert first["ec_scope"] == "privileged_admin_vpn_germany_yesterday"

    turns = [
        ("scope_service_accounts", 1),
        ("scope_build_servers", 2),
        ("check_last_month_incident", 3),
        ("fetch_old_incident_ticket", 4),
        ("update_incident_ticket", 5),
        ("notify_incident_owner", 6),
        ("generate_current_scope_summary", 7),
    ]
    body = first
    for follow_up_id, expected_turn in turns:
        response = client.post(
            f"/demo/scenarios/{S6_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ec_session_state"]["session_id"] == session_id
        assert body["ec_session_state"]["turn"] == expected_turn
        assert body["production_side_effect"] is False
        if follow_up_id == "scope_service_accounts":
            statuses = {item["id"]: item["status"] for item in body["ec_evidence_state"]}
            assert statuses["admin_vpn"] == "OUT_OF_SCOPE"
            assert statuses["service_accounts"] == "OBTAINED"
            assert "no longer applicable" in str(body["ec_evidence_state"]).lower()
        if follow_up_id == "scope_build_servers":
            statuses = {item["id"]: item["status"] for item in body["ec_evidence_state"]}
            assert statuses["service_accounts"] == "SUPERSEDED"
            labels = {item["status"] for item in body["ec_investigation_outcome"]["applicability"]}
            assert "OUT_OF_SCOPE" in labels
            assert "SUPERSEDED" in labels
        if follow_up_id == "check_last_month_incident":
            labels = {item["status"] for item in body["ec_investigation_outcome"]["applicability"]}
            assert "STALE" in labels
            assert "REUSABLE" in labels
        if follow_up_id == "fetch_old_incident_ticket":
            assert body["ec_ticket_id"] == "INC-VPN-0712"
            fetch = next(item for item in body["ec_actions"] if item["kind"] == "ticket_fetch")
            assert fetch["state"] == "EXECUTED"
        if follow_up_id == "update_incident_ticket":
            update = next(item for item in body["ec_actions"] if item["kind"] == "ticket_update")
            assert update["state"] == "EXECUTED"
            assert update["receipt"]["production_side_effect"] is False
        if follow_up_id == "notify_incident_owner":
            email = next(item for item in body["ec_actions"] if item["kind"] == "email_send")
            assert email["state"] == "APPROVAL_REQUIRED"
            assert body["ec_email"]["logical_recipient"] == "INCIDENT_OWNER"
            assert email["production_side_effect"] is False
        if follow_up_id == "generate_current_scope_summary":
            assert "OUT_OF_SCOPE" in body["ec_investigation_outcome"]["closure_summary"]
            assert "No destructive" in body["ec_investigation_outcome"]["closure_summary"]


def test_s6_synonym_does_not_grow_alias_index(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    before = dict(_ALIAS_INDEX)
    client = TestClient(app)
    session_id = "s6-syn"
    run_experience_center_turn(S6_SCENARIO_ID, session_id=session_id)
    response = client.post(
        f"/demo/scenarios/{S6_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "What about service accounts?", "session_id": session_id},
    )
    assert response.status_code == 200, response.text
    assert "scope_service_accounts" in response.json()["ec_session_state"]["applied_follow_up_ids"]
    assert _ALIAS_INDEX == before


def test_s6_no_production_session() -> None:
    from app.demo.fixtures.s6 import pack as s6_pack

    source = inspect.getsource(s6_pack)
    assert "routes_chat" not in source
    assert "session_store" not in source
    assert "_ALIAS_INDEX" not in source


def test_s6_scope_change_journey_marks_applicability() -> None:
    run_experience_center_turn(S6_SCENARIO_ID, session_id="s6-journey")
    scoped = run_experience_center_turn(
        S6_SCENARIO_ID,
        session_id="s6-journey",
        follow_up_id="scope_service_accounts",
    )
    blob = " ".join(stage.title for stage in scoped.ec_execution_journey.stages)
    assert "OUT_OF_SCOPE" in blob
    assert scoped.ec_execution_journey.header == "Continuing investigation"
    builds = run_experience_center_turn(
        S6_SCENARIO_ID,
        session_id="s6-journey",
        follow_up_id="scope_build_servers",
    )
    assert "SUPERSEDED" in " ".join(stage.title for stage in builds.ec_execution_journey.stages)
