"""Deterministic multi-turn FSM state for Experience Center scenarios (plan Track D2).

Only multi-turn scenarios (currently the MITRE require-input showcase) engage this FSM.
State is keyed by ``(session_id, scenario_family)`` so two parallel sessions never
cross-contaminate step state. All other EC scenarios stay one-shot and never touch this
store.

Step model for the MITRE require-input showcase:
  step 0 (no state)        -> serve the clarification turn, mark awaiting-input
  step 1 (awaiting-input)  -> on a turn that supplies the required context, advance and
                              serve the mapped-answer turn; on partial/invalid input,
                              re-serve the clarification (do NOT fall through to a wrong
                              scenario).
A fresh turn-1 query resets the step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

_store_lock = Lock()
_state_by_key: dict[tuple[str, str], dict[str, Any]] = {}
_ec_sessions: dict[tuple[str, str], dict[str, Any]] = {}

# EC FSM state is short-lived demo state; expire so a stale session can't strand a step.
_FSM_TTL = timedelta(minutes=30)


def _now() -> datetime:
    return datetime.now(UTC)


def get_step(session_id: str | None, scenario_family: str) -> int:
    """Return the active FSM step for this session+family (0 when none/expired)."""
    if not session_id:
        return 0
    key = (session_id, scenario_family)
    with _store_lock:
        record = _state_by_key.get(key)
        if not record:
            return 0
        expires_at = record.get("expires_at")
        if isinstance(expires_at, datetime) and _now() >= expires_at:
            _state_by_key.pop(key, None)
            return 0
        return int(record.get("step", 0))


def set_step(session_id: str | None, scenario_family: str, step: int) -> None:
    """Persist the FSM step for this session+family with a fresh TTL."""
    if not session_id:
        return
    key = (session_id, scenario_family)
    with _store_lock:
        _state_by_key[key] = {"step": int(step), "expires_at": _now() + _FSM_TTL}


def reset(session_id: str | None, scenario_family: str) -> None:
    """Clear any FSM state for this session+family."""
    if not session_id:
        return
    with _store_lock:
        _state_by_key.pop((session_id, scenario_family), None)


def clear_all_for_tests() -> None:
    """Test helper — drop all FSM state."""
    with _store_lock:
        _state_by_key.clear()
        _ec_sessions.clear()


def get_ec_session(session_id: str | None, family: str) -> dict[str, Any] | None:
    if not session_id:
        return None
    key = (session_id, family)
    with _store_lock:
        record = _ec_sessions.get(key)
        if not record:
            return None
        expires_at = record.get("expires_at")
        if isinstance(expires_at, datetime) and _now() >= expires_at:
            _ec_sessions.pop(key, None)
            return None
        return dict(record)


def upsert_ec_session(
    session_id: str,
    family: str,
    *,
    scenario_id: str,
    turn: int | None = None,
    pending_action_id: str | None = None,
    awaiting_external: bool | None = None,
    applied_follow_up_id: str | None = None,
) -> dict[str, Any]:
    key = (session_id, family)
    with _store_lock:
        current = _ec_sessions.get(key) or {
            "session_id": session_id,
            "family": family,
            "scenario_id": scenario_id,
            "turn": 0,
            "pending_action_id": None,
            "awaiting_external": False,
            "applied_follow_up_ids": [],
        }
        if current.get("scenario_id") not in {None, scenario_id} and current.get("family") != family:
            raise ValueError("ec_session_scenario_mismatch")
        current["scenario_id"] = scenario_id
        current["family"] = family
        current["session_id"] = session_id
        if turn is not None:
            current["turn"] = int(turn)
        if pending_action_id is not None:
            current["pending_action_id"] = pending_action_id
        if awaiting_external is not None:
            current["awaiting_external"] = bool(awaiting_external)
        if applied_follow_up_id:
            applied = list(current.get("applied_follow_up_ids") or [])
            applied.append(applied_follow_up_id)
            current["applied_follow_up_ids"] = applied
        current["expires_at"] = _now() + _FSM_TTL
        _ec_sessions[key] = current
        return dict(current)


def apply_follow_up(
    session_id: str,
    family: str,
    *,
    scenario_id: str,
    follow_up_id: str,
) -> dict[str, Any]:
    current = get_ec_session(session_id, family)
    next_turn = int((current or {}).get("turn") or 0) + 1
    return upsert_ec_session(
        session_id,
        family,
        scenario_id=scenario_id,
        turn=next_turn,
        applied_follow_up_id=follow_up_id,
    )
