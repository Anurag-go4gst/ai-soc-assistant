from uuid import uuid4

from fastapi import APIRouter, Depends

from app.auth.session import require_auth
from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.evidence.context_structurer import structure_context
from app.evidence.context_sufficiency import check_context_sufficiency
from app.evidence.source_evidence import build_source_evidence
from app.orchestration.human_review import no_human_review
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.workflow_planner import plan_workflow
from app.routing.skill_router import route_skill
from app.safeguards.spl_validator import validate_spl
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse
from app.splunk.capabilities import build_splunk_capability_profile
from app.splunk.spl_services import explain_spl, generate_candidate_spl_with_provider, optimize_spl, splunk_guidance

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
    execution, human_review = _execution_stage(
        trace_id=trace_id,
        selected_skill=str(routed["skill"]),
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=request.requested_mcp_tool,
    )
    source_evidence, structured_context, context_sufficiency = _context_stage(
        trace_id=trace_id,
        query=request.message,
        selected_skill=str(routed["skill"]),
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        execution=execution,
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
        message=_chat_message(spl_validation, execution),
        note=_chat_note(spl_validation, execution),
        workflow_plan=workflow_plan,
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
        execution=execution,
        human_review=human_review,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
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
    profile = build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    candidate, provider_metadata = generate_candidate_spl_with_provider(trace_id=trace_id, skill=skill, user_query=user_query, profile=profile)
    candidate_payload = candidate.model_dump()
    candidate_payload.update(provider_metadata)
    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=candidate.generation_mode,
        confidence=candidate.confidence,
        warnings=candidate.warnings,
        selected_candidate_spl_provider=provider_metadata["selected_candidate_spl_provider"],
        fallback_required=provider_metadata["fallback_required"],
    )

    validation = validate_spl(candidate.candidate_spl)
    explanation = explain_spl(candidate.candidate_spl, profile=profile)
    optimization = optimize_spl(candidate.candidate_spl, profile=profile)
    guidance = splunk_guidance(user_query, profile=profile)
    validation_payload = {
        "approved": validation["approved"],
        "normalized_spl": validation["normalized_spl"],
        "reject_reasons": validation["reject_reasons"],
        "warnings": validation["warnings"],
        "enforced_limits": validation["enforced_limits"],
        "policy_version": validation["policy_version"],
        "selected_candidate_spl_provider": provider_metadata["selected_candidate_spl_provider"],
        "candidate_provider_reason": provider_metadata["reason"],
        "saia_available": provider_metadata["saia_available"],
        "fallback_required": provider_metadata["fallback_required"],
        "spl_explanation_provider": explanation["provider"],
        "spl_optimization_provider": optimization["provider"],
        "spl_guidance_provider": guidance["provider"],
        "optimization_applied": optimization["optimization_applied"],
        "optimization_revalidation_status": optimization["revalidation_status"],
        "capability_profile": profile.model_dump(),
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


def _chat_message(spl_validation: dict | None, execution: dict | None = None) -> str:
    if spl_validation is None:
        return "Routing complete. SPL is not required at this stage."
    if execution and execution.get("status") == "executed":
        return "Mock MCP execution complete. Final synthesis is disabled."
    return "SPL validation complete. MCP execution is disabled."


def _chat_note(spl_validation: dict | None, execution: dict | None = None) -> str:
    if spl_validation is None:
        return "Routing and workflow planning only; SPL is not required at this stage. No MCP execution, RAG retrieval, or synthesis was run."
    status = "approved" if spl_validation.get("approved") else "rejected"
    if execution and execution.get("status") == "executed":
        return f"Candidate SPL generated and {status}; mock MCP execution used normalized SPL only. No RAG retrieval, final synthesis, or Splunk telemetry write was run."
    return f"Candidate SPL generated and {status} by deterministic validation. No MCP execution, RAG retrieval, or synthesis was run."


def _execution_stage(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict,
    spl_validation: dict | None,
    requested_mcp_server: str | None,
    requested_mcp_tool: str | None,
) -> tuple[dict, dict]:
    if spl_validation is None:
        return (
            {
                "status": "skipped",
                "execution_intent": "none",
                "selected_mcp_server": None,
                "selected_mcp_tool": None,
                "tool_selection_status": "unavailable",
                "tool_selection_reason": "spl_not_required_for_skill",
                "executed_spl": None,
                "result_count": 0,
                "results_preview": [],
                "block_reason": None,
                "duration_ms": 0,
            },
            no_human_review(),
        )
    return evaluate_mcp_execution(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        requested_mcp_server=requested_mcp_server,
        requested_mcp_tool=requested_mcp_tool,
    )


def _context_stage(
    *,
    trace_id: str,
    query: str,
    selected_skill: str,
    workflow_plan: dict,
    spl_validation: dict | None,
    execution: dict,
) -> tuple[list[dict], dict, dict]:
    telemetry = get_telemetry_connector()
    source_evidence = build_source_evidence(
        trace_id=trace_id,
        query=query,
        selected_skill=selected_skill,
        spl_validation=spl_validation,
        execution=execution,
    )
    telemetry.record_step(
        trace_id,
        "source_evidence_created",
        "completed",
        evidence_count=len(source_evidence),
        collected_count=sum(1 for item in source_evidence if item["collection_status"] == "collected"),
    )
    structured_context = structure_context(
        query=query,
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        execution=execution,
        source_evidence=source_evidence,
    )
    telemetry.record_step(
        trace_id,
        "context_structured",
        "completed",
        context_quality=structured_context["context_quality"],
        fact_count=len(structured_context["structured_facts"]),
        synthesis_allowed=False,
    )
    context_sufficiency = check_context_sufficiency(structured_context, source_evidence)
    telemetry.record_step(
        trace_id,
        "context_sufficiency_checked",
        "completed",
        sufficiency_status=context_sufficiency["status"],
        synthesis_allowed=False,
        reasons=context_sufficiency["reasons"],
    )
    return source_evidence, structured_context, context_sufficiency
