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
