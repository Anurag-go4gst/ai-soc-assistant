"""Phase 0/1 — live /chat telemetry spine + per-turn LLM-call ledger.

Verifies the wiring (not the DB): a live chat turn opens a trace run, persists
the LLM-call records from the turn budget, closes the run with explainability
metadata, and the quality layer merges turn_id/user_id back onto the run.
"""

from __future__ import annotations

from typing import Any

import pytest

import app.api.routes_chat as routes_chat
from app.chat import pipeline
from app.connectors.mcp.base import ConnectorStatus
from app.quality.store import post_chat_response
from app.schemas.requests import ChatRequest


class CapturingTelemetry:
    mode = "capture"

    def __init__(self) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.end_calls: list[dict[str, Any]] = []
        self.llm_calls: list[dict[str, Any]] = []
        self.merge_calls: list[dict[str, Any]] = []

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="capture")

    def start_trace(self, trace_id: str | None = None, **fields: Any):
        self.start_calls.append({"trace_id": trace_id, **fields})
        from app.connectors.telemetry.base import TraceHandle

        return TraceHandle(trace_id=trace_id or "x")

    def end_trace(self, trace_id: str, status: str = "completed", **fields: Any) -> None:
        self.end_calls.append({"trace_id": trace_id, "status": status, **fields})

    def merge_run_metadata(self, trace_id: str, metadata: dict[str, Any]) -> None:
        self.merge_calls.append({"trace_id": trace_id, "metadata": metadata})

    def record_llm_call(self, trace_id: str, **fields: Any) -> None:
        self.llm_calls.append({"trace_id": trace_id, **fields})

    # Unused-but-required protocol surface for the live path.
    def record_step(self, *a: Any, **k: Any) -> None: ...
    def record_routing_decision(self, *a: Any, **k: Any) -> None: ...
    def record_routing_disagreement(self, *a: Any, **k: Any) -> None: ...
    def record_spl_validation(self, *a: Any, **k: Any) -> None: ...
    def record_mcp_execution(self, *a: Any, **k: Any) -> None: ...
    def record_rag_retrieval(self, *a: Any, **k: Any) -> None: ...
    def record_harness_result(self, *a: Any, **k: Any) -> str: return "x"


@pytest.fixture
def capturing(monkeypatch: pytest.MonkeyPatch) -> CapturingTelemetry:
    cap = CapturingTelemetry()
    # Pipeline resolves the connector via the routes_chat seam; the quality
    # layer imports it directly from the connector package. Patch both.
    import app.connectors.telemetry as telemetry_pkg

    monkeypatch.setattr(routes_chat, "get_telemetry_connector", lambda: cap)
    monkeypatch.setattr(telemetry_pkg, "get_telemetry_connector", lambda: cap)
    return cap


def test_live_chat_opens_and_closes_a_trace_run(capturing: CapturingTelemetry) -> None:
    response = pipeline.build_live_chat_response(
        ChatRequest(message="summarize the alert for failed logins on host srv1", session_id="s-spine")
    )

    assert response.trace_id
    assert len(capturing.start_calls) == 1
    assert capturing.start_calls[0]["trace_id"] == response.trace_id
    assert capturing.start_calls[0]["entrypoint"] == "chat"
    assert capturing.start_calls[0].get("started_at") is not None

    assert len(capturing.end_calls) == 1
    end = capturing.end_calls[0]
    assert end["trace_id"] == response.trace_id
    assert end["status"] in {"completed", "human_review"}
    # Explainability is carried on the run so the debug bundle is not hollow.
    assert "control_plane_trace" in end["metadata"]
    assert "selected_skill" in end["metadata"]
    assert "llm_call_count" in end["metadata"]
    assert "debug_summary" in end["metadata"]
    assert isinstance(end["metadata"]["debug_summary"], dict)
    assert "routing" in end["metadata"]["debug_summary"]


def test_llm_call_records_persisted_from_turn_budget(capturing: CapturingTelemetry) -> None:
    response = pipeline.build_live_chat_response(
        ChatRequest(message="map this alert to MITRE ATT&CK for host srv1", session_id="s-llm")
    )
    # Each captured LLM call is tied to the same trace and carries an outcome,
    # so the debug timeline can answer "which LLM ran and did it succeed".
    for call in capturing.llm_calls:
        assert call["trace_id"] == response.trace_id
        assert "outcome" in call
        assert "role" in call or call.get("kind") == "narration"
    assert capturing.end_calls[0]["metadata"]["llm_call_count"] == len(capturing.llm_calls)


def test_post_chat_response_merges_turn_id_and_user(capturing: CapturingTelemetry) -> None:
    response = pipeline.build_live_chat_response(
        ChatRequest(message="summarize the alert for failed logins on host srv1", session_id="s-merge")
    )
    finalized = post_chat_response(
        response,
        ChatRequest(message="summarize the alert for failed logins on host srv1", session_id="s-merge"),
        entrypoint="chat",
        user={"username": "alice"},
    )

    assert len(capturing.merge_calls) == 1
    merge = capturing.merge_calls[0]
    assert merge["trace_id"] == response.trace_id
    assert merge["metadata"]["turn_id"] == finalized.turn_id
    assert merge["metadata"]["user_id"] == "alice"
    assert "debug_summary" in merge["metadata"]
    assert "llm_live_calls" in merge["metadata"]
    assert "match_path" in merge["metadata"]
