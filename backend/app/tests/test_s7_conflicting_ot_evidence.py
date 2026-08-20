"""S7 conflicting Splunk vs retired CMDB — no forced incident."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s7.pack import S7_SCENARIO_ID
from app.main import app


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s7_initial_action_readiness_blocks_incident() -> None:
    envelope = run_experience_center_turn(S7_SCENARIO_ID, session_id="s7-readiness").model_dump()
    readiness = envelope["ec_action_readiness"]
    assert any(row["action"] == "Force incident from Splunk alone" and row["state"] == "NOT_RECOMMENDED_YET" for row in readiness)
    assert any("BLOCKED" in row["state"] for row in readiness if "incident" in row["action"].lower())
    assert envelope["ec_investigation_pivot"]["title"]


def test_s7_initial_conflict_no_forced_incident() -> None:
    envelope = run_experience_center_turn(S7_SCENARIO_ID, session_id="s7-e3").model_dump()
    outcome = envelope["ec_investigation_outcome"]
    assert outcome["disposition"] == "unresolved_conflict"
    assert outcome["forced_incident"] is False
    statuses = {item["id"]: item["status"] for item in envelope["ec_evidence_state"]}
    assert statuses["cmdb"] == "CONFLICTING"
    assert statuses["splunk"] == "OBTAINED"
    assert statuses["ot_inventory"] == "MISSING"
    ticket_ids = {item["follow_up_id"] for item in envelope["ec_followups"]}
    assert "create_incident_ticket" not in ticket_ids
    assert envelope["production_side_effect"] is False


def test_s7_path_a_resolves_to_active_device_then_ticket(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s7-a"
    run_experience_center_turn(S7_SCENARIO_ID, session_id=session_id)
    for follow_up_id in ("check_ot_inventory", "check_firewall_activity", "check_arp_mac", "ask_ot_team", "ingest_ot_response", "create_incident_ticket"):
        response = client.post(
            f"/demo/scenarios/{S7_SCENARIO_ID}/follow-up",
            json={"follow_up_id": follow_up_id, "session_id": session_id},
        )
        assert response.status_code == 200, response.text
        if follow_up_id == "ask_ot_team":
            asked = response.json()
            email = next(item for item in asked["ec_actions"] if item["kind"] == "email_send")
            assert email["state"] == "APPROVAL_REQUIRED"
            assert asked["ec_email"]["logical_recipient"] == "OT_TEAM"
    body = response.json()
    assert body["ec_investigation_outcome"]["disposition"] == "confirmed"
    assert body["ec_path"] == "A"
    ticket = next(item for item in body["ec_actions"] if item["kind"] == "ticket_create")
    assert ticket["state"] == "EXECUTED"
    assert ticket["production_side_effect"] is False


def test_s7_path_b_recycled_identity_no_incident(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    session_id = "s7-b"
    run_experience_center_turn(S7_SCENARIO_ID, session_id=session_id)
    response = client.post(
        f"/demo/scenarios/{S7_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "confirm_stale_identity", "session_id": session_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ec_investigation_outcome"]["disposition"] == "not_an_incident"
    assert body["ec_path"] == "B"
    assert "No active compromise" in " ".join(body["ec_investigation_outcome"]["confirmed"]) or "no active compromise" in str(body["ec_investigation_outcome"]).lower()
    ids = {item["follow_up_id"] for item in body["ec_followups"]}
    assert "create_incident_ticket" not in ids
    correction = client.post(
        f"/demo/scenarios/{S7_SCENARIO_ID}/follow-up",
        json={"follow_up_id": "recommend_cmdb_correction", "session_id": session_id},
    )
    assert correction.status_code == 200, correction.text
    tickets = [item for item in correction.json()["ec_actions"] if item["kind"] == "ticket_create"]
    assert tickets
    assert all(item["state"] == "EXECUTED" for item in tickets)
    assert all(item["production_side_effect"] is False for item in tickets)
    assert "INC-OT-14" not in str(correction.json()["ec_actions"])


def test_s7_initial_journey_lingers_on_conflict() -> None:
    envelope = run_experience_center_turn(S7_SCENARIO_ID, session_id="s7-journey").model_dump()
    assert envelope["ec_investigation_outcome"]["disposition"] == "unresolved_conflict"
    titles = [stage["title"] for stage in envelope["ec_execution_journey"]["stages"]]
    assert "Conflict detected" in titles
    conflict = next(stage for stage in envelope["ec_execution_journey"]["stages"] if stage["title"] == "Conflict detected")
    assert conflict["duration_ms_hint"] and conflict["duration_ms_hint"] >= 1200
    assert conflict["outcome_change"] == "unresolved_conflict"
