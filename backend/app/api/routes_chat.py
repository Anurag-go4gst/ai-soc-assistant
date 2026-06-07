from uuid import uuid4

from fastapi import APIRouter, Depends

from app.auth.session import require_auth
from app.chat.pipeline import (
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


@router.post("/chat", response_model=PlaceholderResponse)
def chat(request: ChatRequest, user: object = Depends(require_auth)) -> PlaceholderResponse:
    if is_clear_chat_command(request.message):
        clear_session(request.session_id)
        return PlaceholderResponse(
            trace_id=str(uuid4()),
            message="Chat cleared. Ask your next question when ready.",
            note="client_command:/clear",
            user_query=request.message,
        )

    if settings.ai_soc_live_chat_ec_parity_enabled:
        scenario_id = resolve_demo_scenario_id_for_query(request.message)
        if scenario_id:
            return post_chat_response(
                PlaceholderResponse(**run_demo_scenario(scenario_id)),
                request,
                entrypoint="chat",
                user=user,
            )

    if settings.langgraph_orchestration_enabled:
        from app.graph.chat_workflow import run_chat_via_langgraph

        return post_chat_response(run_chat_via_langgraph(request), request, entrypoint="chat", user=user)

    return post_chat_response(build_live_chat_response(request), request, entrypoint="chat", user=user)
