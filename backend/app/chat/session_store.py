"""Ephemeral investigation session pins — not the durable quality ledger."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def get_session_pins(session_id: str | None) -> SessionPins | None:
    if not session_id:
        return None
    with _store_lock:
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
    with _store_lock:
        _pins_by_session[updated.session_id] = updated.model_dump(mode="json")
    return updated


def delete_session_pins(session_id: str | None) -> None:
    if not session_id:
        return
    with _store_lock:
        _pins_by_session.pop(session_id, None)


def clear_all_session_pins_for_tests() -> None:
    with _store_lock:
        _pins_by_session.clear()
