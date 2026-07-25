"""Durable canonical handoff persistence (PostgreSQL)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.config import settings
from app.connectors.telemetry.redaction import minimize

_LOGGER = logging.getLogger("ai_soc.canonical_handoff")

_TEST_STORE: dict[str, dict[str, Any]] = {}
_USE_TEST_STORE = False


def use_in_memory_store_for_tests(enabled: bool = True) -> None:
    global _USE_TEST_STORE
    _USE_TEST_STORE = enabled
    if enabled:
        _TEST_STORE.clear()


def clear_in_memory_store_for_tests() -> None:
    _TEST_STORE.clear()


def _key(handoff_id: str, handoff_version: int) -> str:
    return f"{handoff_id}:v{handoff_version}"


def _ttl_minutes() -> int:
    return max(5, int(getattr(settings, "ai_soc_handoff_store_ttl_minutes", 60)))


def _sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return minimize(payload) if isinstance(payload, dict) else {}


def _disabled() -> bool:
    url = (settings.database_url or "").strip()
    return not url or "change-me@postgres" in url


def _run(coro_factory):
    return asyncio.run(coro_factory())


async def _with_conn(fn):
    if _disabled():
        return None
    conn = await asyncpg.connect(settings.database_url, timeout=2.0)
    try:
        return await fn(conn)
    finally:
        await conn.close()


def save_handoff_record(record: CanonicalHandoffRecord, *, refresh_ttl: bool = True) -> CanonicalHandoffRecord:
    now = datetime.now(UTC)
    updated = record.model_copy(
        update={
            "updated_at": now,
            "expires_at": now + timedelta(minutes=_ttl_minutes()) if refresh_ttl else record.expires_at,
        }
    )
    payload = updated.model_dump(mode="json")

    if _USE_TEST_STORE or _disabled():
        _TEST_STORE[_key(updated.handoff_id, updated.handoff_version)] = payload
        return updated

    async def _write(conn: asyncpg.Connection) -> None:
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
            updated.handoff_id,
            updated.handoff_version,
            updated.session_id,
            updated.turn_id,
            updated.trace_id,
            updated.status,
            updated.original_query,
            updated.original_skill,
            updated.original_use_case_id,
            updated.original_answer_goal,
            updated.initial_tier,
            updated.resolved_tier,
            json.dumps(_sanitize_payload(updated.canonical_planning_input)),
            json.dumps(_sanitize_payload(updated.gap_resolution)),
            json.dumps(list(updated.unresolved_fields)),
            updated.clarification_reason,
            updated.committed_resource_plan_id,
            json.dumps(_sanitize_payload(updated.committed_resource_plan)),
            json.dumps(_sanitize_payload(updated.committed_evidence_plan)),
            json.dumps(list(updated.duplicate_call_hashes)),
            updated.retry_count,
            updated.created_at,
            updated.updated_at,
            updated.expires_at,
        )

    try:
        _run(lambda: _with_conn(_write))
    except Exception:
        _LOGGER.warning("canonical_handoff_save_failed", exc_info=True)
        _TEST_STORE[_key(updated.handoff_id, updated.handoff_version)] = payload
    return updated


def load_handoff_record(handoff_id: str, handoff_version: int) -> CanonicalHandoffRecord | None:
    key = _key(handoff_id, handoff_version)
    if _USE_TEST_STORE:
        raw = _TEST_STORE.get(key)
        return CanonicalHandoffRecord.model_validate(raw) if raw else None

    async def _read(conn: asyncpg.Connection) -> dict[str, Any] | None:
        row = await conn.fetchrow(
            """
            SELECT * FROM canonical_handoffs
            WHERE handoff_id = $1 AND handoff_version = $2 AND expires_at > now()
            """,
            handoff_id,
            handoff_version,
        )
        return dict(row) if row else None

    raw: dict[str, Any] | None
    if _disabled():
        raw = _TEST_STORE.get(key)
    else:
        try:
            raw = _run(lambda: _with_conn(_read))
        except Exception:
            _LOGGER.warning("canonical_handoff_load_failed", exc_info=True)
            raw = _TEST_STORE.get(key)
    if not raw:
        return None
    return CanonicalHandoffRecord.model_validate(_to_record_dict(raw))


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
        "canonical_planning_input": row.get("canonical_planning_input"),
        "gap_resolution": row.get("gap_resolution"),
        "unresolved_fields": row.get("unresolved_fields") or [],
        "clarification_reason": row.get("clarification_reason"),
        "committed_resource_plan_id": row.get("committed_resource_plan_id"),
        "committed_resource_plan": row.get("committed_resource_plan"),
        "committed_evidence_plan": row.get("committed_evidence_plan"),
        "duplicate_call_hashes": row.get("duplicate_call_hashes") or [],
        "retry_count": row.get("retry_count") or 0,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "expires_at": row.get("expires_at"),
    }
