"""Phase 3 — file/NDJSON telemetry sink write→read parity.

Writes a full turn through FileTelemetryConnector, then reads it back through
the same read_store the debug API uses, asserting the run + timeline + bundle
reconstruct (and secrets stay redacted) without any Postgres.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.connectors.telemetry import read_store
from app.connectors.telemetry.file import FileTelemetryConnector


@pytest.fixture
def file_sink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FileTelemetryConnector:
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "file")
    monkeypatch.setattr(settings, "ai_soc_telemetry_file_dir", str(tmp_path))
    return FileTelemetryConnector(directory=str(tmp_path))


def _write_turn(conn: FileTelemetryConnector, trace_id: str) -> None:
    conn.start_trace(trace_id, entrypoint="chat", status="running", user_id="analyst")
    conn.record_step(trace_id, "node.init_routing", "completed", duration_ms=11)
    conn.record_routing_decision(trace_id, selected_skill="alert_summary")
    conn.record_llm_call(trace_id, role="mitre_reasoner", outcome="completed", latency_ms=42)
    conn.record_rag_retrieval(trace_id, collection="soc_kb", result_count=3)
    conn.end_trace(
        trace_id,
        status="completed",
        metadata={"answer_mode": "full_answer", "selected_skill": "alert_summary"},
    )
    conn.merge_run_metadata(trace_id, {"turn_id": "turn-1", "user_id": "analyst"})


def test_round_trip_run_and_timeline(file_sink: FileTelemetryConnector) -> None:
    _write_turn(file_sink, "trace-file-1")

    runs = read_store.list_trace_runs(limit=10)
    assert len(runs) == 1
    run = runs[0]
    assert run["trace_id"] == "trace-file-1"
    assert run["status"] == "completed"
    assert run["entrypoint"] == "chat"
    assert run["answer_mode"] == "full_answer"
    assert run["selected_skill"] == "alert_summary"
    assert run["turn_id"] == "turn-1"
    assert run["duration_ms"] is not None and run["duration_ms"] >= 0

    timeline = read_store.fetch_trace_timeline("trace-file-1")
    assert timeline is not None
    kinds = [event["kind"] for event in timeline["events"]]
    assert {"step", "routing_decision", "llm_call", "rag_retrieval"} <= set(kinds)
    llm = next(e for e in timeline["events"] if e["kind"] == "llm_call")
    assert llm["event"]["latency_ms"] == 42


def test_bundle_carries_explainability_and_caps(file_sink: FileTelemetryConnector) -> None:
    _write_turn(file_sink, "trace-file-2")

    bundle = read_store.fetch_trace_bundle("trace-file-2", max_events=2)
    assert bundle is not None
    assert bundle["turn_id"] == "turn-1"
    assert bundle["event_truncated"] is True
    assert len(bundle["timeline"]) == 2


def test_unknown_trace_returns_none(file_sink: FileTelemetryConnector) -> None:
    _write_turn(file_sink, "trace-file-3")
    assert read_store.fetch_trace_timeline("does-not-exist") is None


def test_secret_values_redacted_in_file_events(file_sink: FileTelemetryConnector) -> None:
    file_sink.start_trace("trace-secret", entrypoint="chat")
    file_sink.record_step("trace-secret", "node.x", "completed", api_key="super-secret-token-value")
    timeline = read_store.fetch_trace_timeline("trace-secret")
    assert timeline is not None
    serialized = str(timeline["events"])
    assert "super-secret-token-value" not in serialized
