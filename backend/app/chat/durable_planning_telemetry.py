"""Durable persistence for canonical planning telemetry events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from app.config import settings
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


def _disabled() -> bool:
    url = (settings.database_url or "").strip()
    return not url or "change-me@postgres" in url


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


def persist_planning_event(payload: dict[str, Any]) -> None:
    raw = payload if isinstance(payload, dict) else {}
    sanitized = minimize(raw) if raw else {}
    correlation = _correlation(raw)
    if _USE_TEST_EVENTS or _disabled():
        _TEST_EVENTS.append({**sanitized, **correlation})
        return

    async def _write() -> None:
        conn = await asyncpg.connect(settings.database_url, timeout=1.0)
        try:
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
        finally:
            await conn.close()

    try:
        asyncio.run(_write())
    except Exception:
        # Surface loudly, never silently. The live path must not fall back into the
        # fixture store: it grows without bound across a long-running process and lets
        # production writes pollute test capture. Fail-closed classification for
        # audit-critical events is item 21b of the canonical cutover plan.
        _LOGGER.warning(
            "planning_event_persist_failed",
            exc_info=True,
            extra={
                "planning_event": correlation.get("event"),
                "planning_trace_id": correlation.get("trace_id"),
            },
        )
