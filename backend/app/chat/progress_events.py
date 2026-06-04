"""Structured chat progress events for SSE streaming (/chat/stream)."""

from __future__ import annotations

import json
import queue
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from app.schemas.responses import PlaceholderResponse

ChatProgressStage = Literal[
    "queued",
    "understanding_query",
    "classifying_intent",
    "planning_evidence",
    "route_adjudication",
    "retrieving_knowledge",
    "generating_spl",
    "checking_mcp",
    "mapping_mitre",
    "checking_sufficiency",
    "generating_answer",
    "validating_answer",
    "completed",
    "partial_timeout",
    "failed",
]

STAGE_LABELS: dict[str, str] = {
    "queued": "Queued for investigation",
    "understanding_query": "Understanding query",
    "classifying_intent": "Classifying intent",
    "planning_evidence": "Planning evidence",
    "route_adjudication": "Route adjudication",
    "retrieving_knowledge": "Retrieving knowledge",
    "generating_spl": "Generating SPL",
    "checking_mcp": "Checking MCP",
    "mapping_mitre": "Mapping MITRE",
    "checking_sufficiency": "Checking sufficiency",
    "generating_answer": "Generating answer",
    "validating_answer": "Validating answer",
    "completed": "Completed",
    "partial_timeout": "Partial timeout",
    "failed": "Failed",
}

MCP_PENDING_USER_MESSAGE = (
    "Live Splunk/MCP execution is not available; generating answer from validated plan "
    "and available knowledge."
)

_HEARTBEAT_MIN_INTERVAL_S = 3.0
_LIVE_SYNTHESIS_TIMEOUT_S = 120.0


@dataclass
class ProgressReporter:
    """Thread-safe progress emitter; optional callback for async SSE bridging."""

    on_event: Callable[[dict[str, Any]], None] | None = None
    _heartbeat_stage: str | None = field(default=None, init=False)
    _last_heartbeat_at: float = field(default=0.0, init=False)

    def _publish(self, payload: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(payload)

    def stage(
        self,
        stage: ChatProgressStage,
        *,
        label: str | None = None,
        detail: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "type": "progress",
            "stage": stage,
            "label": label or STAGE_LABELS.get(stage, stage),
        }
        if detail:
            body["detail"] = detail
        self._publish(body)
        if stage in {"generating_answer", "validating_answer"}:
            self._heartbeat_stage = stage

    def heartbeat(self, stage: ChatProgressStage, label: str) -> None:
        now = time.monotonic()
        if now - self._last_heartbeat_at < _HEARTBEAT_MIN_INTERVAL_S:
            return
        self._last_heartbeat_at = now
        self._heartbeat_stage = stage
        self._publish({"type": "heartbeat", "stage": stage, "label": label})

    def mcp_pending(self) -> None:
        self.stage("checking_mcp", detail=MCP_PENDING_USER_MESSAGE)

    def final(self, response: PlaceholderResponse) -> None:
        self._publish(
            {
                "type": "final",
                "stage": "completed",
                "label": STAGE_LABELS["completed"],
                "response": _response_payload(response),
            }
        )

    def partial_timeout(self, response: PlaceholderResponse, *, reason: str | None = None) -> None:
        payload: dict[str, Any] = {
            "type": "partial_timeout",
            "stage": "partial_timeout",
            "label": STAGE_LABELS["partial_timeout"],
            "response": _response_payload(response),
        }
        if reason:
            payload["reason"] = reason
        self._publish(payload)

    def llm_degraded(
        self,
        *,
        stage: ChatProgressStage = "generating_answer",
        code: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        self._publish(
            {
                "type": "llm_degraded",
                "stage": stage,
                "label": "Live LLM synthesis unavailable",
                "code": code,
                "message": message,
                "recoverable": recoverable,
            }
        )

    def failed(
        self,
        message: str,
        *,
        code: str | None = None,
        recoverable: bool = False,
        stage: ChatProgressStage = "failed",
    ) -> None:
        payload: dict[str, Any] = {
            "type": "failed",
            "stage": stage,
            "label": STAGE_LABELS.get(stage, STAGE_LABELS["failed"]),
            "message": message,
            "recoverable": recoverable,
        }
        if code:
            payload["code"] = code
        self._publish(payload)


def _response_payload(response: PlaceholderResponse) -> dict[str, Any]:
    try:
        return response.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - must not drop the stream without a terminal event
        return {
            "trace_id": response.trace_id,
            "message": response.message,
            "note": f"{response.note} (response serialization fallback: {exc})",
            "user_query": response.user_query,
        }


def format_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def sse_keepalive() -> str:
    return ": keepalive\n\n"


class _StreamClosed:
    """Sentinel: worker finished and the bridge is closed (not a poll timeout)."""


_STREAM_CLOSED = _StreamClosed()


@dataclass
class QueueProgressBridge:
    """Sync queue drained by an async SSE generator."""

    _queue: queue.SimpleQueue[dict[str, Any] | _StreamClosed] = field(default_factory=queue.SimpleQueue)
    _closed: bool = field(default=False, init=False)

    def reporter(self) -> ProgressReporter:
        return ProgressReporter(on_event=self._enqueue)

    def _enqueue(self, payload: dict[str, Any]) -> None:
        if not self._closed:
            self._queue.put(payload)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put(_STREAM_CLOSED)

    def drain(self, *, block: bool = True, timeout: float | None = None) -> dict[str, Any] | _StreamClosed | None:
        """Return an event dict, ``_STREAM_CLOSED`` when the worker finished, or ``None`` on poll timeout."""
        try:
            if timeout is None:
                item = self._queue.get(block=block)
            else:
                item = self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
        if item is _STREAM_CLOSED:
            return _STREAM_CLOSED
        return item


def live_synthesis_timeout_seconds() -> float:
    return _LIVE_SYNTHESIS_TIMEOUT_S
