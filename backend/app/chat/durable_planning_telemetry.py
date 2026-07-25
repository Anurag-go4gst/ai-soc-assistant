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


def persist_planning_event(payload: dict[str, Any]) -> None:
    sanitized = minimize(payload) if isinstance(payload, dict) else {}
    if _USE_TEST_EVENTS or _disabled():
        _TEST_EVENTS.append(dict(sanitized))
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
                sanitized.get("trace_id"),
                sanitized.get("turn_id"),
                sanitized.get("session_id"),
                sanitized.get("decision_id"),
                sanitized.get("parent_decision_id"),
                sanitized.get("handoff_id"),
                sanitized.get("handoff_version"),
                sanitized.get("resource_plan_id"),
                sanitized.get("event"),
                sanitized.get("node_name"),
                sanitized.get("node_version"),
                sanitized.get("contract_version"),
                sanitized.get("status"),
                sanitized.get("duration_ms"),
                sanitized.get("error_category"),
                json.dumps(sanitized),
            )
        finally:
            await conn.close()

    try:
        asyncio.run(_write())
    except Exception:
        _LOGGER.warning("planning_event_persist_failed", exc_info=True)
        _TEST_EVENTS.append(dict(sanitized))
