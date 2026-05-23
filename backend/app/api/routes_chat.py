from uuid import uuid4

from fastapi import APIRouter, Depends

from app.auth.session import require_auth
from app.config import settings
from app.orchestration.workflow_planner import plan_workflow
from app.routing.skill_router import route_skill
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

router = APIRouter()


@router.post("/chat", response_model=PlaceholderResponse, dependencies=[Depends(require_auth)])
def chat(request: ChatRequest) -> PlaceholderResponse:
    trace_id = str(uuid4())
    routed = route_skill(request.message, trace_id=trace_id)
    comparison = routed.get("comparison", {})
    disagreement = not bool(comparison.get("match", False))
    workflow_plan = plan_workflow(
        selected_skill=str(routed["skill"]),
        tool_plan=list(routed["tool_plan"]),
        query=request.message,
        trace_id=trace_id,
    )

    return PlaceholderResponse(
        trace_id=trace_id,
        user_query=request.message,
        selected_skill=str(routed["skill"]),
        tool_plan=list(routed["tool_plan"]),
        confidence=float(routed["confidence"]),
        routing_mode=settings.routing_mode,
        disagreement=disagreement,
        disagreement_reason=_disagreement_reason(comparison) if disagreement else None,
        message="Routing complete. SPL/MCP execution is not enabled yet.",
        note="Routing and workflow planning only; no SPL generation, MCP execution, RAG retrieval, or synthesis was run.",
        workflow_plan=workflow_plan,
    )


def _disagreement_reason(comparison: dict) -> str:
    if comparison.get("skill_match") is False:
        return "skill_mismatch"
    if comparison.get("tool_plan_match") is False:
        return "tool_plan_mismatch"
    return "unknown_mismatch"
