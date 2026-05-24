from uuid import uuid4

from fastapi import APIRouter, Depends

from app.auth.session import require_auth
from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.workflow_planner import plan_workflow
from app.routing.skill_router import route_skill
from app.safeguards.spl_validator import validate_spl
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse
from app.spl.generator import generate_candidate_spl

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
    candidate_spl, spl_validation = _candidate_spl_stage(
        trace_id=trace_id,
        skill=str(routed["skill"]),
        user_query=request.message,
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
        message=_chat_message(spl_validation),
        note=_chat_note(spl_validation),
        workflow_plan=workflow_plan,
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
    )


def _disagreement_reason(comparison: dict) -> str:
    if comparison.get("skill_match") is False:
        return "skill_mismatch"
    if comparison.get("tool_plan_match") is False:
        return "tool_plan_mismatch"
    return "unknown_mismatch"


def _candidate_spl_stage(trace_id: str, skill: str, user_query: str) -> tuple[dict | None, dict | None]:
    if skill not in {"attack_discovery", "spl_generation"}:
        return None, None

    telemetry = get_telemetry_connector()
    candidate = generate_candidate_spl(trace_id=trace_id, skill=skill, user_query=user_query)
    candidate_payload = candidate.model_dump()
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate.generation_mode,
        confidence=candidate.confidence,
        warnings=candidate.warnings,
    )

    validation = validate_spl(candidate.candidate_spl)
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
    }
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=validation["approved"],
        reject_reasons=validation["reject_reasons"],
        warnings=validation["warnings"],
        policy_version=validation["policy_version"],
    )
    return candidate_payload, validation_payload


def _chat_message(spl_validation: dict | None) -> str:
    if spl_validation is None:
        return "Routing complete. SPL is not required at this stage."
    return "SPL validation complete. MCP execution is disabled."


def _chat_note(spl_validation: dict | None) -> str:
    if spl_validation is None:
        return "Routing and workflow planning only; SPL is not required at this stage. No MCP execution, RAG retrieval, or synthesis was run."
    status = "approved" if spl_validation.get("approved") else "rejected"
    return f"Candidate SPL generated and {status} by deterministic validation. No MCP execution, RAG retrieval, or synthesis was run."
