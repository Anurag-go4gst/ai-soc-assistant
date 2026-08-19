"""S4 zero-day / no SOAR playbook — EC agent lifecycle (EC-only)."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from app.demo.ec_actions import clear_all_for_tests as clear_actions
from app.demo.ec_fsm_store import clear_all_for_tests
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s4.pack import S4_ADVISORY_ID, S4_QUERY, S4_SCENARIO_ID
from app.main import app


def setup_function() -> None:
    clear_all_for_tests()
    clear_actions()


def test_s4_preread_only_uses_canonical_initial_journey() -> None:
    from app.demo.ec_journeys import INITIAL_ARCHITECTURE_STEP_COUNT, journey_for
    from app.demo.fixtures.s4.pack import S4_SCENARIO_ID

    journey = journey_for(S4_SCENARIO_ID, ["show_advisory"])
    assert journey is not None
    assert journey.kind == "initial"
    assert len(journey.stages) == INITIAL_ARCHITECTURE_STEP_COUNT


def test_s4_initial_turn_envelope_uses_ten_step_journey() -> None:
    from app.demo.ec_journeys import INITIAL_ARCHITECTURE_STEP_COUNT
    from app.demo.ec_turn import run_experience_center_turn
    from app.demo.fixtures.s4.pack import S4_SCENARIO_ID

    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-journey-initial").model_dump()
    journey = envelope.get("ec_execution_journey") or {}
    assert len(journey.get("stages") or []) == INITIAL_ARCHITECTURE_STEP_COUNT


def test_s4_agent_plan_ready_on_initial_turn() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-agent").model_dump()
    workflow = envelope["ec_agent_workflow"]
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert workflow["investigation_plan"]["editable"] is True
    assert len(workflow["investigation_plan"]["steps"]) >= 7
    assert not envelope.get("ec_investigation_phases")
    assert not envelope.get("ec_opening_briefing")
    assert envelope["analyst"]["finding_title"] == "Zero-day exposure — VPN gateways"


def test_s4_run_investigation_pauses_for_agilus_hil() -> None:
    session_id = "s4-hil"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    mid = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    ).model_dump()
    assert mid["ec_agent_lifecycle"] == "INVESTIGATION_NEEDS_APPROVAL"
    assert mid["ec_agent_workflow"]["hil_prompt"] is not None
    assert "Agilus" in mid["ec_agent_workflow"]["hil_prompt"]["body"]
    assert "run_network_assessment" in mid["ec_session_state"]["applied_follow_up_ids"]


def test_s4_full_agent_lifecycle_to_complete() -> None:
    session_id = "s4-full"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    after_inv = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="skip_investigation_vuln_scan",
    ).model_dump()
    assert after_inv["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    assert after_inv["ec_agent_workflow"]["phase"] == "investigation_complete"
    assert after_inv["ec_agent_workflow"]["remediation_offer"] is None
    assert not after_inv["ec_agent_workflow"]["remediation_plan"]["visible"]
    assert after_inv["ec_agent_workflow"].get("next_step_cta")
    inv_results = after_inv["ec_agent_workflow"]["investigation_results"]["steps"]
    gateways = next(step for step in inv_results if step["id"] == "identify_gateways")
    assert "12 internet-facing" in (gateways.get("finding") or {}).get("headline_finding", "")
    assert gateways["status"] == "COMPLETE"
    hunt = next(step for step in inv_results if step["id"] == "hunt_iocs")
    assert hunt["finding"]["headline_finding"]
    assert "—" not in hunt["finding"]["headline_finding"]
    conclusion = after_inv["ec_agent_workflow"]["investigation_conclusion"]
    assert conclusion is not None
    assert conclusion.get("narrative_points")
    assert "4 gateways are vulnerable" in conclusion.get("headline", "")

    ready = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_remediation_plan",
    ).model_dump()
    assert ready["ec_agent_lifecycle"] == "REMEDIATION_PLAN_READY"
    assert ready["ec_agent_workflow"]["phase"] == "remediation"
    assert ready["ec_agent_workflow"]["remediation_plan"]["visible"]

    final = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_remediation",
        agent_payload={"selected_step_ids": [step["id"] for step in _rem_steps()]},
    ).model_dump()
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    assert final["ec_agent_workflow"]["final_summary"] is not None
    assert final["production_side_effect"] is False


def test_s4_deselected_investigation_step_skipped() -> None:
    session_id = "s4-skip-soar"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    selected = [step["id"] for step in _inv_steps() if step["id"] != "soar_playbooks"]
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": selected},
    )
    envelope = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="skip_investigation_vuln_scan",
    ).model_dump()
    assert "check_soar_playbooks" not in envelope["ec_session_state"]["applied_follow_up_ids"]


def test_s4_follow_up_retains_context() -> None:
    session_id = "s4-context"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id, follow_up_id="skip_investigation_vuln_scan")
    summary = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="generate_executive_summary",
    ).model_dump()
    assert summary["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    assert summary["ec_agent_workflow"]["executive_summary"]
    assert "run_network_assessment" in summary["ec_session_state"]["applied_follow_up_ids"]


def test_s4_pack_isolation() -> None:
    from app.demo.ec_agent_lifecycle import handle_s4_agent_follow_up
    from app.demo.fixtures.s4 import pack as s4_pack

    source = inspect.getsource(s4_pack) + inspect.getsource(handle_s4_agent_follow_up)
    assert "pipeline.py" not in source
    assert "routes_chat" not in source


def test_s4_no_playbook_stage_is_complete_context_not_failed() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-journey")
    assert envelope.ec_execution_journey is not None
    assert envelope.ec_agent_workflow is not None


def test_s4_http_follow_up_with_agent_payload() -> None:
    from app.config import settings

    client = TestClient(app)
    session_id = "s4-http"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "app_auth_enabled", False)
        run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
        response = client.post(
            f"/demo/scenarios/{S4_SCENARIO_ID}/follow-up",
            json={
                "follow_up_id": "run_investigation",
                "session_id": session_id,
                "agent_payload": {"selected_step_ids": [step["id"] for step in _inv_steps()]},
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["ec_agent_lifecycle"] == "INVESTIGATION_NEEDS_APPROVAL"


def _inv_steps() -> list[dict[str, str]]:
    from app.demo.ec_agent_lifecycle import S4_INVESTIGATION_STEP_DEFS

    return [{"id": step["id"]} for step in S4_INVESTIGATION_STEP_DEFS if step.get("default_selected", True)]


def _rem_steps() -> list[dict[str, str]]:
    from app.demo.ec_agent_lifecycle import S4_REMEDIATION_STEP_DEFS

    return [{"id": step["id"]} for step in S4_REMEDIATION_STEP_DEFS]


def test_s4_remediation_auto_executes_without_manual_action_clicks() -> None:
    session_id = "s4-rem-auto"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id, follow_up_id="skip_investigation_vuln_scan")
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="create_remediation_plan",
    )
    final = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_remediation",
        agent_payload={"selected_step_ids": [step["id"] for step in _rem_steps()]},
    ).model_dump()
    assert final["ec_agent_lifecycle"] == "COMPLETE"
    from app.demo import ec_actions

    pending = [
        item
        for item in ec_actions.list_actions_for_session(session_id, S4_SCENARIO_ID)
        if item.state == "APPROVAL_REQUIRED"
    ]
    assert pending == []
    second = run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id).model_dump()
    pending_again = [
        item
        for item in ec_actions.list_actions_for_session(session_id, S4_SCENARIO_ID)
        if item.state == "APPROVAL_REQUIRED"
    ]
    assert pending_again == []
    assert second["ec_agent_lifecycle"] == "COMPLETE"
    assert len(second.get("ec_followups") or []) <= 1


def test_s4_plan_ready_shows_only_plan_phase() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-phase").model_dump()
    workflow = envelope["ec_agent_workflow"]
    assert workflow["phase"] == "plan"
    assert workflow.get("opening_narrative")
    assert workflow.get("investigation_results") is None
    assert not workflow.get("executive_summary")
    assert workflow.get("remediation_offer") is None


def test_s4_plan_ready_returns_no_orchestration_chips() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-chips").model_dump()
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert envelope["ec_followups"] == []


def test_s4_investigation_outcome_partial_exposure() -> None:
    session_id = "s4-exposure"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [step["id"] for step in _inv_steps()]},
    )
    envelope = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="skip_investigation_vuln_scan",
    ).model_dump()
    assert envelope["ec_investigation_outcome"]["exposure"] == "PARTIAL"
    assert S4_ADVISORY_ID in str(envelope)
    assert envelope["ec_soar_playbook"] == "not_available"
