"""Canonical planning telemetry — correlation fields and failure handling.

``minimize()`` drops any key whose name contains a ``_SECRET_KEY_PARTS`` fragment, and
``session_id`` is one of them. Reading a column value back out of the minimized copy
persisted NULL for every event, which silently defeats multi-worker correlation.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat import durable_planning_telemetry as telemetry
from app.connectors.telemetry.redaction import minimize


@pytest.fixture(autouse=True)
def _capture() -> Any:
    telemetry.use_test_event_store(True)
    yield
    telemetry.clear_persisted_events_for_tests()
    telemetry.use_test_event_store(False)


def test_minimize_still_drops_session_id() -> None:
    """Pins the upstream behaviour this module has to work around."""
    assert "session_id" not in minimize({"session_id": "sess-1", "trace_id": "t-1"})


def test_persisted_event_retains_correlation_fields() -> None:
    telemetry.persist_planning_event(
        {
            "event": "clarification.requested",
            "trace_id": "t-1",
            "session_id": "sess-1",
            "turn_id": "turn-1",
            "handoff_id": "h-1",
            "handoff_version": 2,
            "node_name": "canonical_planning_orchestrator",
            "status": "clarification_required",
        }
    )

    (persisted,) = telemetry.persisted_events()
    assert persisted["session_id"] == "sess-1"
    assert persisted["handoff_id"] == "h-1"
    assert persisted["handoff_version"] == 2
    assert persisted["trace_id"] == "t-1"
    assert persisted["event"] == "clarification.requested"


def test_free_form_payload_is_still_redacted() -> None:
    telemetry.persist_planning_event(
        {
            "event": "detail_tool.completed",
            "session_id": "sess-2",
            "api_key": "sk-live-should-not-persist",
            "detail": {"token": "bearer-should-not-persist"},
        }
    )

    (persisted,) = telemetry.persisted_events()
    assert persisted["session_id"] == "sess-2"
    assert "api_key" not in persisted
    assert "token" not in persisted.get("detail", {})


def test_client_supplied_session_id_is_length_bounded() -> None:
    """session_id arrives from ChatRequest — bound it before it reaches a column."""
    telemetry.persist_planning_event({"event": "lane_router.decided", "session_id": "s" * 5000})

    (persisted,) = telemetry.persisted_events()
    assert len(persisted["session_id"]) == telemetry._MAX_CORRELATION_STR


def test_persist_failure_does_not_populate_fixture_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live write failure logs; it must not fall back into the fixture store."""
    telemetry.use_test_event_store(False)
    monkeypatch.setattr(telemetry, "_disabled", lambda: False)

    def _boom(coro: Any = None, *_args: Any, **_kwargs: Any) -> None:
        if hasattr(coro, "close"):
            coro.close()  # avoid "coroutine was never awaited" noise
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(telemetry.asyncio, "run", _boom)

    telemetry.persist_planning_event({"event": "response.validated", "session_id": "sess-3"})

    assert telemetry.persisted_events() == []
