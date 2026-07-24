"""Stream + Resource Planner trace lifecycle parity with /chat."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import routes_chat_stream as stream_mod
from app.chat.pipeline import persist_chat_admission
from app.chat.progress_events import QueueProgressBridge, _STREAM_CLOSED
from app.connectors.telemetry.base import TraceHandle
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


class CapturingTelemetry:
    mode = "capture"

    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.end_calls: list[dict[str, Any]] = []
        self.merge_calls: list[dict[str, Any]] = []

    def health(self):
        from app.connectors.mcp.base import ConnectorStatus

        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="capture")

    def start_trace(self, trace_id: str | None = None, **fields: Any) -> TraceHandle:
        self.start_calls.append({"trace_id": trace_id, **fields})
        return TraceHandle(trace_id=trace_id or "x")

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        self.end_calls.append({"trace_id": trace_id, "status": status, **fields})

    def merge_run_metadata(self, trace_id: str, metadata: dict[str, Any]) -> None:
        self.merge_calls.append({"trace_id": trace_id, "metadata": metadata})

    def reap_stale_running_runs(self, *, older_than_seconds: int = 900) -> None:
        return None

    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_routing_decision(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_routing_disagreement(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_mcp_execution(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_rag_retrieval(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_llm_call(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_harness_result(self, *args: Any, **kwargs: Any) -> str:
        return "x"


@pytest.fixture
def capturing(monkeypatch: pytest.MonkeyPatch) -> CapturingTelemetry:
    cap = CapturingTelemetry()
    import app.connectors.telemetry as telemetry_pkg
    import app.api.routes_chat as routes_chat

    monkeypatch.setattr(routes_chat, "get_telemetry_connector", lambda: cap)
    monkeypatch.setattr(telemetry_pkg, "get_telemetry_connector", lambda: cap)
    return cap


def test_stream_creates_trace_admission_row(
    monkeypatch: pytest.MonkeyPatch,
    capturing: CapturingTelemetry,
) -> None:
    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_chat_via_resource_planner_graph",
        lambda *a, **k: PlaceholderResponse(trace_id="stream-t1", message="ok", note="n"),
    )
    monkeypatch.setattr(stream_mod, "_finalize_stream_response", lambda request, response: response)
    monkeypatch.setattr(stream_mod.settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(stream_mod.settings, "langgraph_orchestration_enabled", True)

    bridge = QueueProgressBridge()
    stream_mod._run_chat_with_progress(
        ChatRequest(message="hello"),
        bridge,
        trace_id="stream-t1",
        user={"role": "analyst"},
    )
    assert any(call["trace_id"] == "stream-t1" for call in capturing.start_calls)
    assert any(call.get("entrypoint") == "chat_stream" for call in capturing.start_calls)


def test_stream_trace_id_matches_response(
    monkeypatch: pytest.MonkeyPatch,
    capturing: CapturingTelemetry,
) -> None:
    def fake_rp_graph(request: ChatRequest, **kwargs: Any) -> PlaceholderResponse:
        from app.connectors.telemetry.log_context import current_trace_id

        return PlaceholderResponse(trace_id=current_trace_id(), message="ok", note="n")

    monkeypatch.setattr(
        "app.graph.resource_planner_graph.run_chat_via_resource_planner_graph",
        fake_rp_graph,
    )
    monkeypatch.setattr(stream_mod, "_finalize_stream_response", lambda request, response: response)
    monkeypatch.setattr(stream_mod.settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(stream_mod.settings, "langgraph_orchestration_enabled", True)

    bridge = QueueProgressBridge()
    stream_mod._run_chat_with_progress(
        ChatRequest(message="hello"),
        bridge,
        trace_id="stream-match-id",
        user={"role": "analyst"},
    )
    events: list[dict] = []
    while True:
        item = bridge.drain(block=False, timeout=None)
        if item is None:
            break
        if item is _STREAM_CLOSED:
            break
        events.append(item)
    start_ids = {call["trace_id"] for call in capturing.start_calls}
    assert "stream-match-id" in start_ids
    final = next((event for event in events if event.get("type") == "final"), None)
    assert final is not None
    assert final["response"]["trace_id"] == "stream-match-id"


def test_resource_planner_chat_path_calls_end_trace(
    monkeypatch: pytest.MonkeyPatch,
    capturing: CapturingTelemetry,
) -> None:
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

    monkeypatch.setattr(stream_mod.settings, "control_plane_enabled", False)
    monkeypatch.setattr(stream_mod.settings, "langgraph_orchestration_enabled", True)

    response = run_chat_via_resource_planner_graph(
        ChatRequest(message="Show SOP for brute-force investigation", session_id="lg-end"),
    )
    assert response.trace_id
    assert capturing.end_calls
    assert capturing.end_calls[-1]["status"] in {"completed", "human_review"}


def test_completed_turn_not_reaped_abandoned(capturing: CapturingTelemetry) -> None:
    trace_id = "completed-not-abandoned"
    capturing.start_trace(trace_id, entrypoint="chat_stream", status="running", started_at=datetime.now(UTC))
    capturing.end_trace(trace_id, status="completed")
    capturing.reap_stale_running_runs(older_than_seconds=0)
    assert capturing.end_calls[-1]["status"] == "completed"
