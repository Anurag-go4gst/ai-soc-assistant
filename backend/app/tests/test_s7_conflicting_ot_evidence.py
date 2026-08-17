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
    assert "recommend_cmdb_correction" in ids
