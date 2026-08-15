"""Ephemeral investigation session pins — not the durable quality ledger."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config import settings

_store_lock = Lock()
_pins_by_session: dict[str, dict[str, Any]] = {}


class SessionPins(BaseModel):
    session_id: str
    last_trace_id: str | None = None
    last_alert_id: str | None = None
    last_use_case_id: str | None = None
    last_selected_live_execution_skill: str | None = None
    last_planning_or_analytic_skill: str | None = None
    last_entities: dict[str, Any] = Field(default_factory=dict)
    source_profile_slots: dict[str, str] = Field(default_factory=dict)
    last_candidate_spl: str | None = None
    last_spl_validation_status: str | None = None
    last_spl_template_status: str | None = None
    last_mitre_decision: dict[str, Any] | None = None
    last_mitre_evidence_status: dict[str, str] | None = None
    last_context_sufficiency: dict[str, Any] | None = None
    last_execution_status: str | None = None
    last_human_review_status: str | None = None
    pending_execution_confirmation: dict[str, Any] | None = None
    pending_handoff_id: str | None = None
    pending_handoff_version: int | None = None
    original_query: str | None = None
    last_rqc_redacted: dict[str, Any] | None = None
    last_investigation_outcome_ref: dict[str, Any] | None = None
    last_evidence_refs: list[str] = Field(default_factory=list)
    last_clarification_state: dict[str, Any] | None = None
    last_plan_identity: dict[str, Any] | None = None
    last_evidence_scope: dict[str, Any] | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return current >= self.expires_at

    def is_fresh(self, *, now: datetime | None = None) -> bool:
        return not self.is_expired(now=now)


def new_session_id() -> str:
    return str(uuid4())


def default_ttl() -> timedelta:
    minutes = max(1, int(settings.ai_soc_session_context_ttl_minutes))
    return timedelta(minutes=minutes)


def _session_store_dir() -> Path:
    return Path(settings.ai_soc_session_store_file_dir)


def _file_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
    return _session_store_dir() / f"{safe_id}.json"


def _read_file_pins(session_id: str) -> dict[str, Any] | None:
    path = _file_path(session_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_file_pins(session_id: str, payload: dict[str, Any]) -> None:
    """Best-effort file persist; PermissionError must never break /chat."""
    directory = _session_store_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _file_path(session_id).write_text(json.dumps(payload), encoding="utf-8")


def _delete_file_pins(session_id: str) -> None:
    path = _file_path(session_id)
    if path.exists():
        path.unlink(missing_ok=True)


def _use_file_backend() -> bool:
    return str(settings.ai_soc_session_store_backend or "memory").strip().lower() == "file"


def get_session_pins(session_id: str | None) -> SessionPins | None:
    if not session_id:
        return None
    with _store_lock:
        if _use_file_backend():
            raw = _read_file_pins(session_id)
        else:
            raw = _pins_by_session.get(session_id)
    if not raw:
        return None
    pins = SessionPins.model_validate(raw)
    if pins.is_expired():
        delete_session_pins(session_id)
        return None
    return pins


def save_session_pins(pins: SessionPins, *, refresh_ttl: bool = True) -> SessionPins:
    if refresh_ttl:
        now = datetime.now(UTC)
        ttl = default_ttl()
        updated = pins.model_copy(
            update={
                "updated_at": now,
                "expires_at": now + ttl,
            }
        )
    else:
        updated = pins
    payload = updated.model_dump(mode="json")
    with _store_lock:
        if _use_file_backend():
            try:
                _write_file_pins(updated.session_id, payload)
            except OSError:
                # Unwritable store dir (sandbox / misconfigured volume): keep
                # in-process pins so chat finalize never fails closed.
                _pins_by_session[updated.session_id] = payload
        else:
            _pins_by_session[updated.session_id] = payload
    return updated


def delete_session_pins(session_id: str | None) -> None:
    if not session_id:
        return
    with _store_lock:
        if _use_file_backend():
            _delete_file_pins(session_id)
        else:
            _pins_by_session.pop(session_id, None)


def clear_all_session_pins_for_tests() -> None:
    with _store_lock:
        if _use_file_backend():
            directory = _session_store_dir()
            if directory.exists():
                for path in directory.glob("*.json"):
                    path.unlink(missing_ok=True)
        else:
            _pins_by_session.clear()
