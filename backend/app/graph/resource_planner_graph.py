"""Resource Planner LangGraph hierarchy.

Callable from tests always; wired to ``/chat`` when ``LANGGRAPH_ORCHESTRATION_ENABLED=true``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.chat.control_plane_trace import patch_control_plane_trace_decision_log
from app.chat.decision_record import emit_decision_record
from app.chat.final_answer_validator import validate_final_answer
from app.chat.pipeline import (
    ChatPipelineState,
    build_live_chat_response,
    finalize_chat_trace_from_state,
    graph_node_composed_dispatch,
    graph_node_context_finalize,
    graph_node_evidence_planning,
    graph_node_execution,
    graph_node_init_routing,
    graph_node_prepare_rag_only,
    graph_node_query_to_intent,
    graph_node_rag_early,
    graph_node_shadow_enrichment,
    graph_node_spl_source_resolve,
    graph_node_workflow_spl,
)
from app.chat.progress_context import bind_progress_reporter, emit_stage, reset_progress_reporter
from app.chat.progress_events import ProgressReporter
from app.planner.executor import annotate_step_statuses, has_composed_plan
from app.planner.planner_hierarchy import (
    DecisionRecord,
    SkillSpecialistReport,
    SplSpecialistReport,
    build_planner_iteration,
    new_decision_record_id,
    work_bundle_from_resource_plan,
)
from app.planner.resource_plan import ResourcePlan
from app.planner.specialist_registry import load_specialist_registry
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

GOVERNANCE_NODE_NAMES: tuple[str, ...] = (
    "spl_validate",
    "mcp_execution_gate",
    "context_sufficiency",
    "decide_facts",
    "answer_guard",
    "validate_final_answer",
    "human_review",
    "policy_veto",
    "finalize",
)

DispatchRoute = Literal["rag_only", "composed_dispatch", "workflow_spl"]
AfterWorkflowSpl = Literal["rag_early", "spl_source_resolve"]
AfterRagEarly = Literal["governance_entry", "spl_source_resolve"]


class ResourcePlannerGraphState(ChatPipelineState, total=False):
    rp_graph_trace: dict[str, Any]
    planner_iteration: dict[str, Any]
    work_bundle: dict[str, Any]
    specialist_reports: list[dict[str, Any]]
    specialist_delegations: list[dict[str, Any]]
    policy_veto: dict[str, Any]


def _evidence_plan(state: ResourcePlannerGraphState) -> dict[str, Any]:
    plan = state.get("evidence_plan")
    return plan if isinstance(plan, dict) else {}


def _trace_append(state: ResourcePlannerGraphState, node: str) -> dict[str, Any]:
    trace = dict(state.get("rp_graph_trace") or {})
    visited = list(trace.get("visited_nodes") or [])
    visited.append(node)
    trace["visited_nodes"] = visited
    trace["topology"] = "resource_planner_hierarchy"
    return trace


def _with_trace(state: ResourcePlannerGraphState, node: str) -> ResourcePlannerGraphState:
    return {**state, "rp_graph_trace": _trace_append(state, node)}


def _record(
    state: ResourcePlannerGraphState,
    *,
    node: str,
    reason: str,
    inputs_ref: list[str],
    outputs_ref: list[str],
    authority: str = "resource_planner",
) -> ResourcePlannerGraphState:
    return emit_decision_record(
        state,
        DecisionRecord(
            record_id=new_decision_record_id(),
            node=node,
            authority=authority,
            decision_reason=reason,
            inputs_ref=inputs_ref,
            outputs_ref=outputs_ref,
        ),
    )


def rp_node_bootstrap(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_init_routing(state)
    state = graph_node_query_to_intent(state)
    state = graph_node_evidence_planning(state)
    state = _with_trace(state, "bootstrap")
    return _record(
        state,
        node="bootstrap",
        reason="query_and_evidence_plan_ready",
        inputs_ref=["request"],
        outputs_ref=["evidence_plan", "query_to_intent"],
        authority="deterministic",
    )


def rp_node_route_setup(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_shadow_enrichment(state)
    state = _with_trace(state, "route_setup")
    return _record(
        state,
        node="route_setup",
        reason="route_contract_and_skill_chain_ready",
        inputs_ref=["routed", "evidence_plan"],
        outputs_ref=["route_contract", "selected_skill_chain"],
        authority="deterministic",
    )


def rp_node_resource_planner_delegate(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    registry = load_specialist_registry()
    delegations = [
        {
            "delegation_id": f"del:{item.specialist_id}",
            "specialist_id": item.specialist_id,
            "ownership_scope": list(item.ownership_scope),
            "decision_reason": f"delegate_{item.specialist_id}",
        }
        for item in registry.specialists
    ]
    state = _with_trace(state, "resource_planner_delegate")
    state = {**state, "specialist_delegations": delegations}
    return _record(
        state,
        node="resource_planner.delegate",
        reason="fan_out_specialists",
        inputs_ref=["evidence_plan"],
        outputs_ref=["specialist_delegations"],
    )


def rp_node_specialist_skill(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    report = SkillSpecialistReport(
        delegation_id="del:skill",
        decision_reason="route_lane",
        skill_id=str(routed.get("skill") or ""),
        catalogue_tier="adapter",
    )
    reports = list(state.get("specialist_reports") or [])
    reports.append(report.model_dump())
    state = _with_trace(state, "specialist_skill")
    return _record(
        {**state, "specialist_reports": reports},
        node="specialist.skill",
        reason="skill_lane_advisory",
        inputs_ref=["routed"],
        outputs_ref=["specialist_reports"],
        authority="specialist:skill",
    )


def rp_node_specialist_knowledge(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "specialist_knowledge")
    return _record(
        state,
        node="specialist.knowledge",
        reason="knowledge_lane_idle_or_rag",
        inputs_ref=["evidence_plan"],
        outputs_ref=["specialist_reports"],
        authority="specialist:knowledge",
    )


def rp_node_specialist_mcp(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "specialist_mcp")
    return _record(
        state,
        node="specialist.mcp",
        reason="mcp_lane_advisory",
        inputs_ref=["evidence_plan"],
        outputs_ref=["specialist_reports"],
        authority="specialist:mcp",
    )


def rp_node_specialist_spl(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    reports = list(state.get("specialist_reports") or [])
    reports.append(
        SplSpecialistReport(
            delegation_id="del:spl",
            decision_reason="spl_lane_advisory",
            spl_source="template_or_fallback",
        ).model_dump()
    )
    state = _with_trace(state, "specialist_spl")
    return _record(
        {**state, "specialist_reports": reports},
        node="specialist.spl",
        reason="spl_lane_advisory",
        inputs_ref=["evidence_plan"],
        outputs_ref=["specialist_reports"],
        authority="specialist:spl",
    )


def rp_node_resource_planner_merge(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    evidence_plan = _evidence_plan(state)
    resource_plan_raw = evidence_plan.get("resource_plan")
    if isinstance(resource_plan_raw, dict):
        plan = ResourcePlan.model_validate(resource_plan_raw)
        bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:rp")
        iteration = build_planner_iteration(
            iteration=0,
            resource_plan=plan,
            delegations=[],
            bundle_id="bundle:rp",
        )
        state = {
            **state,
            "work_bundle": bundle.model_dump(),
            "planner_iteration": iteration.model_dump(),
        }
    state = _with_trace(state, "resource_planner_merge")
    return _record(
        state,
        node="resource_planner.merge",
        reason="fan_in_work_bundle",
        inputs_ref=["specialist_reports", "evidence_plan.resource_plan"],
        outputs_ref=["work_bundle", "planner_iteration"],
    )


def _rp_dispatch_route(state: ResourcePlannerGraphState) -> DispatchRoute:
    plan = _evidence_plan(state)
    if plan.get("answer_mode") == "rag_only":
        return "rag_only"
    if has_composed_plan(state):
        return "composed_dispatch"
    return "workflow_spl"


def _rp_after_workflow_spl(state: ResourcePlannerGraphState) -> AfterWorkflowSpl:
    plan = _evidence_plan(state)
    if bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp":
        return "rag_early"
    return "spl_source_resolve"


def _rp_after_rag_early(state: ResourcePlannerGraphState) -> AfterRagEarly:
    if "execution" in state:
        return "governance_entry"
    return "spl_source_resolve"


def rp_node_prepare_rag_only(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_prepare_rag_only(state)
    state = _with_trace(state, "prepare_rag_only")
    return _record(
        state,
        node="prepare_rag_only",
        reason="rag_only_path",
        inputs_ref=["evidence_plan"],
        outputs_ref=["execution"],
        authority="deterministic",
    )


def rp_node_rag_early(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_rag_early(state)
    state = _with_trace(state, "rag_early")
    return _record(
        state,
        node="rag_early",
        reason="governed_rag_retrieval",
        inputs_ref=["evidence_plan"],
        outputs_ref=["soc_kb_retrieval", "source_evidence"],
        authority="deterministic",
    )


def rp_node_composed_dispatch(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_composed_dispatch(state)
    state = _with_trace(state, "composed_dispatch")
    return _record(
        state,
        node="composed_dispatch",
        reason="resource_plan_step_walk",
        inputs_ref=["work_bundle", "evidence_plan.resource_plan"],
        outputs_ref=["candidate_spl", "spl_validation", "execution"],
        authority="deterministic",
    )


def rp_node_workflow_spl(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_workflow_spl(state)
    state = _with_trace(state, "workflow_spl")
    return _record(
        state,
        node="workflow_spl",
        reason="spl_worker",
        inputs_ref=["work_bundle"],
        outputs_ref=["candidate_spl", "spl_validation"],
        authority="deterministic",
    )


def rp_node_spl_source_resolve(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_spl_source_resolve(state)
    state = _with_trace(state, "spl_source_resolve")
    return _record(
        state,
        node="spl_source_resolve",
        reason="placeholder_slot_resolution",
        inputs_ref=["candidate_spl"],
        outputs_ref=["spl_validation"],
        authority="deterministic",
    )


def rp_node_mcp_execution_gate(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    if "execution" not in state:
        state = graph_node_execution(state)
    state = _with_trace(state, "mcp_execution_gate")
    return _record(
        state,
        node="mcp_execution_gate",
        reason="evaluate_mcp_execution",
        inputs_ref=["spl_validation", "normalized_spl"],
        outputs_ref=["execution", "human_review"],
        authority="deterministic",
    )


def rp_node_spl_validate(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else {}
    if spl_validation and spl_validation.get("approved") is not True:
        spl_validation = {**spl_validation, "execution_eligible": False}
        state = {**state, "spl_validation": spl_validation}
    state = _with_trace(state, "spl_validate")
    return _record(
        state,
        node="spl_validate",
        reason="candidate_only_gate",
        inputs_ref=["candidate_spl"],
        outputs_ref=["spl_validation"],
        authority="deterministic",
    )


def rp_node_context_sufficiency(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    sufficiency = state.get("context_sufficiency")
    if not isinstance(sufficiency, dict):
        sufficiency = {"status": "pending_finalize", "synthesis_readiness": "not_evaluated"}
    state = _with_trace(state, "context_sufficiency")
    return _record(
        {**state, "context_sufficiency": sufficiency},
        node="context_sufficiency",
        reason="pre_finalize_sufficiency_surface",
        inputs_ref=["source_evidence"],
        outputs_ref=["context_sufficiency"],
        authority="deterministic",
    )


def rp_node_decide_facts(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "decide_facts")
    return _record(
        state,
        node="decide_facts",
        reason="severity_mitre_authority_pending_finalize",
        inputs_ref=["mitre_decision", "severity_decision"],
        outputs_ref=["severity_decision", "mitre_mappings"],
        authority="deterministic",
    )


def _apply_policy_veto(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    """Enforce evidence-plan policy before response composition."""
    evidence_plan = _evidence_plan(state)
    veto = {
        "mcp_allowed": evidence_plan.get("mcp_allowed"),
        "spl_allowed": evidence_plan.get("spl_allowed"),
        "requires_hil": evidence_plan.get("requires_hil"),
    }
    updated: ResourcePlannerGraphState = {**state, "policy_veto": veto}

    if veto.get("mcp_allowed") is False:
        execution = updated.get("execution")
        if isinstance(execution, dict):
            if str(execution.get("status") or "").lower() not in {
                "skipped",
                "blocked",
                "requires_human_review",
                "failed",
            }:
                updated = {
                    **updated,
                    "execution": {
                        **execution,
                        "status": "blocked",
                        "block_reason": "policy_veto_mcp_not_allowed",
                    },
                }
        else:
            updated = {
                **updated,
                "execution": {
                    "status": "skipped",
                    "block_reason": "policy_veto_mcp_not_allowed",
                },
            }

    if veto.get("spl_allowed") is False:
        spl_validation = updated.get("spl_validation")
        if isinstance(spl_validation, dict):
            updated = {
                **updated,
                "spl_validation": {**spl_validation, "execution_eligible": False},
            }

    if veto.get("requires_hil") is True:
        review = updated.get("human_review")
        review_dict = dict(review) if isinstance(review, dict) else {}
        updated = {
            **updated,
            "human_review": {
                **review_dict,
                "required": True,
                "review_type": review_dict.get("review_type") or "policy_hil",
                "safe_message_for_user": review_dict.get("safe_message_for_user")
                or "Analyst review is required before this answer can proceed.",
            },
        }

    return updated


def rp_node_answer_guard(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "answer_guard")
    return _record(
        state,
        node="answer_guard",
        reason="answer_guard_pending_finalize",
        inputs_ref=["answer_contract"],
        outputs_ref=["answer_guard"],
        authority="deterministic",
    )


def rp_node_finalize(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = annotate_step_statuses(state)
    state = graph_node_context_finalize(state)
    state = _with_trace(state, "finalize")
    return _record(
        state,
        node="finalize",
        reason="context_finalize_compose_response",
        inputs_ref=["structured_context", "source_evidence"],
        outputs_ref=["response", "context_sufficiency", "severity_decision"],
        authority="deterministic",
    )


def _analyst_response_from_state(state: ResourcePlannerGraphState) -> Any:
    response = state.get("response")
    if isinstance(response, PlaceholderResponse):
        return response.analyst_response
    if isinstance(response, dict):
        return response.get("analyst_response")
    return None


def rp_node_validate_final_answer(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    response = state.get("response")
    visible_message = ""
    if isinstance(response, PlaceholderResponse):
        visible_message = str(response.message or "")
    validation = validate_final_answer(
        analyst_response=_analyst_response_from_state(state),
        answer_contract=state.get("answer_contract") if isinstance(state.get("answer_contract"), dict) else None,
        evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
        mitre_decision=state.get("mitre_decision") if isinstance(state.get("mitre_decision"), dict) else None,
        human_review=state.get("human_review") if isinstance(state.get("human_review"), dict) else None,
        planning_decision=state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else None,
        visible_message=visible_message,
    )
    state = {**state, "final_answer_validation": validation.model_dump()}
    state = _with_trace(state, "validate_final_answer")
    state = _record(
        state,
        node="validate_final_answer",
        reason="final_answer_validator",
        inputs_ref=["response", "answer_contract"],
        outputs_ref=["final_answer_validation"],
        authority="deterministic",
    )
    response = state.get("response")
    if isinstance(response, PlaceholderResponse):
        state = {**state, "response": patch_control_plane_trace_decision_log(response, state)}
    return state


def rp_node_human_review(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    review = state.get("human_review")
    if not isinstance(review, dict):
        review = {"required": False, "review_type": "none"}
        state = {**state, "human_review": review}
    state = _with_trace(state, "human_review")
    return _record(
        state,
        node="human_review",
        reason="hil_gate_surface",
        inputs_ref=["execution"],
        outputs_ref=["human_review"],
        authority="deterministic",
    )


def rp_node_policy_veto(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _apply_policy_veto(state)
    state = _with_trace(state, "policy_veto")
    return _record(
        state,
        node="policy_veto",
        reason="evidence_plan_policy_checks",
        inputs_ref=["evidence_plan"],
        outputs_ref=["policy_veto", "execution", "human_review", "spl_validation"],
        authority="deterministic",
    )


def _add_governance_chain(graph: StateGraph) -> None:
    graph.add_edge("spl_validate", "mcp_execution_gate")
    graph.add_edge("mcp_execution_gate", "context_sufficiency")
    graph.add_edge("context_sufficiency", "decide_facts")
    graph.add_edge("decide_facts", "answer_guard")
    graph.add_edge("answer_guard", "human_review")
    graph.add_edge("human_review", "policy_veto")
    graph.add_edge("policy_veto", "finalize")
    graph.add_edge("finalize", "validate_final_answer")
    graph.add_edge("validate_final_answer", END)


@lru_cache(maxsize=1)
def _compiled_resource_planner_graph() -> Any:
    graph: StateGraph = StateGraph(ResourcePlannerGraphState)
    graph.add_node("bootstrap", rp_node_bootstrap)
    graph.add_node("route_setup", rp_node_route_setup)
    graph.add_node("resource_planner_delegate", rp_node_resource_planner_delegate)
    graph.add_node("specialist_skill", rp_node_specialist_skill)
    graph.add_node("specialist_knowledge", rp_node_specialist_knowledge)
    graph.add_node("specialist_mcp", rp_node_specialist_mcp)
    graph.add_node("specialist_spl", rp_node_specialist_spl)
    graph.add_node("resource_planner_merge", rp_node_resource_planner_merge)
    graph.add_node("prepare_rag_only", rp_node_prepare_rag_only)
    graph.add_node("rag_early", rp_node_rag_early)
    graph.add_node("composed_dispatch", rp_node_composed_dispatch)
    graph.add_node("workflow_spl", rp_node_workflow_spl)
    graph.add_node("spl_source_resolve", rp_node_spl_source_resolve)
    for node_name in GOVERNANCE_NODE_NAMES:
        graph.add_node(node_name, globals()[f"rp_node_{node_name}"])

    graph.set_entry_point("bootstrap")
    graph.add_edge("bootstrap", "route_setup")
    graph.add_edge("route_setup", "resource_planner_delegate")
    graph.add_edge("resource_planner_delegate", "specialist_skill")
    graph.add_edge("specialist_skill", "specialist_knowledge")
    graph.add_edge("specialist_knowledge", "specialist_mcp")
    graph.add_edge("specialist_mcp", "specialist_spl")
    graph.add_edge("specialist_spl", "resource_planner_merge")
    graph.add_conditional_edges(
        "resource_planner_merge",
        _rp_dispatch_route,
        {
            "rag_only": "prepare_rag_only",
            "composed_dispatch": "composed_dispatch",
            "workflow_spl": "workflow_spl",
        },
    )
    graph.add_edge("prepare_rag_only", "rag_early")
    graph.add_conditional_edges(
        "rag_early",
        _rp_after_rag_early,
        {"governance_entry": "spl_validate", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_edge("composed_dispatch", "spl_validate")
    graph.add_conditional_edges(
        "workflow_spl",
        _rp_after_workflow_spl,
        {"rag_early": "rag_early", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_edge("spl_source_resolve", "mcp_execution_gate")
    _add_governance_chain(graph)
    return graph.compile()


def run_resource_planner_graph(
    request: ChatRequest,
    *,
    session_role: str | None = None,
) -> ResourcePlannerGraphState:
    """Execute the RP hierarchy graph."""
    return _compiled_resource_planner_graph().invoke(
        {"request": request, "session_role": session_role},
    )


def run_chat_via_resource_planner_graph(
    request: ChatRequest,
    *,
    progress: ProgressReporter | None = None,
    session_role: str | None = None,
    entrypoint: str = "chat",
) -> PlaceholderResponse:
    """Run ``/chat`` through the RP hierarchy graph when orchestration is enabled."""
    token = bind_progress_reporter(progress) if progress is not None else None
    started_at = datetime.now(UTC)
    try:
        emit_stage("queued")
        final_state = run_resource_planner_graph(request, session_role=session_role)
        response = final_state.get("response")
        if response is None:
            return build_live_chat_response(
                request,
                progress=progress,
                session_role=session_role,
                entrypoint=entrypoint,
            )
        note = response.note or ""
        suffix = "Orchestration: resource_planner_hierarchy (parity mode)."
        if suffix not in note:
            response = response.model_copy(update={"note": f"{note} {suffix}".strip()})
        response = patch_control_plane_trace_decision_log(response, final_state)
        finalize_chat_trace_from_state(
            final_state,
            response,
            started_at=started_at,
            session_role=session_role,
            entrypoint=entrypoint,
        )
        return response
    finally:
        if token is not None:
            reset_progress_reporter(token)


def resource_planner_graph_response(state: ResourcePlannerGraphState) -> PlaceholderResponse:
    response = state.get("response")
    if response is None:
        raise RuntimeError("resource planner graph did not produce a response")
    return patch_control_plane_trace_decision_log(response, state)


def resource_planner_graph_node_names() -> list[str]:
    compiled = _compiled_resource_planner_graph()
    nodes = getattr(compiled, "nodes", None)
    if isinstance(nodes, dict):
        return sorted(nodes.keys())
    return []


def resource_planner_graph_edges() -> set[tuple[str, str]]:
    compiled = _compiled_resource_planner_graph()
    graph = compiled.get_graph()
    return {(edge.source, edge.target) for edge in graph.edges}


def resource_planner_governance_inbound_targets() -> dict[str, set[str]]:
    edges = resource_planner_graph_edges()
    inbound: dict[str, set[str]] = {name: set() for name in GOVERNANCE_NODE_NAMES}
    for source, target in edges:
        if target in inbound:
            inbound[target].add(source)
    return inbound
