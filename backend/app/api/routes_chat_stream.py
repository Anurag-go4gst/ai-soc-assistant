"""SSE streaming for live chat progress and final response."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.session import require_auth
from functools import partial

from app.chat.pipeline import build_live_chat_response, persist_chat_admission
from app.quality.store import post_chat_response
from app.chat.session_context import clear_session
from app.chat.progress_events import (
    QueueProgressBridge,
    _STREAM_CLOSED,
    format_sse,
    sse_keepalive,
)
from app.chat_commands import is_clear_chat_command
from app.config import settings
from app.llm.clients.local_chat_errors import local_chat_error_code, user_message_for_local_chat_error
from app.schemas.requests import ChatRequest
from app.connectors.telemetry.log_context import TRACE_ID_HEADER, reset_trace_id, set_trace_id
from app.schemas.responses import PlaceholderResponse

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-stream")

_POLL_TIMEOUT_S = 0.5
_KEEPALIVE_EVERY_POLLS = 4  # ~2s between comment keepalives for nginx/proxies


def _clear_response(request: ChatRequest) -> PlaceholderResponse:
    return PlaceholderResponse(
        trace_id=str(uuid4()),
        message="Chat cleared. Ask your next question when ready.",
        note="client_command:/clear",
        user_query=request.message,
    )


def _finalize_stream_response(request: ChatRequest, response: PlaceholderResponse) -> PlaceholderResponse:
    return post_chat_response(response, request, entrypoint="chat_stream")


def _run_chat_with_progress(
    request: ChatRequest,
    bridge: QueueProgressBridge,
    *,
    trace_id: str,
    user: object,
) -> None:
    reporter = bridge.reporter()
    session_role = user.get("role") if isinstance(user, dict) else None
    started_at = datetime.now(UTC)
    token = set_trace_id(trace_id)
    try:
        persist_chat_admission(trace_id, user, entrypoint="chat_stream")
        if settings.langgraph_orchestration_enabled:
            from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

            response = _finalize_stream_response(
                request,
                run_chat_via_resource_planner_graph(
                    request,
                    progress=reporter,
                    session_role=session_role,
                    entrypoint="chat_stream",
                ),
            )
            reporter.final(response)
            return

        response = _finalize_stream_response(request, build_live_chat_response(request, progress=reporter, session_role=session_role, entrypoint="chat_stream"))
        status = getattr(response.synthesis_status, "status", None) if response.synthesis_status else None
        if status == "partial_timeout":
            reporter.partial_timeout(
                response,
                reason="Final LLM synthesis timed out; showing validated intermediate result.",
            )
        elif status == "degraded" and response.synthesis_status:
            reporter.llm_degraded(
                code="live_narration_degraded",
                message=response.synthesis_status.reason,
            )
            reporter.final(response)
        else:
            reporter.final(response)
    except Exception as exc:  # noqa: BLE001 - stream must surface failure as an event
        logger.exception("chat stream worker failed")
        code = local_chat_error_code(exc)
        message = (
            user_message_for_local_chat_error(code)
            if code.startswith(("http_", "url_error", "transport_error", "base_url", "empty_"))
            else str(exc)
        )
        reporter.failed(message, code=code, recoverable=True)
    finally:
        reset_trace_id(token)
        bridge.close()


def _drain_remaining(bridge: QueueProgressBridge) -> list[dict]:
    """Non-blocking drain after the worker closes the bridge."""
    remaining: list[dict] = []
    while True:
        item = bridge.drain(block=False, timeout=None)
        if item is None:
            break
        if item is _STREAM_CLOSED:
            break
        remaining.append(item)
    return remaining


async def _sse_event_stream(
    request: ChatRequest,
    *,
    trace_id: str,
    user: object,
) -> AsyncIterator[str]:
    bridge = QueueProgressBridge()
    loop = asyncio.get_running_loop()
    worker = loop.run_in_executor(
        _executor,
        partial(_run_chat_with_progress, request, bridge, trace_id=trace_id, user=user),
    )

    polls = 0
    try:
        while True:
            item = await loop.run_in_executor(
                None,
                lambda: bridge.drain(block=True, timeout=_POLL_TIMEOUT_S),
            )
            if item is _STREAM_CLOSED:
                for payload in _drain_remaining(bridge):
                    yield format_sse(payload)
                break
            if item is not None:
                polls = 0
                yield format_sse(item)
                continue

            # Poll timeout — worker may still be running; do NOT end the stream.
            polls += 1
            if polls >= _KEEPALIVE_EVERY_POLLS:
                polls = 0
                yield sse_keepalive()

            if worker.done():
                await worker
                while True:
                    item = await loop.run_in_executor(
                        None,
                        lambda: bridge.drain(block=True, timeout=0.25),
                    )
                    if item is _STREAM_CLOSED:
                        break
                    if item is not None:
                        yield format_sse(item)
                    else:
                        break
                break
    finally:
        if worker.done():
            exc = worker.exception()
            if exc is not None:
                logger.error("chat stream worker raised after SSE loop: %s", exc)


@router.post("/chat/stream", dependencies=[Depends(require_auth)])
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    user: dict[str, Any] = Depends(require_auth),
) -> StreamingResponse:
    if is_clear_chat_command(request.message):
        clear_session(request.session_id)
        payload = _clear_response(request).model_dump(mode="json")

        async def clear_events() -> AsyncIterator[str]:
            yield format_sse({"type": "progress", "stage": "queued", "label": "Queued"})
            yield format_sse({"type": "final", "stage": "completed", "label": "Completed", "response": payload})

        return StreamingResponse(clear_events(), media_type="text/event-stream")

    trace_id = str(getattr(getattr(http_request, "state", None), "trace_id", "") or uuid4())
    return StreamingResponse(
        _sse_event_stream(request, trace_id=trace_id, user=user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            TRACE_ID_HEADER: trace_id,
        },
    )
