from __future__ import annotations

from typing import Any, TypedDict
from uuid import uuid4

from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.actions.capability_policy import action_capability_for
from app.answer_guard.models import AnswerGuardStatus
from app.evidence.context_structurer import structure_context
from app.evidence.context_sufficiency import check_context_sufficiency
from app.evidence.source_evidence import build_source_evidence
from app.knowledge.rag_evidence_lineage import resolve_answer_readiness, resolve_response_evidence_origin
from app.knowledge.soc_kb_retriever import retrieve_soc_kb
from app.lineage.builder import build_investigation_lineage
from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.workflow_planner import plan_workflow
from app.query_understanding.semantic_intent import build_semantic_intent_envelope
from app.query_understanding.parser import understand_query
from app.routing.routing_provenance import degraded_query_understanding_from_failover
from app.routing.operation_audit import build_operation_audit_record, operation_audit_human_review
from app.routing.llm_route_plan_candidate import skipped_reason_to_candidate_reason
from app.routing.route_plan_models import ROUTE_PLAN_GENERATOR_MODEL_FAMILY, ROUTE_PLAN_REASONING_MODEL_ALLOWED
from app.routing.route_plan_preflight import preflight_route_plan
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.routing.intent_operation_bridge_shadow import apply_intent_operation_bridge_to_shadow
from app.coverage.question_runtime_map_shadow import apply_question_runtime_map_to_shadow
from app.routing.precondition_evaluation_shadow import apply_precondition_evaluation_to_shadow
from app.routing.route_authority_compare import apply_route_authority_compare_to_shadow
from app.routing.registry_route_authority import resolve_effective_routing_skill
from app.routing.route_adjudication import adjudicate_route as adjudicate_control_plane_route
from app.routing.llm_plan_validator import (
    build_advisory_plan_from_context,
    should_validate_llm_advisory_plan,
    validate_llm_advisory_plan,
)
from app.routing.supporter_registry import build_supporter_trace
from app.routing.use_case_registry_bridge import build_use_case_registry_bridge
from app.routing.template_match_shadow import apply_template_match_to_shadow
from app.synthesis.analyst_summary_llm_assist import apply_analyst_summary_shadow
from app.governance.trace_panels import build_governance_trace
from app.risk.severity_policy import decide_severity
from app.safeguards.spl_validator import validate_spl
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse
from app.skills.selector import select_skill_chain
from app.spl.template_registry import template_summary
from app.splunk.capabilities import build_splunk_capability_profile
from app.splunk.spl_services import explain_spl, generate_candidate_spl_with_provider, optimize_spl, splunk_guidance
from app.answer_guard.runner import run_answer_guard_lab
from app.synthesis.lab_runner import apply_synthesis_allowed_to_sufficiency, run_governed_synthesis_lab
from app.synthesis.models import SynthesisStatus
from app.threat.mitre_kb import map_mitre_for_use_case
from app.threat.mitre_permitted import resolve_mitre_mappings_for_chat
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import match_use_cases
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent

def _routes_chat():
    """Lazy import so tests can monkeypatch symbols on app.api.routes_chat."""
    from app.api import routes_chat

    return routes_chat


class ChatPipelineState(TypedDict, total=False):
    request: ChatRequest
    trace_id: str
    query_understanding: Any
    selected_use_case: Any
    routed: dict[str, Any]
    route_plan_shadow: dict[str, Any]
    routing_skill_resolution: dict[str, Any]
    skill_selection: Any
    selected_skill_chain: Any
    disagreement: bool
    comparison: dict[str, Any]
    workflow_plan: dict[str, Any]
    candidate_spl: dict[str, Any] | None
    spl_validation: dict[str, Any] | None
    execution: dict[str, Any]
    human_review: dict[str, Any]
    source_evidence: list[dict[str, Any]]
    structured_context: dict[str, Any]
    context_sufficiency: dict[str, Any]
    spl_template: dict[str, object] | None
    mitre_mappings: list[Any]
    severity_decision: Any
    synthesis_status: Any
    answer_guard: Any
    action_capability: Any
    investigation_lineage: Any
    message: str
    note: str
    governance_trace: Any
    query_to_intent: dict[str, Any] | None
    intent_classification: dict[str, Any] | None
    evidence_plan: dict[str, Any] | None
    route_adjudication: dict[str, Any] | None
    llm_plan_validation: dict[str, Any] | None
    soc_kb_retrieval: dict[str, Any] | None
    response: PlaceholderResponse


def build_live_chat_response(request: ChatRequest) -> PlaceholderResponse:
    state: ChatPipelineState = {"request": request}
    state = graph_node_init_routing(state)
    state = graph_node_query_to_intent(state)
    state = graph_node_evidence_planning(state)
    state = graph_node_shadow_enrichment(state)
    if _uses_rag_only_path(state):
        state = graph_node_prepare_rag_only(state)
        state = graph_node_rag_early(state)
    else:
        state = graph_node_workflow_spl(state)
        if _uses_pre_mcp_rag(state):
            state = graph_node_rag_early(state)
        state = graph_node_execution(state)
    state = graph_node_context_finalize(state)
    response = state.get("response")
    if response is None:
        raise RuntimeError("chat pipeline did not produce a response")
    return response


