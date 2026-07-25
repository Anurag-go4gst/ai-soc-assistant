"""Durable persistence for canonical planning telemetry events."""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from app.chat.canonical_db import (
    append_turn_buffered_event,
    canonical_db_disabled,
    drain_turn_buffered_events,
    run_in_canonical_unit_of_work,
    run_on_canonical_loop,
)
from app.chat.planning_telemetry_policy import (
    AuditCriticalTelemetryPersistenceError,
    DiagnosticTelemetryPersistenceDegraded,
    is_audit_critical_planning_event,
    should_persist_planning_event_to_db,
)
from app.connectors.telemetry.redaction import minimize

_LOGGER = logging.getLogger("ai_soc.planning_telemetry")
_TEST_EVENTS: list[dict[str, Any]] = []
_USE_TEST_EVENTS = False


def use_test_event_store(enabled: bool = True) -> None:
    global _USE_TEST_EVENTS
    _USE_TEST_EVENTS = enabled
    if enabled:
        _TEST_EVENTS.clear()


def persisted_events() -> list[dict[str, Any]]:
    return list(_TEST_EVENTS)


def clear_persisted_events_for_tests() -> None:
    _TEST_EVENTS.clear()


#: Correlation values bound to typed columns. These must be read from the raw event,
#: never from the ``minimize()``d copy: ``minimize`` drops any key containing a
#: ``_SECRET_KEY_PARTS`` fragment, and ``session_id`` is one of them — reading the
#: column value back out of ``sanitized`` persisted NULL for every event and made
#: multi-worker correlation impossible. ``minimize`` still guards the free-form payload.
_CORRELATION_COLUMNS: tuple[str, ...] = (
    "trace_id",
    "turn_id",
    "session_id",
    "decision_id",
    "parent_decision_id",
    "handoff_id",
    "handoff_version",
    "resource_plan_id",
    "event",
    "node_name",
    "node_version",
    "contract_version",
    "status",
    "duration_ms",
    "error_category",
)


#: ``session_id`` is the client-supplied chat conversation id from ``ChatRequest`` — it is
#: NOT the auth credential (that is the signed cookie in ``app/auth/session.py``).
#: ``minimize()`` classifies it as a secret by keyword, grouping it with ``session_secret``;
#: that heuristic over-matches for this field, so correlation deliberately keeps it. Being
#: client-supplied, it is length-bounded before it reaches a column.
_MAX_CORRELATION_STR = 200


def _correlation(payload: dict[str, Any]) -> dict[str, Any]:
    correlation: dict[str, Any] = {}
    for key in _CORRELATION_COLUMNS:
        value = payload.get(key)
        correlation[key] = value[:_MAX_CORRELATION_STR] if isinstance(value, str) else value
    return correlation


