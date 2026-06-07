from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.session import require_auth
import time

from app.chat.progress_events import ProgressReporter, QueueProgressBridge, _STREAM_CLOSED
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


def test_chat_stream_waits_for_slow_worker(
    monkeypatch: pytest.MonkeyPatch,
    authed_client: TestClient,
) -> None:
    from app.api import routes_chat_stream as stream_mod

    def fake_run(request: ChatRequest, bridge) -> None:
        reporter = bridge.reporter()
        reporter.stage("queued")
        time.sleep(0.9)
        reporter.final(PlaceholderResponse(trace_id="slow", message="done", note="n"))

    monkeypatch.setattr(stream_mod, "_run_chat_with_progress", fake_run)
    response = authed_client.post("/api/chat/stream", json={"message": "slow"})
    assert response.status_code == 200
    assert '"type": "final"' in response.text
    assert "slow" in response.text


def test_chat_stream_clear_command(authed_client: TestClient) -> None:
    response = authed_client.post("/api/chat/stream", json={"message": "/clear"})
    assert response.status_code == 200
    body = response.text
    assert '"type": "final"' in body
    assert '"stage": "completed"' in body


def test_chat_stream_emits_progress_before_final(
    monkeypatch: pytest.MonkeyPatch,
    authed_client: TestClient,
) -> None:
    from app.api import routes_chat_stream as stream_mod

    seen: list[str] = []

    def fake_run(request: ChatRequest, bridge) -> None:
        reporter = bridge.reporter()
        reporter.stage("understanding_query")
        reporter.stage("generating_answer")
        reporter.heartbeat("generating_answer", "Still generating the final governed answer...")
        reporter.final(
            PlaceholderResponse(trace_id="trace-stream", message="done", note="n"),
        )

    monkeypatch.setattr(stream_mod, "_run_chat_with_progress", fake_run)

    response = authed_client.post("/api/chat/stream", json={"message": "hello"})
    assert response.status_code == 200
    stages: list[str] = []
    for chunk in response.text.split("\n\n"):
        if not chunk.startswith("data:"):
            continue
        payload = json.loads(chunk[5:].strip())
        if payload.get("type") == "progress":
            stages.append(payload["stage"])
        if payload.get("type") == "final":
            seen.append("final")
    assert "understanding_query" in stages
    assert "generating_answer" in stages
    assert seen == ["final"]
