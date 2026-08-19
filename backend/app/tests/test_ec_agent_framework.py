"""Tests for the reusable EC agent workflow framework."""

from __future__ import annotations

from app.demo.ec_agent.registry import get_agent_profile, has_agent_profile, registered_agent_scenario_ids
from app.demo.ec_agent.dispatch import handle_agent_follow_up, maybe_init_agent_session
from app.demo.ec_agent_lifecycle import S4_SCENARIO_ID
from app.demo.ec_turn import run_experience_center_turn


def test_s4_agent_profile_is_registered() -> None:
    assert has_agent_profile(S4_SCENARIO_ID)
    profile = get_agent_profile(S4_SCENARIO_ID)
    assert profile is not None
    assert profile.scenario_id == S4_SCENARIO_ID
    assert profile.build_workflow is not None
    assert S4_SCENARIO_ID in registered_agent_scenario_ids()


def test_agent_dispatch_returns_none_for_non_agent_scenario() -> None:
    handled = handle_agent_follow_up(
        session_id="ec-framework",
        family="s1_governed_splunk",
        scenario_id="s1_governed_splunk_investigation",
        follow_up_id="run_investigation",
        agent_payload={},
        session_record={},
    )
    assert handled is None


def test_agent_first_turn_initializes_s4_state() -> None:
    session_id = "ec-framework-init"
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id).model_dump()
    assert envelope["ec_agent_workflow"] is not None
    assert envelope["ec_agent_lifecycle"] == "PLAN_READY"
    assert "show_advisory" in envelope["ec_session_state"]["applied_follow_up_ids"]


def test_maybe_init_agent_session_skips_when_preread_already_applied() -> None:
    from app.demo import ec_fsm_store

    session_id = "ec-framework-idempotent"
    run_experience_center_turn(S4_SCENARIO_ID, session_id=session_id)
    before = ec_fsm_store.get_ec_session(session_id, "s4_zero_day") or {}
    applied_before = list(before.get("applied_follow_up_ids") or [])
    again = maybe_init_agent_session(
        scenario_id=S4_SCENARIO_ID,
        session_id=session_id,
        family="s4_zero_day",
        session_record=before,
        follow_up_id=None,
    )
    assert list(again.get("applied_follow_up_ids") or []) == applied_before
