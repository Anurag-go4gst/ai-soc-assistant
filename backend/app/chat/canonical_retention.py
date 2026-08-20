"""Bounded retention purge for canonical handoffs and planning events (item 28)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.chat.canonical_db import canonical_db_disabled, run_on_canonical_loop
from app.chat.planning_telemetry_policy import (
    AUDIT_CRITICAL_PLANNING_EVENTS,
    DIAGNOSTIC_PLANNING_EVENTS,
)
from app.config import settings

_LOGGER = logging.getLogger("ai_soc.canonical_retention")

# Statuses that must never be purged while ``expires_at`` is still in the future.
_ACTIVE_HANDOFF_STATUSES: frozenset[str] = frozenset(
    {
        "created",
        "awaiting_clarification",
        "awaiting_investigation_plan",
        "resumed",
        "planning",
        "executing",
        "in_progress",
        "clarification_required",
    }
)

# Terminal rows eligible once ``expires_at`` is past the grace cutoff.
_TERMINAL_HANDOFF_STATUSES: frozenset[str] = frozenset(
    {
        "completed",
        "failed",
        "expired",
        "plan_committed",
    }
)

_LAST_PURGE_SUMMARY: dict[str, Any] | None = None


@dataclass(frozen=True)
class CanonicalPurgeResult:
    handoffs_deleted: int
    diagnostic_events_deleted: int
    audit_events_deleted: int
    duration_ms: int
    error_category: str | None = None

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "handoffs_deleted": self.handoffs_deleted,
            "diagnostic_events_deleted": self.diagnostic_events_deleted,
            "audit_events_deleted": self.audit_events_deleted,
            "duration_ms": self.duration_ms,
            "error_category": self.error_category,
        }


def last_purge_summary() -> dict[str, Any] | None:
    return dict(_LAST_PURGE_SUMMARY) if _LAST_PURGE_SUMMARY is not None else None


def retention_policy_snapshot() -> dict[str, Any]:
    """Documented retention windows for operators and tests."""
    return {
        "handoff_grace_hours": handoff_grace_hours(),
        "handoff_terminal_statuses": sorted(_TERMINAL_HANDOFF_STATUSES),
        "handoff_active_statuses": sorted(_ACTIVE_HANDOFF_STATUSES),
        "diagnostic_event_retention_days": diagnostic_event_retention_days(),
        "audit_event_retention_days": audit_event_retention_days(),
        "purge_batch_size": purge_batch_size(),
        "ai_trace_runs_automated_purge": False,
    }


def handoff_grace_hours() -> int:
    return max(1, int(settings.ai_soc_canonical_handoff_retention_grace_hours))


def diagnostic_event_retention_days() -> int:
    return max(1, int(settings.ai_soc_canonical_planning_event_diagnostic_retention_days))


def audit_event_retention_days() -> int:
    return max(
        diagnostic_event_retention_days(),
        int(settings.ai_soc_canonical_planning_event_audit_retention_days),
    )


def purge_batch_size() -> int:
    return max(1, int(settings.ai_soc_canonical_retention_purge_batch_size))


def purge_interval_seconds() -> int:
    return max(60, int(settings.ai_soc_canonical_retention_purge_interval_seconds))


def purge_enabled() -> bool:
    return bool(settings.ai_soc_canonical_retention_purge_enabled)


def _handoff_purge_cutoff(*, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current - timedelta(hours=handoff_grace_hours())


def _diagnostic_event_cutoff(*, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current - timedelta(days=diagnostic_event_retention_days())


def _audit_event_cutoff(*, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current - timedelta(days=audit_event_retention_days())


def _record_summary(result: CanonicalPurgeResult) -> None:
    global _LAST_PURGE_SUMMARY
    _LAST_PURGE_SUMMARY = {
        **result.to_log_dict(),
        "recorded_at": datetime.now(UTC).isoformat(),
    }


async def _purge_handoffs_batch(
    conn: asyncpg.Connection,
    *,
    cutoff: datetime,
    batch_size: int,
    now: datetime,
) -> int:
    terminal_statuses = list(_TERMINAL_HANDOFF_STATUSES)
    rows = await conn.fetch(
        """
        WITH eligible AS (
            SELECT h.id
            FROM canonical_handoffs h
            WHERE h.expires_at < $1::timestamptz
              AND (
                h.status = ANY($2::text[])
                OR h.status = 'awaiting_clarification'
              )
              AND NOT EXISTS (
                SELECT 1
                FROM canonical_handoffs live
                WHERE live.handoff_id = h.handoff_id
                  AND live.expires_at >= $3::timestamptz
              )
              AND NOT EXISTS (
                SELECT 1
                FROM canonical_execution_idempotency lease
                WHERE lease.handoff_id = h.handoff_id
                  AND lease.handoff_version = h.handoff_version
                  AND lease.status = 'running'
                  AND (
                    lease.lease_expires_at IS NULL
                    OR lease.lease_expires_at > $3::timestamptz
                  )
              )
            ORDER BY h.expires_at ASC
            LIMIT $4
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM canonical_handoffs AS deleted
        USING eligible
        WHERE deleted.id = eligible.id
        RETURNING deleted.id
        """,
        cutoff,
        terminal_statuses,
        now,
        batch_size,
    )
    return len(rows)


async def _purge_events_batch(
    conn: asyncpg.Connection,
    *,
    cutoff: datetime,
    allowed_events: frozenset[str],
    batch_size: int,
    now: datetime,
) -> int:
    if not allowed_events:
        return 0
    rows = await conn.fetch(
        """
        WITH eligible AS (
            SELECT e.id
            FROM canonical_planning_events e
            WHERE e.created_at < $1::timestamptz
              AND e.event = ANY($2::text[])
              AND NOT EXISTS (
                SELECT 1
                FROM canonical_handoffs h
                WHERE h.handoff_id IS NOT DISTINCT FROM e.handoff_id
                  AND h.handoff_version IS NOT DISTINCT FROM e.handoff_version
                  AND h.expires_at >= $3::timestamptz
              )
              AND NOT EXISTS (
                SELECT 1
                FROM canonical_handoffs chain
                WHERE chain.handoff_id IS NOT DISTINCT FROM e.handoff_id
                  AND chain.expires_at >= $3::timestamptz
              )
            ORDER BY e.created_at ASC
            LIMIT $4
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM canonical_planning_events AS deleted
        USING eligible
        WHERE deleted.id = eligible.id
        RETURNING deleted.id
        """,
        cutoff,
        sorted(allowed_events),
        now,
        batch_size,
    )
    return len(rows)


async def _purge_once_async(*, batch_size: int | None = None) -> CanonicalPurgeResult:
    started = time.perf_counter()
    if canonical_db_disabled():
        result = CanonicalPurgeResult(0, 0, 0, 0, error_category="canonical_db_disabled")
        _record_summary(result)
        return result

    limit = batch_size if batch_size is not None else purge_batch_size()
    now = datetime.now(UTC)
    handoff_cutoff = _handoff_purge_cutoff(now=now)
    diagnostic_cutoff = _diagnostic_event_cutoff(now=now)
    audit_cutoff = _audit_event_cutoff(now=now)

    from app.chat.canonical_db import canonical_unit_of_work

    handoffs_deleted = 0
    diagnostic_deleted = 0
    audit_deleted = 0
    try:
        async with canonical_unit_of_work() as conn:
            if conn is None:
                result = CanonicalPurgeResult(0, 0, 0, 0, error_category="canonical_db_unavailable")
                _record_summary(result)
                return result
            diagnostic_deleted = await _purge_events_batch(
                conn,
                cutoff=diagnostic_cutoff,
                allowed_events=DIAGNOSTIC_PLANNING_EVENTS,
                batch_size=limit,
                now=now,
            )
            audit_deleted = await _purge_events_batch(
                conn,
                cutoff=audit_cutoff,
                allowed_events=AUDIT_CRITICAL_PLANNING_EVENTS,
                batch_size=limit,
                now=now,
            )
            handoffs_deleted = await _purge_handoffs_batch(
                conn,
                cutoff=handoff_cutoff,
                batch_size=limit,
                now=now,
            )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = CanonicalPurgeResult(
            handoffs_deleted,
            diagnostic_deleted,
            audit_deleted,
            duration_ms,
            error_category=type(exc).__name__,
        )
        _LOGGER.warning(
            "canonical_retention_purge_failed",
            extra=result.to_log_dict(),
            exc_info=True,
        )
        _record_summary(result)
        return result

    duration_ms = int((time.perf_counter() - started) * 1000)
    result = CanonicalPurgeResult(
        handoffs_deleted,
        diagnostic_deleted,
        audit_deleted,
        duration_ms,
        error_category=None,
    )
    if handoffs_deleted or diagnostic_deleted or audit_deleted:
        _LOGGER.info("canonical_retention_purge_completed", extra=result.to_log_dict())
    else:
        _LOGGER.debug("canonical_retention_purge_noop", extra=result.to_log_dict())
    _record_summary(result)
    return result


def run_canonical_retention_purge(*, batch_size: int | None = None) -> CanonicalPurgeResult:
    """Run one bounded purge batch on the canonical DB loop."""
    return run_on_canonical_loop(_purge_once_async(batch_size=batch_size))


def run_canonical_retention_purge_until_idle(
    *,
    batch_size: int | None = None,
    max_batches: int = 100,
) -> CanonicalPurgeResult:
    """Run repeated bounded batches until a batch deletes nothing or ``max_batches`` is hit."""
    totals = CanonicalPurgeResult(0, 0, 0, 0)
    started = time.perf_counter()
    for _ in range(max(1, max_batches)):
        result = run_canonical_retention_purge(batch_size=batch_size)
        totals = CanonicalPurgeResult(
            totals.handoffs_deleted + result.handoffs_deleted,
            totals.diagnostic_events_deleted + result.diagnostic_events_deleted,
            totals.audit_events_deleted + result.audit_events_deleted,
            totals.duration_ms + result.duration_ms,
            error_category=result.error_category,
        )
        if result.error_category is not None:
            break
        if (
            result.handoffs_deleted == 0
            and result.diagnostic_events_deleted == 0
            and result.audit_events_deleted == 0
        ):
            break
    duration_ms = int((time.perf_counter() - started) * 1000)
    final = CanonicalPurgeResult(
        totals.handoffs_deleted,
        totals.diagnostic_events_deleted,
        totals.audit_events_deleted,
        duration_ms,
        error_category=totals.error_category,
    )
    _record_summary(final)
    return final
