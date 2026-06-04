"""SSE streaming for live chat progress and final response."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.session import require_auth
from app.chat.pipeline import build_live_chat_response
from app.quality.store import post_chat_response
from app.chat.progress_events import (
    QueueProgressBridge,
    _STREAM_CLOSED,
    format_sse,
    sse_keepalive,
)
from app.chat_commands import is_clear_chat_command
from app.config import settings
from app.demo.scenarios import resolve_demo_scenario_id_for_query, run_demo_scenario
from app.llm.clients.local_chat_errors import local_chat_error_code, user_message_for_local_chat_error
from app.schemas.requests import ChatRequest
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


def _run_chat_with_progress(request: ChatRequest, bridge: QueueProgressBridge) -> None:
    reporter = bridge.reporter()
    try:
        if settings.ai_soc_live_chat_ec_parity_enabled:
            scenario_id = resolve_demo_scenario_id_for_query(request.message)
            if scenario_id:
                response = _finalize_stream_response(
                    request,
                    PlaceholderResponse(**run_demo_scenario(scenario_id)),
                )
                reporter.final(response)
                return

        if settings.langgraph_orchestration_enabled:
            from app.graph.chat_workflow import run_chat_via_langgraph

            response = _finalize_stream_response(request, run_chat_via_langgraph(request))
            reporter.final(response)
            return

        response = _finalize_stream_response(request, build_live_chat_response(request, progress=reporter))
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


async def _sse_event_stream(request: ChatRequest) -> AsyncIterator[str]:
    bridge = QueueProgressBridge()
    loop = asyncio.get_running_loop()
    worker = loop.run_in_executor(_executor, _run_chat_with_progress, request, bridge)

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
        exc = worker.exception()
        if exc is not None:
            logger.error("chat stream worker raised after SSE loop: %s", exc)


@router.post("/chat/stream", dependencies=[Depends(require_auth)])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    if is_clear_chat_command(request.message):
        payload = _clear_response(request).model_dump(mode="json")

        async def clear_events() -> AsyncIterator[str]:
            yield format_sse({"type": "progress", "stage": "queued", "label": "Queued"})
            yield format_sse({"type": "final", "stage": "completed", "label": "Completed", "response": payload})

        return StreamingResponse(clear_events(), media_type="text/event-stream")

    return StreamingResponse(
        _sse_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
