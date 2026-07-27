"""Transactional clarification handoff resumption (plan item 19)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.chat.canonical_db import run_in_canonical_unit_of_work
from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.chat.canonical_handoff_repository import (
    HandoffPersistenceError,
    fetch_handoff_record,
    in_memory_handoff_store_enabled,
    load_handoff_record,
    load_pending_for_update,
    memory_handoff_lock,
    persist_handoff_record,
    supersede_version,
    test_store_read,
    test_store_write,
)
from app.config import settings


class ClarificationResumeError(Exception):
    """Clarification handoff cannot be resumed under current controls."""

    def __init__(self, reason: str, *, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail or reason
        super().__init__(self.reason)


@dataclass(frozen=True)
class ClarificationResumeResult:
    prior_version: CanonicalHandoffRecord
    record: CanonicalHandoffRecord
    merged_canonical: dict[str, Any]
    idempotent_replay: bool = False


def _ttl_minutes() -> int:
    return max(5, int(getattr(settings, "ai_soc_handoff_store_ttl_minutes", 60)))


def merge_user_clarification(
    record: CanonicalHandoffRecord,
    user_answer: str,
) -> dict[str, Any]:
    """Merge clarification answer into known field values without re-classifying."""
    canonical = dict(record.canonical_planning_input or {})
    detail = dict(canonical.get("detail_state") or {})
    field_values = dict(detail.get("field_values") or {})
    field_sources = dict(detail.get("field_sources") or {})
    unresolved = list(record.unresolved_fields or [])
    if unresolved:
        target = unresolved[0]
        field_values[target] = user_answer.strip()
        field_sources[target] = "user"
    detail["field_values"] = field_values
    detail["field_sources"] = field_sources
    detail["present_fields"] = list(dict.fromkeys([*detail.get("present_fields", []), *field_values.keys()]))
    detail["missing_fields"] = [k for k in detail.get("missing_fields", []) if k not in field_values]
    canonical["detail_state"] = detail
    return canonical


def validate_pending_for_resume(
    pending: CanonicalHandoffRecord | None,
    *,
    session_id: str | None,
) -> None:
    if pending is None:
        raise ClarificationResumeError("handoff_not_found")
    if pending.is_expired():
        raise ClarificationResumeError("handoff_expired")
    normalized = pending.normalized_status()
    if normalized == "plan_committed":
        raise ClarificationResumeError("handoff_already_completed")
    if normalized in {"failed", "expired"}:
        raise ClarificationResumeError("handoff_not_resumable")
    if normalized != "awaiting_clarification":
        raise ClarificationResumeError("handoff_not_pending")
    if session_id and pending.session_id and session_id != pending.session_id:
        raise ClarificationResumeError("session_ownership_mismatch")


def build_resumed_record(
    pending: CanonicalHandoffRecord,
    *,
    next_version: int,
    merged_canonical: dict[str, Any],
    session_id: str | None,
    trace_id: str | None,
) -> CanonicalHandoffRecord:
    now = datetime.now(UTC)
    merged_fields = (merged_canonical.get("detail_state") or {}).get("field_values") or {}
    remaining_unresolved = [field for field in pending.unresolved_fields if field not in merged_fields]
    return CanonicalHandoffRecord(
        handoff_id=pending.handoff_id,
        handoff_version=next_version,
        status="in_progress",
        trace_id=trace_id or pending.trace_id,
        session_id=session_id or pending.session_id,
        original_query=pending.original_query,
        original_skill=pending.original_skill,
        original_use_case_id=pending.original_use_case_id,
        original_answer_goal=pending.original_answer_goal,
        initial_tier=pending.initial_tier,
        resolved_tier=pending.resolved_tier,
        canonical_planning_input=merged_canonical,
        gap_resolution=pending.gap_resolution,
        unresolved_fields=remaining_unresolved,
        clarification_reason=pending.clarification_reason,
        duplicate_call_hashes=list(pending.duplicate_call_hashes),
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=_ttl_minutes()),
    )


async def _merge_clarification_answer_db(
    conn: asyncpg.Connection,
    *,
    handoff_id: str,
    handoff_version: int,
    user_answer: str,
    session_id: str | None,
    trace_id: str | None,
) -> ClarificationResumeResult:
    next_version = handoff_version + 1
    existing_next = await fetch_handoff_record(conn, handoff_id, next_version)
    if existing_next:
        from app.chat.canonical_handoff_repository import handoff_record_from_row

        record = handoff_record_from_row(existing_next)
        pending = await load_pending_for_update(conn, handoff_id, handoff_version)
        if pending is None:
            pending = await fetch_handoff_record(conn, handoff_id, handoff_version)
            pending = handoff_record_from_row(pending) if pending else None
        if pending is None:
            raise ClarificationResumeError("handoff_not_found")
        return ClarificationResumeResult(
            prior_version=pending,
            record=record,
            merged_canonical=dict(record.canonical_planning_input or {}),
            idempotent_replay=True,
        )

    pending = await load_pending_for_update(conn, handoff_id, handoff_version)
    validate_pending_for_resume(pending, session_id=session_id)
    assert pending is not None

    merged = merge_user_clarification(pending, user_answer)
    await supersede_version(conn, pending)
    new_record = build_resumed_record(
        pending,
        next_version=next_version,
        merged_canonical=merged,
        session_id=session_id,
        trace_id=trace_id,
    )
    await persist_handoff_record(conn, new_record)
    return ClarificationResumeResult(
        prior_version=pending,
        record=new_record,
        merged_canonical=merged,
        idempotent_replay=False,
    )


def _merge_clarification_answer_memory(
    *,
    handoff_id: str,
    handoff_version: int,
    user_answer: str,
    session_id: str | None,
    trace_id: str | None,
) -> ClarificationResumeResult:
    next_version = handoff_version + 1
    existing_next = load_handoff_record(handoff_id, next_version)
    if existing_next is not None:
        pending = load_handoff_record(handoff_id, handoff_version)
        if pending is None:
            raise ClarificationResumeError("handoff_not_found")
        return ClarificationResumeResult(
            prior_version=pending,
            record=existing_next,
            merged_canonical=dict(existing_next.canonical_planning_input or {}),
            idempotent_replay=True,
        )

    pending = load_handoff_record(handoff_id, handoff_version)
    validate_pending_for_resume(pending, session_id=session_id)
    assert pending is not None

    merged = merge_user_clarification(pending, user_answer)
    superseded = pending.model_copy(update={"status": "resumed", "updated_at": datetime.now(UTC)})
    test_store_write(handoff_id, handoff_version, superseded)

    new_record = build_resumed_record(
        pending,
        next_version=next_version,
        merged_canonical=merged,
        session_id=session_id,
        trace_id=trace_id,
    )
    test_store_write(handoff_id, next_version, new_record)
    return ClarificationResumeResult(
        prior_version=pending,
        record=new_record,
        merged_canonical=merged,
        idempotent_replay=False,
    )


def merge_clarification_answer(
    *,
    handoff_id: str,
    handoff_version: int,
    user_answer: str,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> ClarificationResumeResult:
    """Load pending handoff under lock, merge answer, and advance version once."""
    if in_memory_handoff_store_enabled():
        with memory_handoff_lock(handoff_id):
            return _merge_clarification_answer_memory(
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                user_answer=user_answer,
                session_id=session_id,
                trace_id=trace_id,
            )

    from app.chat.canonical_handoff_repository import canonical_db_disabled, _raise_persistence_error

    if canonical_db_disabled():
        _raise_persistence_error("handoff_resume")

    async def _txn(conn: asyncpg.Connection | None) -> ClarificationResumeResult:
        if conn is None:
            _raise_persistence_error("handoff_resume")
        return await _merge_clarification_answer_db(
            conn,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            user_answer=user_answer,
            session_id=session_id,
            trace_id=trace_id,
        )

    return run_in_canonical_unit_of_work(_txn)


def resume_clarification_handoff(
    *,
    handoff_id: str,
    handoff_version: int,
    user_answer: str,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> ClarificationResumeResult:
    """Resume a pending clarification inside one canonical unit of work."""
    return merge_clarification_answer(
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        user_answer=user_answer,
        session_id=session_id,
        trace_id=trace_id,
    )
