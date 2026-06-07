from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.auth.session import require_auth
import time

from app.chat.progress_events import ProgressReporter, QueueProgressBridge, _STREAM_CLOSED
from app.chat.session_store import SessionPins, get_session_pins, save_session_pins
from app.main import app
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


@pytest.fixture
def authed_client() -> TestClient:
    app.dependency_overrides[require_auth] = lambda: "test-analyst"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_progress_reporter_emits_stage_and_heartbeat() -> None:
    events: list[dict] = []
    reporter = ProgressReporter(on_event=events.append)
    reporter.stage("queued")
    reporter.heartbeat("generating_answer", "Still generating the final governed answer...")
    reporter.heartbeat("generating_answer", "Should be throttled")
    assert events[0]["type"] == "progress"
    assert events[0]["stage"] == "queued"
    assert events[1]["type"] == "heartbeat"
    assert events[1]["stage"] == "generating_answer"


def test_progress_reporter_llm_degraded() -> None:
    events: list[dict] = []
    reporter = ProgressReporter(on_event=events.append)
    reporter.llm_degraded(code="http_105", message="LLM HTTP 105")
    assert events[-1]["type"] == "llm_degraded"
    assert events[-1]["code"] == "http_105"


def test_progress_reporter_final_payload() -> None:
    events: list[dict] = []
    reporter = ProgressReporter(on_event=events.append)
    response = PlaceholderResponse(
        trace_id="t-1",
        message="ok",
        note="note",
    )
    reporter.final(response)
    assert events[-1]["type"] == "final"
    assert events[-1]["stage"] == "completed"
    assert events[-1]["response"]["trace_id"] == "t-1"


def test_bridge_poll_timeout_is_not_stream_end() -> None:
    bridge = QueueProgressBridge()
    assert bridge.drain(block=True, timeout=0.05) is None
    bridge.reporter().stage("queued")
    item = bridge.drain(block=True, timeout=0.05)
    assert item is not None
    assert item is not _STREAM_CLOSED
    assert item["stage"] == "queued"
    bridge.close()
    assert bridge.drain(block=True, timeout=0.05) is _STREAM_CLOSED


def _bridge_events(bridge: QueueProgressBridge) -> list[dict]:
    events: list[dict] = []
    deadline = time.monotonic() + 2.0
    while True:
        item = bridge.drain(block=False, timeout=None)
        if item is None:
            if time.monotonic() > deadline:
                raise AssertionError("stream bridge did not close")
            continue
        if item is _STREAM_CLOSED:
            return events
        events.append(item)


async def _collect_stream_events(iterator) -> list[dict]:
    events: list[dict] = []
    async for chunk in iterator:
        for frame in str(chunk).split("\n\n"):
            if not frame.startswith("data:"):
                continue
            events.append(json.loads(frame[5:].strip()))
    return events


async def _collect_response_events(response) -> list[dict]:
    return await _collect_stream_events(response.body_iterator)


def test_chat_stream_waits_for_slow_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import routes_chat_stream as stream_mod

    def fake_build(request: ChatRequest, progress=None) -> PlaceholderResponse:
        reporter = progress
        assert reporter is not None
        reporter.stage("queued")
        time.sleep(0.05)
        return PlaceholderResponse(trace_id="slow", message="done", note="n")

    monkeypatch.setattr(stream_mod, "build_live_chat_response", fake_build)
    monkeypatch.setattr(stream_mod, "_finalize_stream_response", lambda request, response: response)
    monkeypatch.setattr(stream_mod.settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(stream_mod.settings, "langgraph_orchestration_enabled", False)
    bridge = QueueProgressBridge()
    stream_mod._run_chat_with_progress(ChatRequest(message="slow"), bridge)
    events = _bridge_events(bridge)
    final = next(event for event in events if event.get("type") == "final")
    assert final["response"]["trace_id"] == "slow"


def test_chat_stream_clear_command() -> None:
    from app.api import routes_chat_stream as stream_mod

    response = asyncio.run(stream_mod.chat_stream(ChatRequest(message="/clear")))
    events = asyncio.run(_collect_response_events(response))
    assert any(event.get("type") == "final" and event.get("stage") == "completed" for event in events)


def test_chat_stream_clear_command_deletes_session_pins() -> None:
    from app.api import routes_chat_stream as stream_mod

    save_session_pins(SessionPins(session_id="stream-clear-session", last_alert_id="ALT-2026-7"))
    assert get_session_pins("stream-clear-session") is not None

    response = asyncio.run(
        stream_mod.chat_stream(ChatRequest(message="/clear", session_id="stream-clear-session"))
    )

    events = asyncio.run(_collect_response_events(response))
    assert any(event.get("type") == "final" for event in events)
    assert get_session_pins("stream-clear-session") is None


def test_chat_stream_emits_progress_before_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import routes_chat_stream as stream_mod

    seen: list[str] = []

    def fake_build(request: ChatRequest, progress=None) -> PlaceholderResponse:
        reporter = progress
        assert reporter is not None
        reporter.stage("understanding_query")
        reporter.stage("generating_answer")
        reporter.heartbeat("generating_answer", "Still generating the final governed answer...")
        return PlaceholderResponse(trace_id="trace-stream", message="done", note="n")

    monkeypatch.setattr(stream_mod, "build_live_chat_response", fake_build)
    monkeypatch.setattr(stream_mod, "_finalize_stream_response", lambda request, response: response)
    monkeypatch.setattr(stream_mod.settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(stream_mod.settings, "langgraph_orchestration_enabled", False)

    bridge = QueueProgressBridge()
    stream_mod._run_chat_with_progress(ChatRequest(message="hello"), bridge)
    events = _bridge_events(bridge)
    stages: list[str] = []
    for payload in events:
        if payload.get("type") == "progress":
            stages.append(payload["stage"])
        if payload.get("type") == "final":
            seen.append("final")
    assert "understanding_query" in stages
    assert "generating_answer" in stages
    assert seen == ["final"]