def graph_node_init_routing(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    trace_id = str(uuid4())
    qu_failed = False
    try:
        query_understanding = understand_query(request.message)
    except Exception:
        query_understanding = None
        qu_failed = True
    selected_use_case = _selected_use_case(request.message)
    rc = _routes_chat()
    routed = rc.route_skill(
        request.message,
        trace_id=trace_id,
        query_understanding=query_understanding,
        qu_failed=qu_failed,
    )
    if query_understanding is None:
        query_understanding = degraded_query_understanding_from_failover(
            request.message,
            routed.get("routing_provenance") or {},
        )
    route_plan_shadow = _route_plan_shadow_stage(
        request.message,
        deterministic_primary_skill=str(routed["skill"]),
    )
    return {
        **state,
        "trace_id": trace_id,
        "query_understanding": query_understanding,
        "selected_use_case": selected_use_case,
        "routed": routed,
        "route_plan_shadow": route_plan_shadow,
    }


def graph_node_query_to_intent(state: ChatPipelineState) -> ChatPipelineState:
    """Passive query-to-intent stage (does not change routing when flag is off)."""
    request = state["request"]
    query_understanding = state.get("query_understanding")
    routed = state.get("routed") or {}
    routed_skill = str(routed.get("skill")) if routed.get("skill") else None
    result = build_query_to_intent(
        query=request.message,
        query_understanding=query_understanding,
        routed_skill=routed_skill,
    )
    payload = result.model_dump()
    return {
        **state,
        "query_to_intent": payload,
        "intent_classification": payload.get("intent_classification"),
    }


def graph_node_evidence_planning(state: ChatPipelineState) -> ChatPipelineState:
    if not settings.control_plane_enabled:
        return {**state, "evidence_plan": None}
    intent = state.get("intent_classification")
    if not isinstance(intent, dict):
        return {**state, "evidence_plan": None}
    plan = plan_evidence(
        intent,
        query_to_intent=state.get("query_to_intent"),
        routed=state.get("routed"),
    )
    return {**state, "evidence_plan": plan.model_dump()}


def graph_node_shadow_enrichment(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    routed = state["routed"]
    route_plan_shadow = state["route_plan_shadow"]
    apply_intent_operation_bridge_to_shadow(route_plan_shadow, legacy_intent=str(routed["skill"]))
    apply_route_authority_compare_to_shadow(
        route_plan_shadow,
        selected_skill=str(routed["skill"]),
        routing_comparison=routed.get("comparison"),
    )
    route_authority = _route_authority_payload(route_plan_shadow)
    primary_operation = _primary_operation_from_authority(route_plan_shadow, route_authority)
    routing_skill_resolution = resolve_effective_routing_skill(
        selected_skill=str(routed["skill"]),
        route_authority=route_authority,
        primary_operation=primary_operation,
    )
    route_plan_shadow["routing_skill_resolution"] = routing_skill_resolution
    route_plan_shadow["use_case_registry_bridge"] = build_use_case_registry_bridge(request.message)
    if isinstance(route_authority, dict):
        route_authority["legacy_intent_authority"] = routing_skill_resolution.get("legacy_intent_authority", True)
        route_authority["selected_skill_mirror_only"] = not bool(
            routing_skill_resolution.get("legacy_intent_authority", True)
        )
        route_plan_shadow["route_authority_compare"] = route_authority
    apply_question_runtime_map_to_shadow(route_plan_shadow)
    apply_precondition_evaluation_to_shadow(route_plan_shadow)
    if route_plan_shadow.get("candidate_available"):
        route_plan_shadow["supporter_trace"] = build_supporter_trace(
            _route_plan_for_supporters(route_plan_shadow),
            query=request.message,
            shadow=route_plan_shadow,
            runtime_invoked=True,
        )
    _apply_ood_llm_lab_metadata(route_plan_shadow, request.message)
    apply_analyst_summary_shadow(route_plan_shadow)
    skill_selection = select_skill_chain(routed=routed, selected_use_case=state.get("selected_use_case"))
    comparison = routed.get("comparison", {})
    route_adjudication_payload: dict[str, Any] | None = None
    llm_plan_validation_payload: dict[str, Any] | None = None
    if settings.control_plane_enabled and isinstance(state.get("intent_classification"), dict):
        llm_advisory = comparison.get("llm_shadow") if isinstance(comparison, dict) else None
        adjudication = adjudicate_control_plane_route(
            deterministic_route=str(routed.get("skill") or "knowledge_recall"),
            llm_advisory=llm_advisory if isinstance(llm_advisory, dict) else None,
            route_plan_shadow=route_plan_shadow,
            evidence_plan=state.get("evidence_plan"),
            intent_classification=state["intent_classification"],
            query_understanding=state.get("query_understanding"),
            message=request.message,
            query_to_intent=state.get("query_to_intent"),
        )
        route_adjudication_payload = adjudication.model_dump()
        routing_skill_resolution = {
            **routing_skill_resolution,
            "effective_skill": adjudication.final_route,
            "skill_resolution": "control_plane_route_adjudication",
            "legacy_intent_authority": False,
            "route_adjudication_authority_source": adjudication.authority_source,
        }
    if should_validate_llm_advisory_plan():
        advisory_plan = build_advisory_plan_from_context(
            comparison=comparison if isinstance(comparison, dict) else None,
            route_plan_shadow=route_plan_shadow,
        )
        q2i = state.get("query_to_intent")
        candidate_mappings = (
            q2i.get("candidate_mappings") if isinstance(q2i, dict) else None
        )
        llm_validation = validate_llm_advisory_plan(
            advisory_plan,
            evidence_plan=state.get("evidence_plan"),
            route_adjudication=route_adjudication_payload,
            intent_classification=state.get("intent_classification"),
            candidate_mappings=candidate_mappings,
        )
        llm_plan_validation_payload = llm_validation.model_dump()
        route_plan_shadow["llm_plan_validation"] = llm_plan_validation_payload
    return {
        **state,
        "route_plan_shadow": route_plan_shadow,
        "routing_skill_resolution": routing_skill_resolution,
        "route_adjudication": route_adjudication_payload,
        "llm_plan_validation": llm_plan_validation_payload,
        "skill_selection": skill_selection,
        "selected_skill_chain": skill_selection.selected_chain,
        "comparison": comparison,
        "disagreement": not bool(comparison.get("match", False)),
    }


def graph_node_workflow_spl(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    routed = state["routed"]
    trace_id = state["trace_id"]
    effective_skill = _effective_routing_skill(state)
    rc = _routes_chat()
    workflow_plan = rc.plan_workflow(
        selected_skill=effective_skill,
        tool_plan=list(routed["tool_plan"]),
        query=request.message,
        trace_id=trace_id,
    )
    candidate_spl, spl_validation = _candidate_spl_stage(
        trace_id=trace_id,
        skill=effective_skill,
        user_query=request.message,
        spl_allowed=_spl_allowed(state),
    )
    return {
        **state,
        "workflow_plan": workflow_plan,
        "candidate_spl": candidate_spl,
        "spl_validation": spl_validation,
    }


def graph_node_execution(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    routed = state["routed"]
    execution, human_review = _execution_stage(
        trace_id=state["trace_id"],
        selected_skill=_effective_routing_skill(state),
        workflow_plan=state["workflow_plan"],
        spl_validation=state.get("spl_validation"),
        precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=request.requested_mcp_tool,
        mcp_allowed=_mcp_allowed(state),
    )
    return {**state, "execution": execution, "human_review": human_review}


def graph_node_prepare_rag_only(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    trace_id = state["trace_id"]
    rc = _routes_chat()
    workflow_plan = rc.plan_workflow(
        selected_skill="knowledge_recall",
        tool_plan=["retrieve_approved_knowledge", "no_spl", "no_mcp"],
        query=request.message,
        trace_id=trace_id,
    )
    execution, human_review = _execution_stage(
        trace_id=trace_id,
        selected_skill="knowledge_recall",
        workflow_plan=workflow_plan,
        spl_validation=None,
        precondition_evaluation=state.get("route_plan_shadow", {}).get("precondition_evaluation"),
        requested_mcp_server=request.requested_mcp_server,
        requested_mcp_tool=request.requested_mcp_tool,
        mcp_allowed=False,
    )
    return {
        **state,
        "workflow_plan": workflow_plan,
        "candidate_spl": None,
        "spl_validation": None,
        "execution": execution,
        "human_review": human_review,
    }


def graph_node_rag_early(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    workflow_plan = state["workflow_plan"]
    execution = state["execution"] if "execution" in state else {"block_reason": None}
    retrieval = retrieve_soc_kb(
        query=request.message,
        selected_skill=_context_selected_skill(state),
        workflow_stage="context",
        workflow_plan=workflow_plan,
        required_sources=list(workflow_plan.get("required_sources") or []),
        execution_block_reason=execution.get("block_reason"),
    )
    return {**state, "soc_kb_retrieval": retrieval}


def graph_node_context_finalize(state: ChatPipelineState) -> ChatPipelineState:
    request = state["request"]
    routed = state["routed"]
    trace_id = state["trace_id"]
    selected_use_case = state.get("selected_use_case")
    spl_validation = state.get("spl_validation")
    execution = state["execution"]
    source_evidence, structured_context, context_sufficiency = _context_stage(
        trace_id=trace_id,
        query=request.message,
        selected_skill=_context_selected_skill(state),
        workflow_plan=state["workflow_plan"],
        spl_validation=spl_validation,
        execution=execution,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        evidence_plan=state.get("evidence_plan"),
    )
    human_review = _attach_hil_soc_kb_guidance(state["human_review"], source_evidence)
    source_refs = [str(item.get("evidence_id")) for item in source_evidence]
    spl_template = template_summary(selected_use_case.default_spl_template if selected_use_case else None)
    provenance = routed.get("routing_provenance") if isinstance(routed.get("routing_provenance"), dict) else {}
    mapped_refs = provenance.get("mapped_use_case_ids") if isinstance(provenance.get("mapped_use_case_ids"), list) else []
    use_case_id = selected_use_case.use_case_id if selected_use_case else (str(mapped_refs[0]) if mapped_refs else None)
    question_ref = provenance.get("mapped_question_ref") if isinstance(provenance.get("mapped_question_ref"), str) else None
    mitre_mappings = _mitre_mappings_for_finalize(
        question_ref=question_ref,
        use_case_id=use_case_id,
        source_refs=source_refs,
    )
    severity_decision = decide_severity(
        selected_use_case.use_case_id if selected_use_case else None,
        structured_context,
        source_refs,
    )
    action_capability = action_capability_for(
        selected_use_case.use_case_id if selected_use_case else None,
        severity_decision.severity_label,
    )
    synthesis_lab = run_governed_synthesis_lab(
        structured_context=structured_context,
        source_evidence=source_evidence,
        context_sufficiency=context_sufficiency,
        mitre_mappings=mitre_mappings,
        action_capability=action_capability,
        severity_label=severity_decision.severity_label,
        spl_validation=spl_validation,
        human_review=human_review,
    )
    synthesis_status = synthesis_lab.status
    context_sufficiency = apply_synthesis_allowed_to_sufficiency(
        context_sufficiency,
        package=synthesis_lab.package,
    )
    answer_guard = run_answer_guard_lab(
        draft=synthesis_lab.draft,
        package=synthesis_lab.package,
        structured_context=structured_context,
        source_evidence=source_evidence,
        severity_label=severity_decision.severity_label,
        action_policy={
            "allowed_actions": list(action_capability.allowed_actions),
            "current_tier": action_capability.current_tier,
        },
    )
    analyst_summary_from_lab: str | None = None
    if synthesis_lab.analyst_summary and synthesis_status.status == "completed":
        if not answer_guard.enabled or answer_guard.guard_status == "passed":
            analyst_summary_from_lab = synthesis_lab.analyst_summary
        elif answer_guard.guard_status == "blocked":
            human_review = {
                **human_review,
                "required": True,
                "review_type": "answer_guard_blocked",
                "safe_message_for_user": (
                    "A governed draft answer was produced but blocked by Answer Guard. "
                    "Review the technical trace and evidence package."
                ),
            }
    route_plan_shadow = state["route_plan_shadow"]
    route_authority = _route_authority_payload(route_plan_shadow)
    primary_operation = _primary_operation_from_authority(route_plan_shadow, route_authority)
    coverage_id = _coverage_id_from_authority(route_authority)
    semantic_intent = build_semantic_intent_envelope(
        query_understanding=state["query_understanding"],
        routed=routed,
        route_plan_shadow=route_plan_shadow,
        route_authority=route_authority,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
    )
    operation_audit = build_operation_audit_record(
        query=request.message,
        primary_operation=primary_operation,
        coverage_id=coverage_id,
        semantic_intent=semantic_intent,
        route_plan_shadow=route_plan_shadow,
        trace_id=trace_id,
    )
    if operation_audit is not None:
        route_plan_shadow["operation_audit"] = operation_audit
    investigation_lineage = build_investigation_lineage(
        trace_id=trace_id,
        mode_source="live",
        query_understanding=state["query_understanding"],
        selected_use_case=selected_use_case,
        selected_skill_chain=state["selected_skill_chain"],
        workflow_plan=state["workflow_plan"],
        spl_validation=spl_validation,
        execution=execution,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
        route_plan_shadow=route_plan_shadow,
        spl_template=spl_template,
        mitre_mappings=mitre_mappings,
        severity_decision=severity_decision,
        synthesis_status=synthesis_status,
        answer_guard_status=answer_guard,
        action_capability=action_capability,
    )

    message = _chat_message(spl_validation, execution)
    note = _chat_note(spl_validation, execution)
    candidate_spl = state.get("candidate_spl")
    if _needs_mitre_clarification(request.message, candidate_spl):
        human_review = _mitre_clarification_review()
        message = (
            "I need alert context before mapping to MITRE ATT&CK. Share the alert title, "
            "detection rule, notable/event ID, or the SPL and a few sample fields."
        )
        note = "MITRE mapping requires grounded alert context; no SPL was generated."
    else:
        audit_review = operation_audit_human_review(operation_audit)
        if audit_review is not None:
            human_review = audit_review
            message = audit_review["safe_message_for_user"]
            note = "Novel operation proposals stop at audit/HIL; no MCP or SPL execution is authorized."

    evidence_origin = resolve_response_evidence_origin(
        source_evidence=source_evidence,
        soc_kb_retrieval=state.get("soc_kb_retrieval"),
        execution=execution,
    )
    answer_readiness = resolve_answer_readiness(
        evidence_origin=evidence_origin,
        context_sufficiency=context_sufficiency,
    )
    if evidence_origin:
        reasons = list(context_sufficiency.get("reasons") or [])
        label = f"evidence_origin:{evidence_origin}"
        if label not in reasons:
            reasons.append(label)
            context_sufficiency = {**context_sufficiency, "reasons": sorted(reasons)}

    comparison = state.get("comparison") or {}
    governance_trace = build_governance_trace(
        demo_mode=False,
        use_case_id=selected_use_case.use_case_id if selected_use_case else None,
        selected_skill=str(routed["skill"]),
        severity_decision=severity_decision,
        investigation_lineage=investigation_lineage,
        source_evidence=source_evidence,
        execution=execution,
        route_plan_shadow=route_plan_shadow,
        question_runtime_map=route_plan_shadow.get("question_runtime_map") if route_plan_shadow else None,
        precondition_evaluation=route_plan_shadow.get("precondition_evaluation") if route_plan_shadow else None,
        selected_use_case=selected_use_case.model_dump() if selected_use_case else None,
    )

    routing_skill_resolution = state.get("routing_skill_resolution") or route_plan_shadow.get(
        "routing_skill_resolution"
    )
    response = PlaceholderResponse(
        trace_id=trace_id,
        user_query=request.message,
        selected_skill=str(routed["skill"]),
        primary_operation=primary_operation,
        coverage_id=coverage_id,
        route_authority=route_authority,
        legacy_intent_authority=bool(
            (routing_skill_resolution or {}).get("legacy_intent_authority", True)
        ),
        routing_skill_resolution=routing_skill_resolution,
        evidence_origin=evidence_origin,
        answer_readiness=answer_readiness,
        semantic_intent=semantic_intent,
        operation_audit=operation_audit,
        tool_plan=list(routed["tool_plan"]),
        confidence=float(routed["confidence"]),
        routing_mode=settings.routing_mode,
        disagreement=state["disagreement"],
        disagreement_reason=_disagreement_reason(comparison) if state["disagreement"] else None,
        query_understanding=state["query_understanding"],
        selected_use_case=selected_use_case,
        selected_skill_chain=state["selected_skill_chain"],
        skill_selection=state["skill_selection"],
        message=message,
        note=note,
        analyst_summary=analyst_summary_from_lab,
        workflow_plan=state["workflow_plan"],
        candidate_spl=candidate_spl,
        spl_validation=spl_validation,
        execution=execution,
        human_review=human_review,
        source_evidence=source_evidence,
        structured_context=structured_context,
        context_sufficiency=context_sufficiency,
        route_plan_shadow=route_plan_shadow,
        spl_template=spl_template,
        mitre_mappings=mitre_mappings,
        severity_decision=severity_decision,
        investigation_lineage=investigation_lineage,
        synthesis_status=synthesis_status,
        answer_guard=answer_guard,
        action_capability=action_capability,
        governance_trace=governance_trace,
        query_to_intent=state.get("query_to_intent"),
        evidence_plan=state.get("evidence_plan"),
        route_adjudication=state.get("route_adjudication"),
    )
    return {**state, "response": response}


def _route_authority_payload(route_plan_shadow: dict[str, Any] | None) -> dict[str, object] | None:
    if not isinstance(route_plan_shadow, dict):
        return None
    compare = route_plan_shadow.get("route_authority_compare")
    if isinstance(compare, dict):
        return dict(compare)
    return None


def _primary_operation_from_authority(
    route_plan_shadow: dict[str, Any] | None,
    route_authority: dict[str, object] | None,
) -> str | None:
    if route_authority:
        for key in ("planning_primary_skill", "candidate_primary_skill", "route_plan_primary_skill_observed"):
            value = route_authority.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(route_plan_shadow, dict):
        value = route_plan_shadow.get("primary_skill")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coverage_id_from_authority(route_authority: dict[str, object] | None) -> str | None:
    if not route_authority:
        return None
    value = route_authority.get("coverage_id_resolved") or route_authority.get("coverage_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _evidence_plan(state: ChatPipelineState) -> dict[str, Any]:
    plan = state.get("evidence_plan")
    return plan if isinstance(plan, dict) else {}


def _uses_rag_only_path(state: ChatPipelineState) -> bool:
    if not settings.control_plane_enabled:
        return False
    return _evidence_plan(state).get("answer_mode") == "rag_only"


def _uses_pre_mcp_rag(state: ChatPipelineState) -> bool:
    if not settings.control_plane_enabled:
        return False
    plan = _evidence_plan(state)
    return bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp"


def _spl_allowed(state: ChatPipelineState) -> bool:
    if not settings.control_plane_enabled:
        return True
    return bool(_evidence_plan(state).get("spl_allowed", True))


def _mcp_allowed(state: ChatPipelineState) -> bool:
    if not settings.control_plane_enabled:
        return True
    return bool(_evidence_plan(state).get("mcp_allowed", True))


def _context_selected_skill(state: ChatPipelineState) -> str:
    workflow_plan = state.get("workflow_plan")
    if settings.control_plane_enabled and isinstance(workflow_plan, dict):
        skill = workflow_plan.get("skill")
        if isinstance(skill, str) and skill.strip():
            return skill.strip()
    routed = state.get("routed") or {}
    return str(routed.get("skill") or _effective_routing_skill(state))


def _selected_use_case(query: str) -> UseCaseSelection | None:
    matches = match_use_cases(query, limit=1)
    if matches:
        return matches[0]
    return None


def _mitre_mappings_for_finalize(
    *,
    question_ref: str | None,
    use_case_id: str | None,
    source_refs: list[str],
) -> list[Any]:
    """Legacy use-case KB mapping by default; registry-augmented path only when control plane is on."""
    if not settings.control_plane_enabled:
        return map_mitre_for_use_case(use_case_id, source_refs)
    return resolve_mitre_mappings_for_chat(
        question_ref=question_ref,
        use_case_id=use_case_id,
        source_refs=source_refs,
    )


_MITRE_INTENT_KEYWORDS = ("mitre", "att&ck", "attack technique", "map this alert", "map the alert")
# Markers that an alert/event was actually supplied, so mapping can proceed normally.
_ALERT_CONTEXT_MARKERS = ("index=", "sourcetype=", "rule:", "rule ", "alert:", "notable", "signature=", "event id", "eventid")


def _needs_mitre_clarification(query: str, candidate_spl: dict | None) -> bool:
    """Conservative heuristic: a MITRE mapping ask with no alert context yet.

    False positives (asking for detail when context was present) are worse than
    false negatives, so any context marker, a generated SPL, or a long message
    routes through normal handling instead.
    """
    normalized = " ".join(query.lower().split())
    if not any(keyword in normalized for keyword in _MITRE_INTENT_KEYWORDS):
        return False
    if candidate_spl and candidate_spl.get("candidate_spl"):
        return False
    if len(normalized) > 160:
        return False
    return not any(marker in normalized for marker in _ALERT_CONTEXT_MARKERS)


def _mitre_clarification_review() -> dict:
    return human_review(
        "intent_clarification",
        "mitre_mapping_requires_alert_context",
        "soc_analyst",
        ["provide_alert_details", "cancel"],
        "To map to MITRE ATT&CK I need the alert context first: the alert title, detection rule, "
        "notable/event ID, or the SPL with a few sample fields. I will not generate SPL or guess "
        "techniques without grounding.",
    )


def _disagreement_reason(comparison: dict) -> str:
    if comparison.get("skill_match") is False:
        return "skill_mismatch"
    if comparison.get("tool_plan_match") is False:
        return "tool_plan_mismatch"
    return "unknown_mismatch"


def _route_plan_shadow_stage(query: str, *, deterministic_primary_skill: str | None = None) -> dict:
    shadow = _route_plan_shadow_base(model_role="instruct_candidate_only")
    preflight = preflight_route_plan(query)
    shadow["preflight_status"] = preflight.route_status.value if preflight.route_status else "passed"
    shadow["missing_slots"] = list(preflight.missing_slots)
    shadow["blocking_findings"] = list(preflight.blocking_findings)
    shadow["warnings"] = list(preflight.warnings)

    if preflight.is_blocked:
        shadow["route_status"] = preflight.route_status.value if preflight.route_status else None
        shadow["candidate_available"] = False
        shadow["candidate_reason"] = "deterministic_preflight_blocked"
        apply_template_match_to_shadow(shadow, normalized_route_plan=None)
        return shadow

    llm_result = _routes_chat().generate_llm_route_plan_candidate(
        query,
        preflight=preflight,
        deterministic_primary_skill=deterministic_primary_skill,
    )
    llm_result.apply_to_shadow(shadow)

    candidate: dict | None = None
    candidate_reason: str | None = None
    validation = llm_result.validation

    if llm_result.llm_candidate_route_plan_available and llm_result.candidate is not None:
        candidate = llm_result.candidate
        candidate_reason = llm_result.candidate_reason or "llm_shadow_candidate"
        shadow["model_role"] = "instruct_candidate_only"
    else:
        hook_candidate = _routes_chat()._route_plan_shadow_candidate(query)
        if hook_candidate is not None:
            candidate = hook_candidate
            candidate_reason = "test_or_mock_candidate"
            validation = validate_route_plan_candidate(candidate)
        elif llm_result.llm_called:
            shadow["model_role"] = "instruct_candidate_only"
            candidate_reason = "llm_candidate_dropped"
        else:
            candidate_reason = skipped_reason_to_candidate_reason(llm_result.skipped_reason)
            shadow["model_role"] = (
                "none" if ROUTE_PLAN_GENERATOR_MODEL_FAMILY != "instruct" else "instruct_candidate_only"
            )

    if candidate is None:
        shadow["candidate_available"] = False
        shadow["candidate_reason"] = candidate_reason or "live_llm_routing_disabled"
        shadow["supporter_trace"] = build_supporter_trace(None)
        apply_template_match_to_shadow(shadow, normalized_route_plan=None)
        return shadow

    if validation is None:
        validation = validate_route_plan_candidate(candidate)
    normalized = validation.normalized_route_plan or {}
    shadow.update(
        {
            "route_status": normalized.get("route_status"),
            "primary_skill": normalized.get("primary_skill") or candidate.get("primary_skill"),
            "pattern_id": normalized.get("pattern_id") or candidate.get("pattern_id"),
            "candidate_available": True,
            "candidate_reason": candidate_reason,
            "validation_result": {"is_valid": validation.is_valid},
            "validation_findings": list(validation.validation_findings),
            "blocking_findings": list(validation.blocking_findings),
            "warnings": sorted(set(shadow["warnings"]) | set(validation.warnings)),
            "normalized_plan_available": bool(validation.normalized_route_plan and validation.is_valid),
        }
    )
    shadow["supporter_trace"] = build_supporter_trace(
        validation.normalized_route_plan or candidate,
        query=query,
        shadow=shadow,
        runtime_invoked=True,
    )
    validated_plan = validation.normalized_route_plan if validation.is_valid else None
    apply_template_match_to_shadow(shadow, normalized_route_plan=validated_plan)
    if validated_plan:
        parameters = validated_plan.get("parameters")
        if isinstance(parameters, dict):
            shadow["route_plan_parameters"] = dict(parameters)
        time_window = validated_plan.get("time_window")
        if isinstance(time_window, str) and time_window.strip():
            shadow["route_plan_time_window"] = time_window
    return shadow


def _route_plan_shadow_base(*, model_role: str) -> dict:
    return {
        "enabled": True,
        "mode": "dormant_shadow",
        "preflight_status": None,
        "route_status": None,
        "primary_skill": None,
        "pattern_id": None,
        "candidate_available": False,
        "candidate_reason": None,
        "validation_result": None,
        "validation_findings": [],
        "blocking_findings": [],
        "warnings": [],
        "missing_slots": [],
        "normalized_plan_available": False,
        "execution_authorized": False,
        "llm_called": False,
        "llm_role": None,
        "llm_model_family": None,
        "llm_candidate_route_plan_available": False,
        "llm_candidate_dropped_reasons": [],
        "deterministic_route_plan_wins": True,
        "disagreements": [],
        "analyst_summary_shadow_available": False,
        "analyst_summary_shadow_text": None,
        "analyst_summary_trace_bullets": [],
        "analyst_summary_dropped_reasons": [],
        "analyst_summary_shadow_source": None,
        "analyst_summary_narration_llm_called": False,
        "mcp_called": False,
        "spl_generated": False,
        "spl_executed": False,
        "model_role": model_role,
        "reasoning_model_used": ROUTE_PLAN_REASONING_MODEL_ALLOWED,
        "intent_operation_bridge": None,
        "route_authority_compare": None,
        "precondition_evaluation": None,
        "supporter_trace": None,
        "ood_llm_route_plan_lab": None,
        "operation_audit": None,
        "use_case_registry_bridge": None,
        "routing_skill_resolution": None,
    }


def _route_plan_for_supporters(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    for key in ("primary_skill", "pattern_id", "route_status", "source_class", "evidence_needs"):
        value = route_plan_shadow.get(key)
        if value is not None:
            plan[key] = value
    parameters = route_plan_shadow.get("route_plan_parameters")
    if isinstance(parameters, dict):
        plan["parameters"] = dict(parameters)
    return plan


def _apply_ood_llm_lab_metadata(route_plan_shadow: dict[str, Any], query: str) -> None:
    """Annotate P6-add lab-primary OOD routing without granting execution authority."""
    if settings.routing_mode != "llm_primary_lab" or not settings.routing_lab_llm_primary_enabled:
        route_plan_shadow["ood_llm_route_plan_lab"] = {
            "enabled": False,
            "reason": "lab_primary_mode_disabled",
        }
        return
    if settings.ai_soc_environment_mode == "production":
        route_plan_shadow["ood_llm_route_plan_lab"] = {
            "enabled": False,
            "reason": "production_blocked",
        }
        return

    runtime_map = route_plan_shadow.get("question_runtime_map")
    registry_hit = bool(isinstance(runtime_map, dict) and runtime_map.get("map_entry_found") is True)
    route_plan_shadow["supporter_trace"] = build_supporter_trace(
        _route_plan_for_supporters(route_plan_shadow),
        query=query,
        shadow=route_plan_shadow,
        runtime_invoked=True,
    )
    route_plan_shadow["ood_llm_route_plan_lab"] = {
        "enabled": True,
        "registry_exact_match": registry_hit,
        "llm_primary_for_ood": not registry_hit,
        "candidate_source": route_plan_shadow.get("candidate_reason"),
        "validator_wins": True,
        "execution_authorized": False,
        "mcp_called": False,
    }


def _effective_routing_skill(state: ChatPipelineState) -> str:
    if settings.control_plane_enabled:
        adjudication = state.get("route_adjudication")
        if isinstance(adjudication, dict):
            final_route = adjudication.get("final_route")
            if isinstance(final_route, str) and final_route.strip():
                return final_route.strip()
    resolution = state.get("routing_skill_resolution")
    if isinstance(resolution, dict):
        skill = resolution.get("effective_skill")
        if isinstance(skill, str) and skill.strip():
            return skill.strip()
    routed = state.get("routed") or {}
    return str(routed.get("skill") or "knowledge_recall")


def _route_plan_shadow_candidate(query: str) -> dict | None:
    return None


def _candidate_spl_stage(
    trace_id: str,
    skill: str,
    user_query: str,
    *,
    spl_allowed: bool = True,
) -> tuple[dict | None, dict | None]:
    if not spl_allowed:
        return None, None
    if skill not in {"attack_discovery", "spl_generation"}:
        return None, None

    telemetry = _routes_chat().get_telemetry_connector()
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
        "optimization_revalidation_approved": optimization["revalidation_approved"],
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
    rag_note = "Governed SOC KB retrieval may contribute source evidence when enabled."
    if not settings.soc_kb_retrieval_enabled:
        rag_note = "No RAG retrieval"
    if spl_validation is None:
        if not settings.soc_kb_retrieval_enabled:
            return "Routing and workflow planning only; SPL is not required at this stage. No MCP execution, RAG retrieval, or synthesis was run."
        return "Routing and workflow planning only; SPL is not required at this stage. Governed SOC KB retrieval may contribute source evidence when enabled. No MCP execution, final synthesis, or Splunk telemetry write was run."
    status = "approved" if spl_validation.get("approved") else "rejected"
    if execution and execution.get("status") == "executed":
        if not settings.soc_kb_retrieval_enabled:
            return f"Candidate SPL generated and {status}; mock MCP execution used normalized SPL only. No RAG retrieval, final synthesis, or Splunk telemetry write was run."
        return f"Candidate SPL generated and {status}; mock MCP execution used normalized SPL only. {rag_note} No final synthesis or Splunk telemetry write was run."
    if not settings.soc_kb_retrieval_enabled:
        return f"Candidate SPL generated and {status} by deterministic validation. No MCP execution, RAG retrieval, or synthesis was run."
    return f"Candidate SPL generated and {status} by deterministic validation. {rag_note} No MCP execution, final synthesis, or Splunk telemetry write was run."


def _execution_stage(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict,
    spl_validation: dict | None,
    precondition_evaluation: dict | None,
    requested_mcp_server: str | None,
    requested_mcp_tool: str | None,
    mcp_allowed: bool = True,
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
    if not mcp_allowed:
        return (
            {
                "status": "skipped",
                "execution_intent": "none",
                "selected_mcp_server": None,
                "selected_mcp_tool": None,
                "tool_selection_status": "blocked_by_evidence_plan",
                "tool_selection_reason": "mcp_not_allowed_by_evidence_plan",
                "executed_spl": None,
                "result_count": 0,
                "results_preview": [],
                "block_reason": "mcp_not_allowed_by_evidence_plan",
                "duration_ms": 0,
            },
            no_human_review(),
        )
    return evaluate_mcp_execution(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        spl_validation=spl_validation,
        precondition_evaluation=precondition_evaluation,
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
    soc_kb_retrieval: dict | None = None,
    evidence_plan: dict | None = None,
) -> tuple[list[dict], dict, dict]:
    telemetry = _routes_chat().get_telemetry_connector()
    if soc_kb_retrieval is None:
        soc_kb_retrieval = retrieve_soc_kb(
            query=query,
            selected_skill=selected_skill,
            workflow_stage="context",
            workflow_plan=workflow_plan,
            required_sources=list(workflow_plan.get("required_sources") or []),
            execution_block_reason=execution.get("block_reason"),
        )
    source_evidence = build_source_evidence(
        trace_id=trace_id,
        query=query,
        selected_skill=selected_skill,
        spl_validation=spl_validation,
        execution=execution,
        soc_kb_retrieval=soc_kb_retrieval,
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
    context_sufficiency = _apply_evidence_plan_sufficiency_reasons(
        context_sufficiency,
        evidence_plan=evidence_plan,
        soc_kb_retrieval=soc_kb_retrieval,
        source_evidence=source_evidence,
    )
    telemetry.record_step(
        trace_id,
        "context_sufficiency_checked",
        "completed",
        sufficiency_status=context_sufficiency["status"],
        synthesis_allowed=False,
        synthesis_readiness=context_sufficiency["synthesis_readiness"],
        reasons=context_sufficiency["reasons"],
    )
    return source_evidence, structured_context, context_sufficiency


def _apply_evidence_plan_sufficiency_reasons(
    context_sufficiency: dict[str, Any],
    *,
    evidence_plan: dict | None,
    soc_kb_retrieval: dict | None,
    source_evidence: list[dict],
) -> dict[str, Any]:
    if not isinstance(evidence_plan, dict) or not evidence_plan.get("policy_context_required"):
        return context_sufficiency
    reasons = set(context_sufficiency.get("reasons") or [])
    reasons.add("policy_context_required")
    retrieved = soc_kb_retrieval if isinstance(soc_kb_retrieval, dict) else {}
    retrieval_status = str(retrieved.get("retrieval_status") or "")
    has_rag = any(item.get("source_type") == "rag" and item.get("collection_status") == "collected" for item in source_evidence)
    if retrieval_status in {"no_match", "disabled", "failed"} or not has_rag:
        reasons.add("rag_no_match")
    return {**context_sufficiency, "reasons": sorted(reasons)}


def _attach_hil_soc_kb_guidance(human_review: dict, source_evidence: list[dict]) -> dict:
    if not human_review.get("required"):
        return human_review
    if any(evidence.get("source_type") == "rag" and evidence.get("collection_status") == "ambiguous" for evidence in source_evidence):
        return {
            **human_review,
            "safe_message_for_user": "Knowledge retrieval is ambiguous and requires analyst review.",
        }
    sop_rows = []
    for evidence in source_evidence:
        if evidence.get("source_type") != "rag" or evidence.get("collection_status") != "collected":
            continue
        for row in evidence.get("preview_rows", []):
            if isinstance(row, dict) and row.get("document_type") in {"sop", "runbook", "escalation_matrix"}:
                sop_rows.append(row)
    if not sop_rows:
        return {
            **human_review,
            "safe_message_for_user": "Approved SOP guidance is unavailable for this scenario.",
        }
    row = sop_rows[0]
    actions = [str(item) for item in row.get("recommended_actions") or []]
    return {
        **human_review,
        "reviewer_role": str(row.get("reviewer_role") or human_review.get("reviewer_role")),
        "allowed_actions": actions or human_review.get("allowed_actions", []),
        "sop_reference": row.get("citation"),
        "sop_excerpt": row.get("source_excerpt"),
        "sop_action_hint": actions[0] if actions else None,
    }
