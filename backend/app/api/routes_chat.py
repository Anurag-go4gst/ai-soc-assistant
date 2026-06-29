import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response

from app.auth.session import require_auth
from app.connectors.telemetry.log_context import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    coerce_request_id,
    set_trace_id,
)
from app.chat.pipeline import (
    persist_chat_admission,
    _attach_hil_soc_kb_guidance,
    _context_stage,
    _route_plan_shadow_candidate,
    _route_plan_shadow_stage,
    build_live_chat_response,
)
from app.chat.session_context import clear_session
from app.chat_commands import is_clear_chat_command
from app.config import settings
from app.demo.scenarios import resolve_demo_scenario_id_for_query, run_demo_scenario
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.workflow_planner import plan_workflow
from app.quality.store import post_chat_response
from app.routing.llm_route_plan_candidate import generate_llm_route_plan_candidate
from app.routing.skill_router import route_skill
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

router = APIRouter()

logger = logging.getLogger("ai_soc.telemetry")


@router.post("/chat", response_model=PlaceholderResponse)
def chat(
    request: ChatRequest,
    http_request: Request = None,  # type: ignore[assignment]  # FastAPI injects; None only for direct in-process calls
    response: Response = None,  # type: ignore[assignment]
    user: object = Depends(require_auth),
) -> PlaceholderResponse:
    # Client-known correlation: adopt the client's X-Request-ID (when a valid UUID)
    # as THE trace id for the whole turn, set it on the contextvar so the pipeline
    # adopts it (graph_node_init_routing reads current_trace_id), and echo it back
    # as X-Trace-ID. The client therefore knows the trace id before it sends the
    # request, so it can query the trace even when a transport timeout means it
    # never receives this response.
    #
    # An admission "running" record is persisted BEFORE pipeline work, so a turn
    # that stalls or whose client disconnects is still distinguishable from a turn
    # lost before backend admission (no record at all).
    #
    # A genuine producer/LLM failure degrades to a complete deterministic answer
    # deep in the pipeline (see _candidate_from_llm_fallback) and returns HTTP 200.
    # Anything that still escapes here is a real defect: we log it with the trace_id
    # and re-raise so the app-level handler returns an honest sanitized HTTP 500.
    # We never mask an unhandled failure as a 200 stub.
    # The middleware already derived the trace id from X-Request-ID and exposed it
    # on request.state; reuse it so the worker-thread contextvar matches exactly.
    # Fall back to re-deriving from the header (http_request is None only for direct
    # in-process test calls, where we just mint one).
    state_trace_id = getattr(getattr(http_request, "state", None), "trace_id", None)
    header_value = http_request.headers.get(REQUEST_ID_HEADER) if http_request is not None else None
    trace_id = state_trace_id or coerce_request_id(header_value)
    set_trace_id(trace_id)
    if response is not None:
        response.headers[TRACE_ID_HEADER] = trace_id
    persist_chat_admission(trace_id, user)
    try:
        return _chat_impl(request, user)
    except Exception as exc:
        logger.error(
            "chat_pipeline_failed trace_id=%s exc_type=%s",
            trace_id,
            type(exc).__name__,
        )
        # ContextVar mutations made by this sync route run in a worker thread and
        # do not reliably propagate to the async exception handler. Carry the
        # correlation id on the exception object instead; the public response still
        # exposes only this id and the stable generic error code.
        try:
            setattr(exc, "_ai_soc_trace_id", trace_id)
        except Exception:  # noqa: BLE001 - never replace the original failure
            pass
        raise



def _chat_impl(request: ChatRequest, user: object) -> PlaceholderResponse:
    if is_clear_chat_command(request.message):
        clear_session(request.session_id)
        return PlaceholderResponse(
            trace_id=str(uuid4()),
            message="Chat cleared. Ask your next question when ready.",
            note="client_command:/clear",
            user_query=request.message,
        )

    if settings.ai_soc_live_chat_ec_parity_enabled:
        scenario_id = resolve_demo_scenario_id_for_query(
            request.message, session_id=request.session_id
        )
        if scenario_id:
            return post_chat_response(
                PlaceholderResponse(**run_demo_scenario(scenario_id)),
                request,
                entrypoint="chat",
                user=user,
            )

    session_role = user.get("role") if isinstance(user, dict) else None
    if settings.langgraph_orchestration_enabled:
        from app.graph.chat_workflow import run_chat_via_langgraph

        return post_chat_response(
            run_chat_via_langgraph(request, session_role=session_role),
            request,
            entrypoint="chat",
            user=user,
        )

    return post_chat_response(
        build_live_chat_response(request, session_role=session_role),
        request,
        entrypoint="chat",
        user=user,
    )
