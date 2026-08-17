"""Experience Center envelope is /demo-owned and does not change /chat."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import UnknownFollowUpError, run_experience_center_turn
from app.demo.scenarios import run_demo_scenario
from app.main import app
from app.schemas.responses import PlaceholderResponse


def setup_function() -> None:
    clear_all_for_tests()


def test_run_demo_scenario_still_builds_placeholder_response() -> None:
    payload = run_demo_scenario("firewall_baseline_template_spl")
    response = PlaceholderResponse(**payload)
    assert response.demo_mode is True
    assert response.message or response.analyst_summary


def test_experience_center_turn_is_demo_owned_envelope() -> None:
    envelope = run_experience_center_turn("firewall_baseline_template_spl", session_id="ec-b1")
    dumped = envelope.model_dump()
    assert dumped["scenario_id"] == "firewall_baseline_template_spl"
    assert dumped["route_source"] == "ec_fixture_selected"
    assert dumped["ec_projection"]["provenance"]["kind"] == "experience_center_fixture"
    assert "production InvestigationOutcome field unused" in dumped["ec_projection"]["investigation_outcome"]["items"]
    assert dumped["ec_session_state"]["turn"] == 0
    assert dumped["ec_provenance"]["envelope"] == "experience_center_response"
    assert dumped["ec_provenance"]["live_llm_called"] is False


def test_ec_projection_provenance_present() -> None:
    envelope = run_experience_center_turn("failed_login_spike_app01", session_id="ec-b2")
    projection = envelope.ec_projection
    assert projection.provenance.kind == "experience_center_fixture"
    assert projection.understanding.provenance.kind == "ec_fixture_selected"
    assert projection.phase_contract.provenance.kind == "ec_scenario_policy"


def test_follow_up_advances_turn() -> None:
    first = run_experience_center_turn("firewall_deny_coordinated_attack", session_id="ec-b4")
    chip = first.ec_followups[0]
    second = run_experience_center_turn(
        "firewall_deny_coordinated_attack",
        session_id="ec-b4",
        follow_up_id=chip.follow_up_id,
    )
    assert second.ec_session_state.turn == first.ec_session_state.turn + 1
    assert chip.follow_up_id in second.ec_session_state.applied_follow_up_ids
    assert second.scenario_id == "firewall_deny_coordinated_attack"


def test_unknown_follow_up_does_not_invent_scenario() -> None:
    try:
        run_experience_center_turn(
            "firewall_deny_coordinated_attack",
            session_id="ec-b4-unknown",
            follow_up_id="not_a_real_follow_up",
        )
        raise AssertionError("expected UnknownFollowUpError")
    except UnknownFollowUpError:
        pass
    try:
        run_experience_center_turn("not_a_real_scenario", session_id="ec-b4-unknown")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_demo_run_openapi_is_not_placeholder_response(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    schema = app.openapi()
    chat = schema["paths"]["/chat"]["post"]["responses"]["200"]
    demo_run = schema["paths"]["/demo/scenarios/{scenario_id}/run"]["post"]["responses"]["200"]
    assert "PlaceholderResponse" in str(chat)
    assert "ExperienceCenterResponse" in str(demo_run)
    assert "PlaceholderResponse" not in str(demo_run)


def test_http_follow_up_unknown_id_is_404(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    response = client.post(
        "/demo/scenarios/firewall_deny_coordinated_attack/follow-up",
        json={"follow_up_id": "not_a_real_follow_up", "session_id": "ec-http"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown follow-up"


def test_ec_execution_journey_is_optional_and_not_on_placeholder() -> None:
    from pathlib import Path

    from app.demo.ec_response import EcExecutionJourney, EcExecutionStage

    schema_text = Path(__file__).resolve().parents[1].joinpath("schemas/responses.py").read_text(encoding="utf-8")
    assert "ec_execution_journey" not in schema_text
    envelope = run_experience_center_turn("firewall_baseline_template_spl", session_id="ec-journey-optional")
    assert envelope.ec_execution_journey is None
    journey = EcExecutionJourney(
        journey_id="lab-fallback",
        kind="initial",
        header="Running governed investigation pipeline",
        stages=[
            EcExecutionStage(id="understand", title="Understanding the question", semantic_type="understand"),
            EcExecutionStage(id="plan", title="Planning evidence", semantic_type="plan"),
            EcExecutionStage(id="gather", title="Gathering evidence", semantic_type="gather"),
            EcExecutionStage(id="outcome", title="Building InvestigationOutcome", semantic_type="outcome"),
        ],
    )
    dumped = envelope.model_copy(update={"ec_execution_journey": journey}).model_dump()
    assert dumped["ec_execution_journey"]["stages"][0]["id"] == "understand"
    payload = run_demo_scenario("firewall_baseline_template_spl")
    PlaceholderResponse(**payload)
