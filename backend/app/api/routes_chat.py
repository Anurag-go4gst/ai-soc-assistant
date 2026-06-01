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
from app.chat_commands import is_clear_chat_command
from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.workflow_planner import plan_workflow
from app.routing.llm_route_plan_candidate import generate_llm_route_plan_candidate
from app.routing.skill_router import route_skill
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

router = APIRouter()


@router.post("/chat", response_model=PlaceholderResponse, dependencies=[Depends(require_auth)])
def chat(request: ChatRequest) -> PlaceholderResponse:
    if is_clear_chat_command(request.message):
        return PlaceholderResponse(
            trace_id=str(uuid4()),
            message="Chat cleared. Ask your next question when ready.",
            note="client_command:/clear",
            user_query=request.message,
        )

    if settings.langgraph_orchestration_enabled:
        from app.graph.chat_workflow import run_chat_via_langgraph

        return run_chat_via_langgraph(request)

    return build_live_chat_response(request)
