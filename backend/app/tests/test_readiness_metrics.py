"""Phase 5 — per-turn / LLM counters and readiness snapshot shape."""

from __future__ import annotations

import pytest

import app.api.routes_chat as routes_chat
from app.connectors.telemetry import metrics
from app.connectors.telemetry.null import NullTelemetryConnector
from app.debug.readiness import build_debug_readiness
from app.chat import pipeline
from app.schemas.requests import ChatRequest


def test_metrics_seed_new_counters() -> None:
    metrics.reset_for_tests()
    snap = metrics.snapshot()
    for key in (
        "chat_turns_completed",
        "chat_turns_human_review",
        "chat_turns_error",
        "llm_calls_total",
        "llm_calls_timed_out",
        "llm_calls_fallback",
    ):
        assert key in snap


def test_chat_turn_increments_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes_chat, "get_telemetry_connector", lambda: NullTelemetryConnector())
    metrics.reset_for_tests()

    pipeline.build_live_chat_response(
        ChatRequest(message="summarize the alert for failed logins on host srv1", session_id="m1")
    )

    snap = metrics.snapshot()
    turns = snap["chat_turns_completed"] + snap["chat_turns_human_review"]
    assert turns == 1


def test_readiness_snapshot_shape() -> None:
    readiness = build_debug_readiness()
    assert set(readiness) >= {"telemetry", "llm", "mcp", "rag", "debug_api_enabled"}
    assert "metrics" in readiness["telemetry"]
    assert "global_write_disabled" in readiness["telemetry"]
    assert "llm_calls_total" in readiness["telemetry"]["metrics"]
