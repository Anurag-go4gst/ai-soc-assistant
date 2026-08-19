"""Generic turn dispatch for registered EC agent workflow profiles."""

from __future__ import annotations

from typing import Any

from app.demo import ec_fsm_store
from app.demo.ec_agent.registry import get_agent_profile


def handle_agent_follow_up(
    *,
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_id: str,
    agent_payload: dict[str, Any] | None,
    session_record: dict[str, Any],
) -> dict[str, Any] | None:
    profile = get_agent_profile(scenario_id)
    if profile is None:
        return None
    return profile.handle_follow_up(
        session_id=session_id,
        family=family,
        scenario_id=scenario_id,
        follow_up_id=follow_up_id,
        agent_payload=agent_payload,
        session_record=session_record,
    )


def maybe_init_agent_session(
    *,
    scenario_id: str,
    session_id: str,
    family: str,
    session_record: dict[str, Any],
    follow_up_id: str | None,
) -> dict[str, Any]:
    """Initialize agent_state and optional plan-preread follow-ups on first turn."""
    profile = get_agent_profile(scenario_id)
    if profile is None:
        return session_record
    if follow_up_id:
        return session_record
    if list(session_record.get("applied_follow_up_ids") or []):
        return session_record

    profile.init_session(session_id, family, scenario_id)
    record = session_record
    for auto_id in profile.plan_preread_follow_ups:
        record = ec_fsm_store.upsert_ec_session(
            session_id,
            family,
            scenario_id=scenario_id,
            applied_follow_up_id=auto_id,
        )
    return record
