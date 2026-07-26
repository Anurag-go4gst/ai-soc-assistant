"""Durable canonical handoff persistence (PostgreSQL)."""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

import asyncpg

from app.chat.canonical_db import canonical_db_disabled, run_in_canonical_unit_of_work, run_on_canonical_loop
from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.config import settings
from app.connectors.telemetry.redaction import minimize

_LOGGER = logging.getLogger("ai_soc.canonical_handoff")

_TEST_STORE: dict[str, dict[str, Any]] = {}
_USE_TEST_STORE = False
_HANDOFF_LOCKS: dict[str, threading.Lock] = {}
_LOCK_GUARD = threading.Lock()


class HandoffPersistenceError(Exception):
    """Canonical handoff could not be durably persisted or loaded."""

    def __init__(
        self,
        reason: str,
        *,
        detail: str | None = None,
        operation: str = "handoff_persist",
    ) -> None:
        self.reason = reason
        self.detail = detail or reason
        self.operation = operation
        super().__init__(self.reason)


def use_in_memory_store_for_tests(enabled: bool = True) -> None:
    global _USE_TEST_STORE
    _USE_TEST_STORE = enabled
    if enabled:
        _TEST_STORE.clear()


def clear_in_memory_store_for_tests() -> None:
    _TEST_STORE.clear()


def in_memory_handoff_store_enabled() -> bool:
    return _USE_TEST_STORE


@contextmanager
def memory_handoff_lock(handoff_id: str) -> Iterator[None]:
    lock = _handoff_lock(handoff_id)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def test_store_write(handoff_id: str, handoff_version: int, record: CanonicalHandoffRecord) -> None:
    _TEST_STORE[_key(handoff_id, handoff_version)] = record.model_dump(mode="json")


def test_store_read(handoff_id: str, handoff_version: int) -> CanonicalHandoffRecord | None:
    raw = _TEST_STORE.get(_key(handoff_id, handoff_version))
    return CanonicalHandoffRecord.model_validate(raw) if raw else None


def _handoff_lock(handoff_id: str) -> threading.Lock:
    with _LOCK_GUARD:
        if handoff_id not in _HANDOFF_LOCKS:
            _HANDOFF_LOCKS[handoff_id] = threading.Lock()
        return _HANDOFF_LOCKS[handoff_id]


def _key(handoff_id: str, handoff_version: int) -> str:
    return f"{handoff_id}:v{handoff_version}"


def _ttl_minutes() -> int:
    return max(5, int(getattr(settings, "ai_soc_handoff_store_ttl_minutes", 60)))


def _sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return minimize(payload) if isinstance(payload, dict) else {}


def _raise_persistence_error(operation: str, exc: Exception | None = None) -> None:
    reason = "canonical_handoff_db_unavailable"
    detail = reason
    if exc is not None:
        reason = f"{operation}_failed"
        detail = str(exc)
    raise HandoffPersistenceError(reason, detail=detail, operation=operation)


def handoff_record_from_row(row: dict[str, Any]) -> CanonicalHandoffRecord:
    return CanonicalHandoffRecord.model_validate(_to_record_dict(row))


async def load_pending_for_update(
    conn: asyncpg.Connection,
    handoff_id: str,
    handoff_version: int,
) -> CanonicalHandoffRecord | None:
    row = await conn.fetchrow(
        """
        SELECT * FROM canonical_handoffs
        WHERE handoff_id = $1 AND handoff_version = $2 AND expires_at > now()
        FOR UPDATE
        """,
        handoff_id,
        handoff_version,
    )
    if not row:
        return None
    return handoff_record_from_row(dict(row))


async def supersede_version(
    conn: asyncpg.Connection,
    record: CanonicalHandoffRecord,
    *,
    new_status: str = "resumed",
) -> CanonicalHandoffRecord:
    updated = record.model_copy(
        update={
            "status": new_status,
            "updated_at": datetime.now(UTC),
        }
    )
    await persist_handoff_record(conn, updated)
    return updated


async def persist_handoff_record(
    conn: asyncpg.Connection,
    record: CanonicalHandoffRecord,
) -> None:
    await conn.execute(
        """
        INSERT INTO canonical_handoffs (
            handoff_id, handoff_version, session_id, turn_id, trace_id, status,
            original_query, original_skill, original_use_case_id, original_answer_goal,
            initial_tier, resolved_tier, canonical_planning_input, gap_resolution,
            unresolved_fields, clarification_reason, committed_resource_plan_id,
            committed_resource_plan, committed_evidence_plan, duplicate_call_hashes,
            retry_count, created_at, updated_at, expires_at
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14::jsonb,$15::jsonb,$16,$17,$18::jsonb,$19::jsonb,$20::jsonb,$21,$22,$23,$24
        )
        ON CONFLICT (handoff_id, handoff_version) DO UPDATE SET
            session_id = EXCLUDED.session_id,
            turn_id = EXCLUDED.turn_id,
            trace_id = EXCLUDED.trace_id,
            status = EXCLUDED.status,
            original_query = EXCLUDED.original_query,
            original_skill = EXCLUDED.original_skill,
            original_use_case_id = EXCLUDED.original_use_case_id,
            original_answer_goal = EXCLUDED.original_answer_goal,
            initial_tier = EXCLUDED.initial_tier,
            resolved_tier = EXCLUDED.resolved_tier,
            canonical_planning_input = EXCLUDED.canonical_planning_input,
            gap_resolution = EXCLUDED.gap_resolution,
            unresolved_fields = EXCLUDED.unresolved_fields,
            clarification_reason = EXCLUDED.clarification_reason,
            committed_resource_plan_id = EXCLUDED.committed_resource_plan_id,
            committed_resource_plan = EXCLUDED.committed_resource_plan,
            committed_evidence_plan = EXCLUDED.committed_evidence_plan,
            duplicate_call_hashes = EXCLUDED.duplicate_call_hashes,
            retry_count = EXCLUDED.retry_count,
            updated_at = EXCLUDED.updated_at,
            expires_at = EXCLUDED.expires_at
        """,
        record.handoff_id,
        record.handoff_version,
        record.session_id,
        record.turn_id,
        record.trace_id,
        record.status,
        record.original_query,
        record.original_skill,
        record.original_use_case_id,
        record.original_answer_goal,
        record.initial_tier,
        record.resolved_tier,
        json.dumps(_sanitize_payload(record.canonical_planning_input)),
        json.dumps(_sanitize_payload(record.gap_resolution)),
        json.dumps(list(record.unresolved_fields)),
        record.clarification_reason,
        record.committed_resource_plan_id,
        json.dumps(_sanitize_payload(record.committed_resource_plan)),
        json.dumps(_sanitize_payload(record.committed_evidence_plan)),
        json.dumps(list(record.duplicate_call_hashes)),
        record.retry_count,
        record.created_at,
        record.updated_at,
        record.expires_at,
    )


