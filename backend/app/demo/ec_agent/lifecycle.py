"""Shared lifecycle vocabulary and session helpers for EC agent workflows."""

from __future__ import annotations

from typing import Any

from app.demo import ec_actions, ec_fsm_store

LIFECYCLE_PLAN_READY = "PLAN_READY"
LIFECYCLE_INVESTIGATING = "INVESTIGATING"
LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL = "INVESTIGATION_NEEDS_APPROVAL"
LIFECYCLE_INVESTIGATION_COMPLETE = "INVESTIGATION_COMPLETE"
LIFECYCLE_REMEDIATION_PLAN_READY = "REMEDIATION_PLAN_READY"
LIFECYCLE_REMEDIATION_APPROVED = "REMEDIATION_APPROVED"
LIFECYCLE_REMEDIATING = "REMEDIATING"
LIFECYCLE_VERIFYING = "VERIFYING"
LIFECYCLE_COMPLETE = "COMPLETE"
LIFECYCLE_BLOCKED = "BLOCKED"
LIFECYCLE_PARTIAL = "PARTIAL"
LIFECYCLE_FAILED = "FAILED"
LIFECYCLE_CANCELLED = "CANCELLED"

LIFECYCLE_PHASES = frozenset(
    {
        LIFECYCLE_PLAN_READY,
        LIFECYCLE_INVESTIGATING,
        LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL,
        LIFECYCLE_INVESTIGATION_COMPLETE,
        LIFECYCLE_REMEDIATION_PLAN_READY,
        LIFECYCLE_REMEDIATION_APPROVED,
        LIFECYCLE_REMEDIATING,
        LIFECYCLE_VERIFYING,
        LIFECYCLE_COMPLETE,
        LIFECYCLE_BLOCKED,
        LIFECYCLE_PARTIAL,
        LIFECYCLE_FAILED,
        LIFECYCLE_CANCELLED,
    }
)


def workflow_phase(lifecycle: str) -> str:
    if lifecycle in {
        LIFECYCLE_PLAN_READY,
        LIFECYCLE_INVESTIGATING,
        LIFECYCLE_INVESTIGATION_NEEDS_APPROVAL,
    }:
        return "plan"
    if lifecycle == LIFECYCLE_INVESTIGATION_COMPLETE:
        return "investigation_complete"
    return "remediation"


def get_agent_state(
    session_id: str | None,
    family: str,
    *,
    default_state: dict[str, Any],
) -> dict[str, Any]:
    session = ec_fsm_store.get_ec_session(session_id, family) if session_id else None
    state = dict((session or {}).get("agent_state") or default_state)
    if "lifecycle" not in state:
        state["lifecycle"] = LIFECYCLE_PLAN_READY
    return state


def save_agent_state(
    session_id: str,
    family: str,
    *,
    scenario_id: str,
    agent_state: dict[str, Any],
) -> dict[str, Any]:
    return ec_fsm_store.upsert_ec_session(
        session_id,
        family,
        scenario_id=scenario_id,
        agent_state=agent_state,
    )


def apply_follow_ups(
    session_id: str,
    family: str,
    scenario_id: str,
    follow_up_ids: list[str],
) -> dict[str, Any]:
    record = ec_fsm_store.get_ec_session(session_id, family) or {}
    for follow_up_id in follow_up_ids:
        record = ec_fsm_store.apply_follow_up(
            session_id,
            family,
            scenario_id=scenario_id,
            follow_up_id=follow_up_id,
        )
    return record


def auto_execute_pending_actions(session_id: str, scenario_id: str, *, max_rounds: int = 12) -> int:
    """Approve and execute all pending remediation actions after envelope minted them."""
    executed = 0
    for _ in range(max_rounds):
        pending = [
            item
            for item in ec_actions.list_actions_for_session(session_id, scenario_id)
            if item.state == "APPROVAL_REQUIRED"
        ]
        if not pending:
            break
        for action in pending:
            approved = ec_actions.approve_action(action.action_id)
            ec_actions.execute_action(approved.action_id)
            executed += 1
    return executed


def selected_follow_ups(step_defs: tuple[dict[str, Any], ...], selected_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    for step in step_defs:
        if step["id"] not in selected_ids:
            continue
        follow_up_id = step.get("follow_up_id")
        if follow_up_id and follow_up_id not in ordered:
            ordered.append(follow_up_id)
    return ordered