def _prepare_event(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = payload if isinstance(payload, dict) else {}
    sanitized = minimize(raw) if raw else {}
    correlation = _correlation(raw)
    return sanitized, correlation


def _capture_test_event(sanitized: dict[str, Any], correlation: dict[str, Any]) -> None:
    if _USE_TEST_EVENTS:
        _TEST_EVENTS.append({**sanitized, **correlation})


def _skip_db_persist(event: str | None, *, reason: str) -> None:
    if is_audit_critical_planning_event(event):
        if reason == "canonical_db_disabled":
            _LOGGER.warning(
                "audit_critical_planning_event_not_persisted",
                extra={"planning_event": event, "reason": reason},
            )
            return
        raise AuditCriticalTelemetryPersistenceError(
            "audit_critical_planning_event_not_persisted",
            event=event,
            detail=reason,
        )
    _LOGGER.info(
        "diagnostic_planning_event_skipped",
        extra={"planning_event": event, "reason": reason},
    )


def _record_diagnostic_persist_failure(event: str | None, *, reason: str, detail: str) -> None:
    _LOGGER.warning(
        "diagnostic_planning_event_persist_failed",
        extra={
            "planning_event": event,
            "reason": reason,
            "error_category": "telemetry_persistence",
            "detail": detail,
        },
    )


async def insert_planning_event(
    conn: asyncpg.Connection,
    payload: dict[str, Any],
) -> None:
    sanitized, correlation = _prepare_event(payload)
    await conn.execute(
        """
        INSERT INTO canonical_planning_events (
            trace_id, turn_id, session_id, decision_id, parent_decision_id,
            handoff_id, handoff_version, resource_plan_id, event, node_name,
            node_version, contract_version, status, duration_ms, error_category, payload
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb
        )
        """,
        correlation["trace_id"],
        correlation["turn_id"],
        correlation["session_id"],
        correlation["decision_id"],
        correlation["parent_decision_id"],
        correlation["handoff_id"],
        correlation["handoff_version"],
        correlation["resource_plan_id"],
        correlation["event"],
        correlation["node_name"],
        correlation["node_version"],
        correlation["contract_version"],
        correlation["status"],
        correlation["duration_ms"],
        correlation["error_category"],
        json.dumps(sanitized),
    )


async def flush_buffered_planning_events_async(
    conn: asyncpg.Connection,
) -> None:
    """Flush queued events on an injected connection (composed transactions)."""
    events = drain_turn_buffered_events()
    for payload in events:
        await insert_planning_event(conn, payload)


def flush_buffered_planning_events(*, conn: asyncpg.Connection | None = None) -> None:
    """Persist queued turn events in one unit-of-work when not already transactional."""
    events = drain_turn_buffered_events()
    if not events:
        return

    persistable: list[dict[str, Any]] = []
    for payload in events:
        event_name = str(payload.get("event") or "")
        if should_persist_planning_event_to_db(event_name):
            persistable.append(payload)
            continue
        sanitized, correlation = _prepare_event(payload)
        _capture_test_event(sanitized, correlation)
        _skip_db_persist(event_name, reason="telemetry_sink_disabled")

    if not persistable:
        return

    if _USE_TEST_EVENTS:
        for payload in persistable:
            sanitized, correlation = _prepare_event(payload)
            _capture_test_event(sanitized, correlation)
        return

    if canonical_db_disabled():
        for payload in persistable:
            _skip_db_persist(str(payload.get("event")), reason="canonical_db_disabled")
        return

    if conn is not None:
        run_on_canonical_loop(flush_buffered_planning_events_async(conn))
        return

    async def _write(active_conn: asyncpg.Connection | None) -> None:
        if active_conn is None:
            return
        for payload in persistable:
            await insert_planning_event(active_conn, payload)

    try:
        run_in_canonical_unit_of_work(_write)
    except AuditCriticalTelemetryPersistenceError:
        raise
    except Exception as exc:
        for payload in persistable:
            event_name = str(payload.get("event") or "")
            if is_audit_critical_planning_event(event_name):
                raise AuditCriticalTelemetryPersistenceError(
                    "audit_critical_planning_event_batch_failed",
                    event=event_name,
                    detail=str(exc),
                ) from exc
            _record_diagnostic_persist_failure(event_name, reason="batch_persist_failed", detail=str(exc))
            raise DiagnosticTelemetryPersistenceDegraded(
                event=event_name,
                reason="batch_persist_failed",
                detail=str(exc),
            ) from exc


def persist_planning_event(
    payload: dict[str, Any],
    *,
    conn: asyncpg.Connection | None = None,
    immediate: bool = False,
) -> None:
    sanitized, correlation = _prepare_event(payload)
    event_name = str(correlation.get("event") or "")

    if not should_persist_planning_event_to_db(event_name):
        _capture_test_event(sanitized, correlation)
        _skip_db_persist(event_name, reason="telemetry_sink_disabled")
        return

    if _USE_TEST_EVENTS:
        _TEST_EVENTS.append({**sanitized, **correlation})
        return

    if canonical_db_disabled():
        _skip_db_persist(event_name, reason="canonical_db_disabled")
        return

    if conn is None and not immediate and append_turn_buffered_event(payload):
        return

    async def _persist(c: asyncpg.Connection | None) -> None:
        target = conn or c
        if target is None:
            return
        await insert_planning_event(target, payload)

    try:
        run_in_canonical_unit_of_work(_persist)
    except AuditCriticalTelemetryPersistenceError:
        raise
    except Exception as exc:
        if is_audit_critical_planning_event(event_name):
            raise AuditCriticalTelemetryPersistenceError(
                "audit_critical_planning_event_persist_failed",
                event=event_name,
                detail=str(exc),
            ) from exc
        _record_diagnostic_persist_failure(event_name, reason="persist_failed", detail=str(exc))
        raise DiagnosticTelemetryPersistenceDegraded(
            event=event_name,
            reason="persist_failed",
            detail=str(exc),
        ) from exc