async def fetch_handoff_record(
    conn: asyncpg.Connection,
    handoff_id: str,
    handoff_version: int,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT * FROM canonical_handoffs
        WHERE handoff_id = $1 AND handoff_version = $2 AND expires_at > now()
        """,
        handoff_id,
        handoff_version,
    )
    return dict(row) if row else None


def save_handoff_record(
    record: CanonicalHandoffRecord,
    *,
    refresh_ttl: bool = True,
    conn: asyncpg.Connection | None = None,
) -> CanonicalHandoffRecord:
    now = datetime.now(UTC)
    updated = record.model_copy(
        update={
            "updated_at": now,
            "expires_at": now + timedelta(minutes=_ttl_minutes()) if refresh_ttl else record.expires_at,
        }
    )

    if _USE_TEST_STORE:
        _TEST_STORE[_key(updated.handoff_id, updated.handoff_version)] = updated.model_dump(mode="json")
        return updated

    if canonical_db_disabled():
        _raise_persistence_error("handoff_persist")

    async def _write(active_conn: asyncpg.Connection | None) -> None:
        target = conn or active_conn
        if target is None:
            _raise_persistence_error("handoff_persist")
        await persist_handoff_record(target, updated)

    try:
        if conn is not None:
            run_on_canonical_loop(persist_handoff_record(conn, updated))
        else:
            run_in_canonical_unit_of_work(_write)
    except HandoffPersistenceError:
        raise
    except Exception as exc:
        _LOGGER.warning("canonical_handoff_save_failed", exc_info=True)
        _raise_persistence_error("handoff_persist", exc)
    return updated


def load_handoff_record(
    handoff_id: str,
    handoff_version: int,
    *,
    conn: asyncpg.Connection | None = None,
) -> CanonicalHandoffRecord | None:
    if _USE_TEST_STORE:
        return test_store_read(handoff_id, handoff_version)

    if canonical_db_disabled():
        _raise_persistence_error("handoff_load")

    async def _read(active_conn: asyncpg.Connection | None) -> dict[str, Any] | None:
        target = conn or active_conn
        if target is None:
            _raise_persistence_error("handoff_load")
        return await fetch_handoff_record(target, handoff_id, handoff_version)

    try:
        if conn is not None:
            raw = run_on_canonical_loop(fetch_handoff_record(conn, handoff_id, handoff_version))
        else:
            raw = run_in_canonical_unit_of_work(_read)
    except HandoffPersistenceError:
        raise
    except Exception as exc:
        _LOGGER.warning("canonical_handoff_load_failed", exc_info=True)
        _raise_persistence_error("handoff_load", exc)

    if not raw:
        return None
    return handoff_record_from_row(raw)


def _coerce_json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _coerce_json_dict(value: Any) -> dict[str, Any] | None:
    coerced = _coerce_json_value(value)
    if coerced is None:
        return None
    return coerced if isinstance(coerced, dict) else None


def _coerce_json_list(value: Any) -> list[Any]:
    coerced = _coerce_json_value(value)
    if coerced is None:
        return []
    return coerced if isinstance(coerced, list) else []


def _to_record_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "handoff_id": row["handoff_id"],
        "handoff_version": row["handoff_version"],
        "status": row["status"],
        "trace_id": row.get("trace_id"),
        "session_id": row.get("session_id"),
        "turn_id": row.get("turn_id"),
        "original_query": row.get("original_query"),
        "original_skill": row.get("original_skill"),
        "original_use_case_id": row.get("original_use_case_id"),
        "original_answer_goal": row.get("original_answer_goal"),
        "initial_tier": row.get("initial_tier"),
        "resolved_tier": row.get("resolved_tier"),
        "canonical_planning_input": _coerce_json_dict(row.get("canonical_planning_input")),
        "gap_resolution": _coerce_json_dict(row.get("gap_resolution")),
        "unresolved_fields": _coerce_json_list(row.get("unresolved_fields")),
        "clarification_reason": row.get("clarification_reason"),
        "committed_resource_plan_id": row.get("committed_resource_plan_id"),
        "committed_resource_plan": _coerce_json_dict(row.get("committed_resource_plan")),
        "committed_evidence_plan": _coerce_json_dict(row.get("committed_evidence_plan")),
        "duplicate_call_hashes": _coerce_json_list(row.get("duplicate_call_hashes")),
        "retry_count": row.get("retry_count") or 0,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "expires_at": row.get("expires_at"),
    }
