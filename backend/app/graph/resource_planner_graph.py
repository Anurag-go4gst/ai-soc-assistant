"""Resource Planner LangGraph hierarchy.

Callable from tests always; wired to ``/chat`` when ``LANGGRAPH_ORCHESTRATION_ENABLED=true``.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Iterator, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.chat.control_plane_trace import patch_control_plane_trace_decision_log
from app.chat.decision_record import emit_decision_record
from app.chat.final_answer_validator import validate_final_answer
from app.chat.pipeline import (
    ChatPipelineState,
    build_rp_degraded_placeholder_response,
    finalize_chat_trace_from_state,
    graph_node_composed_dispatch,
    graph_node_context_finalize,
    graph_node_execution,
    graph_node_ensure_workflow_plan,
    graph_node_init_routing,
    graph_node_prepare_rag_only,
    graph_node_rag_early,
    graph_node_shadow_tail,
    graph_node_spl_source_resolve,
    graph_node_workflow_spl,
)
from app.chat.session_context import resolve_session_context
from app.config import settings
from app.chat.progress_context import bind_progress_reporter, emit_stage, reset_progress_reporter
from app.chat.progress_events import ProgressReporter
from app.synthesis.turn_timing import benchmark_run_kind_override, synthesis_turn_timing_scope
from app.planner.executor import annotate_step_statuses, has_composed_plan
from app.planner.planner_hierarchy import (
    DecisionRecord,
    KnowledgeSpecialistReport,
    McpSpecialistReport,
    SkillSpecialistReport,
    SpecialistDelegation,
    SpecialistReport,
    SplSpecialistReport,
    WorkBundle,
    build_planner_iteration,
    materialize_resource_plan_from_bundle,
    new_decision_record_id,
)
from app.planner.knowledge_specialist import build_knowledge_audit_report
from app.planner.mcp_specialist import build_mcp_audit_report
from app.planner.spl_specialist import build_spl_audit_report
from app.planner.resource_plan import ResourcePlan
from app.planner.specialist_registry import load_specialist_registry
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

logger = logging.getLogger(__name__)

_rp_graph_invoke_depth: ContextVar[int] = ContextVar("_rp_graph_invoke_depth", default=0)

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

DispatchRoute = Literal["rag_only", "composed_dispatch", "workflow_spl", "non_planned_finalize"]
AfterWorkflowSpl = Literal["rag_early", "spl_source_resolve"]
AfterRagEarly = Literal["governance_entry", "spl_source_resolve"]

_SPECIALIST_NODE_NAMES: tuple[str, ...] = (
    "specialist_skill",
    "specialist_knowledge",
    "specialist_mcp",
    "specialist_spl",
)


_MERGE_DECISION_VALIDATED = "specialist_reports_merged"


def rp_graph_invoke_active() -> bool:
    """True while this logical context is inside ``run_resource_planner_graph``."""
    return _rp_graph_invoke_depth.get() > 0


@contextmanager
def _rp_graph_invoke_scope() -> Iterator[None]:
    token: Token = _rp_graph_invoke_depth.set(_rp_graph_invoke_depth.get() + 1)
    try:
        yield
    finally:
        _rp_graph_invoke_depth.reset(token)


def guard_rp_imperative_fallback(entrypoint: str) -> None:
    """Block imperative fallback from nesting inside an active RP graph invoke."""
    from app.config import settings

    if not entrypoint.startswith("rp_"):
        return
    if settings.langgraph_orchestration_enabled and rp_graph_invoke_active():
        raise RuntimeError(
            "resource planner graph fallback must not recurse into RP orchestration"
        )


def _reject_validated_work_bundle(
    state: ResourcePlannerGraphState,
    *,
    reason: str,
    detail: str,
) -> ResourcePlannerGraphState:
    logger.warning("validated_work_bundle rejected: %s (%s)", reason, detail)
    return _record(
        state,
        node="work_bundle.apply",
        reason=reason,
        inputs_ref=["validated_work_bundle"],
        outputs_ref=[],
        authority="resource_planner",
    )


def _reduce_specialist_reports(
    current: list[dict[str, Any]],
    update: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge parallel specialist reports without amplifying identical replays."""
    reports_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for report in [*current, *update]:
        if not isinstance(report, dict):
            raise TypeError("specialist report must be a mapping")
        delegation_id = report.get("delegation_id")
        specialist_id = report.get("specialist_id")
        if not isinstance(delegation_id, str) or not delegation_id:
            raise ValueError("specialist report requires delegation_id")
        if not isinstance(specialist_id, str) or not specialist_id:
            raise ValueError("specialist report requires specialist_id")
        key = (delegation_id, specialist_id)
        existing = reports_by_key.get(key)
        if existing is not None and existing != report:
            raise ValueError(
                "conflicting specialist reports for "
                f"delegation_id={delegation_id!r}, specialist_id={specialist_id!r}"
            )
        reports_by_key[key] = report
    return [reports_by_key[key] for key in sorted(reports_by_key)]


class ResourcePlannerGraphState(ChatPipelineState, total=False):
    rp_graph_trace: dict[str, Any]
    planner_iteration: dict[str, Any]
    work_bundle: dict[str, Any]
    validated_work_bundle: dict[str, Any] | None
    specialist_reports: Annotated[list[dict[str, Any]], _reduce_specialist_reports]
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


def _coerce_specialist_reports(raw_reports: list[Any]) -> list[SpecialistReport]:
    ordered = sorted(
        [item for item in raw_reports if isinstance(item, dict)],
        key=lambda item: str(item.get("specialist_id") or ""),
    )
    reports: list[SpecialistReport] = []
    for raw in ordered:
        specialist_id = raw.get("specialist_id")
        if specialist_id == "skill":
            reports.append(SkillSpecialistReport.model_validate(raw))
        elif specialist_id == "knowledge":
            reports.append(KnowledgeSpecialistReport.model_validate(raw))
        elif specialist_id == "mcp":
            reports.append(McpSpecialistReport.model_validate(raw))
        elif specialist_id == "spl":
            reports.append(SplSpecialistReport.model_validate(raw))
    return reports


def _fan_out_specialists(state: ResourcePlannerGraphState) -> list[Send]:
    return [Send(node, state) for node in _SPECIALIST_NODE_NAMES]


def _append_specialist_traces(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    trace = dict(state.get("rp_graph_trace") or {})
    visited = list(trace.get("visited_nodes") or [])
    for node in _SPECIALIST_NODE_NAMES:
        if node not in visited:
            visited.append(node)
    trace["visited_nodes"] = visited
    return {**state, "rp_graph_trace": trace}


def _record_parallel_specialist_decisions(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    """Emit specialist audit records in stable order after parallel fan-in."""
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    skill_id = str(routed.get("skill") or "")
    report_reasons = {
        str(report.get("specialist_id") or ""): str(report.get("decision_reason") or "")
        for report in state.get("specialist_reports") or []
        if isinstance(report, dict)
    }
    decisions = [
        (
            "specialist.skill",
            "skill_lane_advisory",
            "specialist:skill",
            ["routed", "canonical_planning_input"],
            ["specialist_reports"],
        ),
        (
            "specialist.knowledge",
            report_reasons.get("knowledge") or "knowledge_lane_idle",
            "specialist:knowledge",
            ["intent_classification", "evidence_plan"],
            ["specialist_reports"],
        ),
        (
            "specialist.mcp",
            report_reasons.get("mcp") or "mcp_unavailable",
            "specialist:mcp",
            ["evidence_plan"],
            ["specialist_reports"],
        ),
        (
            "specialist.spl",
            report_reasons.get("spl") or "spl_unavailable",
            "specialist:spl",
            ["evidence_plan"],
            ["specialist_reports"],
        ),
    ]
    for node, reason, authority, inputs_ref, outputs_ref in decisions:
        state = emit_decision_record(
            state,
            DecisionRecord(
                record_id=new_decision_record_id(),
                node=node,
                authority=authority,
                decision_reason=reason if node != "specialist.skill" else f"{reason}:{skill_id or 'unknown'}",
                inputs_ref=inputs_ref,
                outputs_ref=outputs_ref,
            ),
        )
    return state


def _apply_work_bundle_to_workers(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    """Sync policy-validated bundle enrichments into evidence_plan for downstream workers."""
    wb_raw = state.get("validated_work_bundle")
    if not isinstance(wb_raw, dict) or not wb_raw.get("tasks"):
        return state
    try:
        bundle = WorkBundle.model_validate(wb_raw)
    except Exception as exc:
        return _reject_validated_work_bundle(
            state,
            reason=f"validated_work_bundle_model_invalid:{type(exc).__name__}",
            detail=str(exc),
        )
    if bundle.merge_decision_reason != _MERGE_DECISION_VALIDATED:
        return state
    try:
        plan = materialize_resource_plan_from_bundle(bundle)
    except Exception as exc:
        return _reject_validated_work_bundle(
            state,
            reason=f"validated_work_bundle_policy_rejected:{type(exc).__name__}",
            detail=str(exc),
        )
    evidence_plan = dict(_evidence_plan(state))
    evidence_plan["resource_plan"] = plan.model_dump()
    return {**state, "evidence_plan": evidence_plan}


def rp_node_bootstrap(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_init_routing(state)
    from app.chat.canonical_planning_orchestrator import run_canonical_planning

    state = run_canonical_planning(state)
    state = _with_trace(state, "bootstrap")
    return _record(
        state,
        node="bootstrap",
        reason="query_and_evidence_plan_ready",
        inputs_ref=["request"],
        outputs_ref=["evidence_plan", "query_to_intent", "canonical_planning_input"],
        authority="deterministic",
    )


def rp_node_route_resolution(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_shadow_tail(state)
    state = _with_trace(state, "route_resolution")
    return _record(
        state,
        node="route_resolution",
        reason="route_contract_and_planning_decision_ready",
        inputs_ref=["routed", "route_plan_shadow"],
        outputs_ref=[
            "route_plan_shadow",
            "llm_plan_validation",
            "skill_selection",
            "selected_skill_chain",
        ],
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
        inputs_ref=[],
        outputs_ref=["specialist_delegations"],
    )


def rp_node_specialist_skill(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    canonical = (
        state.get("canonical_planning_input")
        if isinstance(state.get("canonical_planning_input"), dict)
        else {}
    )
    routing = canonical.get("routing") if isinstance(canonical.get("routing"), dict) else {}
    catalogue_tier = routing.get("catalogue_tier")
    warnings = [] if catalogue_tier is not None else ["canonical_routing_unavailable"]
    report = SkillSpecialistReport(
        delegation_id="del:skill",
        decision_reason="route_lane",
        skill_id=str(routed.get("skill") or ""),
        catalogue_tier=str(catalogue_tier) if catalogue_tier is not None else None,
        warnings=warnings,
    ).model_dump()
    return {"specialist_reports": [report]}


def rp_node_specialist_knowledge(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    intent = state.get("intent_classification")
    report = build_knowledge_audit_report(
        intent_classification=intent if isinstance(intent, dict) else None,
        evidence_plan=_evidence_plan(state),
    ).model_dump()
    return {"specialist_reports": [report]}


def rp_node_specialist_mcp(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    report = build_mcp_audit_report(evidence_plan=_evidence_plan(state)).model_dump()
    return {"specialist_reports": [report]}


def rp_node_specialist_spl(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    report = build_spl_audit_report(evidence_plan=_evidence_plan(state)).model_dump()
    return {"specialist_reports": [report]}


def rp_node_resource_planner_merge(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _append_specialist_traces(state)
    state = _record_parallel_specialist_decisions(state)
    evidence_plan = _evidence_plan(state)
    resource_plan_raw = evidence_plan.get("resource_plan")
    delegations_raw = state.get("specialist_delegations") or []
    reports = _coerce_specialist_reports(list(state.get("specialist_reports") or []))
    if isinstance(resource_plan_raw, dict):
        plan = ResourcePlan.model_validate(resource_plan_raw)
        delegations = [
            SpecialistDelegation.model_validate(item)
            for item in delegations_raw
            if isinstance(item, dict)
        ]
        iteration = build_planner_iteration(
            iteration=0,
            resource_plan=plan,
            delegations=delegations,
            reports=reports,
            bundle_id="bundle:rp",
        )
        bundle = iteration.bundle
        if bundle is not None:
            evidence_plan_out = dict(evidence_plan)
            evidence_plan_out["resource_plan"] = iteration.resource_plan.model_dump()
            bundle_payload = bundle.model_dump()
            validated_payload = (
                bundle_payload
                if bundle.merge_decision_reason == _MERGE_DECISION_VALIDATED
                else None
            )
            state = {
                **state,
                "work_bundle": bundle_payload,
                "validated_work_bundle": validated_payload,
                "planner_iteration": iteration.model_dump(),
                "evidence_plan": evidence_plan_out,
            }
    state = _with_trace(state, "resource_planner_merge")
    return _record(
        state,
        node="resource_planner.merge",
        reason="fan_in_work_bundle",
        inputs_ref=[
            "specialist_reports",
            "specialist_delegations",
            "evidence_plan.resource_plan",
        ],
        outputs_ref=[
            "work_bundle",
            "validated_work_bundle",
            "planner_iteration",
            "evidence_plan",
        ],
    )


def _rp_dispatch_route(state: ResourcePlannerGraphState) -> DispatchRoute:
    from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome

    read = read_canonical_planning_outcome(state)
    if read.kind != OutcomeReadKind.VALID or read.outcome is None or read.outcome.status != "planned":
        return "non_planned_finalize"
    plan = _evidence_plan(state)
    if plan.get("answer_mode") == "rag_only":
        return "rag_only"
    if has_composed_plan(state):
        return "composed_dispatch"
    return "workflow_spl"


def rp_node_non_planned_finalize(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    from app.chat.canonical_mode import build_non_planned_dispatch_state
    from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome

    read = read_canonical_planning_outcome(state)
    if read.kind == OutcomeReadKind.VALID and read.outcome is not None and read.outcome.status != "planned":
        state = build_non_planned_dispatch_state(state, status=read.outcome.status)
    state = _with_trace(state, "non_planned_finalize")
    return _record(
        state,
        node="non_planned_finalize",
        reason="canonical_non_planned_short_circuit",
        inputs_ref=["canonical_planning_outcome"],
        outputs_ref=["plan_dispatch_trace"],
        authority="deterministic",
    )


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
    state = _apply_work_bundle_to_workers(state)
    state = graph_node_prepare_rag_only(state)
    state = _with_trace(state, "prepare_rag_only")
    return _record(
        state,
        node="prepare_rag_only",
        reason="rag_only_path",
        inputs_ref=["validated_work_bundle", "evidence_plan"],
        outputs_ref=["evidence_plan", "execution"],
        authority="deterministic",
    )


def rp_node_rag_early(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_rag_early(state)
    state = _with_trace(state, "rag_early")
    return _record(
        state,
        node="rag_early",
        reason="governed_rag_retrieval",
        inputs_ref=["workflow_plan"],
        outputs_ref=["soc_kb_retrieval"],
        authority="deterministic",
    )


def rp_node_composed_dispatch(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _apply_work_bundle_to_workers(state)
    if isinstance(state.get("approved_investigation_envelope"), dict):
        state = graph_node_ensure_workflow_plan(state)
    state = graph_node_composed_dispatch(state)
    state = _with_trace(state, "composed_dispatch")
    return _record(
        state,
        node="composed_dispatch",
        reason="resource_plan_step_walk",
        inputs_ref=["validated_work_bundle", "evidence_plan.resource_plan"],
        outputs_ref=["evidence_plan", "candidate_spl", "spl_validation", "execution"],
        authority="deterministic",
    )


def rp_node_workflow_spl(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _apply_work_bundle_to_workers(state)
    state = graph_node_workflow_spl(state)
    state = _with_trace(state, "workflow_spl")
    return _record(
        state,
        node="workflow_spl",
        reason="spl_worker",
        inputs_ref=["validated_work_bundle", "evidence_plan"],
        outputs_ref=["evidence_plan", "candidate_spl", "spl_validation"],
        authority="deterministic",
    )


def rp_node_spl_source_resolve(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = graph_node_spl_source_resolve(state)
    state = _with_trace(state, "spl_source_resolve")
    return _record(
        state,
        node="spl_source_resolve",
        reason="placeholder_slot_resolution",
        inputs_ref=["candidate_spl", "spl_validation"],
        outputs_ref=["spl_validation"],
        authority="deterministic",
    )


def rp_node_mcp_execution_gate(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    if "execution" not in state:
        # A contracted execution phase may be inserted after a read-only/RAG
        # resource wave.  It still needs the normal workflow envelope so the
        # gate can record an honest skip/block instead of raising outside the
        # Resource Planner hub.
        if isinstance(state.get("approved_investigation_envelope"), dict):
            state = graph_node_ensure_workflow_plan(state)
        state = graph_node_execution(state)
    state = _with_trace(state, "mcp_execution_gate")
    return _record(
        state,
        node="mcp_execution_gate",
        reason="evaluate_mcp_execution",
        inputs_ref=["spl_validation", "spl_validation.normalized_spl"],
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
        inputs_ref=["spl_validation"],
        outputs_ref=["spl_validation"],
        authority="deterministic",
    )


def rp_node_context_sufficiency(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    from app.evidence.evidence_sufficiency import attach_evidence_sufficiency
    from app.chat.investigation_run_compiler import attach_investigation_observation

    state = attach_evidence_sufficiency(state)
    state = attach_investigation_observation(state)
    state = _with_trace(state, "context_sufficiency")
    return _record(
        state,
        node="context_sufficiency",
        reason="evidence_state_rqc_sufficiency",
        inputs_ref=["resolved_query_contract", "evidence_state", "evidence_plan", "source_evidence"],
        outputs_ref=[
            "evidence_sufficiency",
            "context_sufficiency",
            "evidence_state",
            "investigation_progress",
            "investigation_run_status",
        ],
        authority="deterministic",
    )


def rp_node_decide_facts(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "decide_facts")
    return _record(
        state,
        node="decide_facts",
        reason="severity_mitre_authority_pending_finalize",
        inputs_ref=[],
        outputs_ref=[],
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

    return updated


def rp_node_answer_guard(state: ResourcePlannerGraphState) -> ResourcePlannerGraphState:
    state = _with_trace(state, "answer_guard")
    return _record(
        state,
        node="answer_guard",
        reason="answer_guard_pending_finalize",
        inputs_ref=[],
        outputs_ref=[],
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
        inputs_ref=["evidence_plan", "execution", "soc_kb_retrieval", "spl_validation"],
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
        inputs_ref=[
            "response",
            "answer_contract",
            "evidence_plan",
            "mitre_decision",
            "human_review",
            "planning_decision",
        ],
        outputs_ref=["final_answer_validation", "response"],
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
        inputs_ref=["human_review"],
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
        inputs_ref=["evidence_plan", "execution", "spl_validation"],
        outputs_ref=["policy_veto", "execution", "spl_validation"],
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
    graph.add_node("route_resolution", rp_node_route_resolution)
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
    graph.add_node("non_planned_finalize", rp_node_non_planned_finalize)
    graph.add_node("spl_source_resolve", rp_node_spl_source_resolve)
    for node_name in GOVERNANCE_NODE_NAMES:
        graph.add_node(node_name, globals()[f"rp_node_{node_name}"])

    graph.set_entry_point("bootstrap")
    graph.add_edge("bootstrap", "route_resolution")
    graph.add_edge("route_resolution", "resource_planner_delegate")
    graph.add_conditional_edges("resource_planner_delegate", _fan_out_specialists)
    for specialist_node in _SPECIALIST_NODE_NAMES:
        graph.add_edge(specialist_node, "resource_planner_merge")
    graph.add_conditional_edges(
        "resource_planner_merge",
        _rp_dispatch_route,
        {
            "rag_only": "prepare_rag_only",
            "composed_dispatch": "composed_dispatch",
            "workflow_spl": "workflow_spl",
            "non_planned_finalize": "non_planned_finalize",
        },
    )
    graph.add_edge("non_planned_finalize", "finalize")
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
    session_resolution = resolve_session_context(request)
    initial_state: ResourcePlannerGraphState = {
        "request": request,
        "session_role": session_role,
        "session_id": session_resolution.session_id,
        "session_pins": session_resolution.pins,
        "session_context_resolution": session_resolution,
        "effective_query": session_resolution.effective_query,
        "handoff_resume": session_resolution.handoff_resume,
    }
    with _rp_graph_invoke_scope():
        return _compiled_resource_planner_graph().invoke(initial_state)


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
        with synthesis_turn_timing_scope(run_kind=benchmark_run_kind_override()):
            emit_stage("queued")
            final_state = run_resource_planner_graph(request, session_role=session_role)
            response = final_state.get("response")
            if response is None:
                degraded = build_rp_degraded_placeholder_response(
                    request,
                    state=final_state,
                    session_role=session_role,
                    entrypoint="rp_fallback",
                    reason="graph_response_missing",
                )
                finalize_chat_trace_from_state(
                    final_state,
                    degraded,
                    started_at=started_at,
                    session_role=session_role,
                    entrypoint=entrypoint,
                )
                return degraded
            note = response.note or ""
            suffix = "Orchestration: resource_planner_hierarchy."
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


GRAPH_START_SENTINEL = "__start__"
GRAPH_END_SENTINEL = "__end__"


@dataclass(frozen=True)
class TopologyReconciliation:
    """Result of comparing documented topology against runtime-derived topology."""

    matched: frozenset[tuple[str, str]]
    documented_only: frozenset[tuple[str, str]]
    runtime_only: frozenset[tuple[str, str]]

    @property
    def is_consistent(self) -> bool:
        return not self.documented_only and not self.runtime_only


def _strip_sentinel_edges(edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    sentinels = {GRAPH_START_SENTINEL, GRAPH_END_SENTINEL}
    return {(src, dst) for src, dst in edges if src not in sentinels and dst not in sentinels}


def reconcile_topology(
    *,
    fixed: set[tuple[str, str]],
    mapped: set[tuple[str, str]],
    dynamic: set[tuple[str, str]],
    documented: set[tuple[str, str]],
) -> TopologyReconciliation:
    """Compare a documented edge set against runtime-derived edges.

    Pure so mutation controls can inject topology instead of rebuilding the
    ``lru_cache``d compiled graph. Sentinel start/end edges are normalized away
    because the documented set describes node-to-node wiring only.
    """
    runtime = _strip_sentinel_edges(fixed | mapped | dynamic)
    documented_normalized = _strip_sentinel_edges(documented)
    return TopologyReconciliation(
        matched=frozenset(runtime & documented_normalized),
        documented_only=frozenset(documented_normalized - runtime),
        runtime_only=frozenset(runtime - documented_normalized),
    )


def unreachable_nodes(
    *,
    nodes: set[str],
    edges: set[tuple[str, str]],
    entry: str = GRAPH_START_SENTINEL,
) -> set[str]:
    """Registered nodes that no path from ``entry`` can reach.

    Pure for the same reason ``reconcile_topology`` is: an orphan must be
    provable by injecting a topology, not only by compiling the live graph.
    """
    outbound: dict[str, set[str]] = {}
    for source, target in edges:
        outbound.setdefault(source, set()).add(target)

    reached: set[str] = set()
    frontier = [entry]
    while frontier:
        current = frontier.pop()
        for target in outbound.get(current, set()):
            if target not in reached:
                reached.add(target)
                frontier.append(target)
    return {node for node in nodes if node not in reached}


def resource_planner_fixed_edges() -> set[tuple[str, str]]:
    """Unconditional ``add_edge`` wiring, including start/end sentinels."""
    builder = _compiled_resource_planner_graph().builder
    return {(str(source), str(target)) for source, target in builder.edges}


def resource_planner_mapped_conditional_edges() -> set[tuple[str, str]]:
    """Conditional destinations declared with an explicit path map."""
    builder = _compiled_resource_planner_graph().builder
    edges: set[tuple[str, str]] = set()
    for source, branches in builder.branches.items():
        for branch in branches.values():
            for target in (branch.ends or {}).values():
                edges.add((str(source), str(target)))
    return edges


def resource_planner_dynamic_send_targets() -> list[str]:
    """Fan-out targets of the delegate's unmapped ``Send`` branch.

    Resolved by invoking the fan-out contract directly. The branch is located by
    name so a rename or an accidentally *mapped* delegate branch fails loudly
    rather than silently reporting the wrong source of truth; reading the
    callable back out of LangGraph's ``BranchSpec`` wrapper would be framework
    internals, which this contract deliberately avoids.
    """
    builder = _compiled_resource_planner_graph().builder
    branches = builder.branches.get("resource_planner_delegate") or {}
    if list(branches) != ["_fan_out_specialists"]:
        raise RuntimeError(f"unexpected delegate branch registration: {sorted(branches)}")
    if branches["_fan_out_specialists"].ends is not None:
        raise RuntimeError("delegate fan-out is mapped; dynamic Send contract no longer holds")
    return [str(send.node) for send in _fan_out_specialists({})]


def resource_planner_dynamic_send_edges() -> set[tuple[str, str]]:
    return {("resource_planner_delegate", target) for target in resource_planner_dynamic_send_targets()}


def resource_planner_registered_node_names() -> set[str]:
    """Node names the builder actually registered (no start/end sentinels)."""
    return {str(name) for name in _compiled_resource_planner_graph().builder.nodes}


def resource_planner_topology_reconciliation() -> TopologyReconciliation:
    return reconcile_topology(
        fixed=resource_planner_fixed_edges(),
        mapped=resource_planner_mapped_conditional_edges(),
        dynamic=resource_planner_dynamic_send_edges(),
        documented=_documented_resource_planner_edges(),
    )


def resource_planner_unreachable_nodes() -> set[str]:
    return unreachable_nodes(
        nodes=resource_planner_registered_node_names(),
        edges=resource_planner_fixed_edges()
        | resource_planner_mapped_conditional_edges()
        | resource_planner_dynamic_send_edges(),
    )


def _documented_resource_planner_edges() -> set[tuple[str, str]]:
    """Human-readable topology, pinned to runtime by ``reconcile_topology``.

    This set is documentation, never a truth source. ``resource_planner_graph_edges()``
    used to union it into the introspected edges, so an invented pair here became a
    member of the set the assertions checked; the reconciliation contract now requires
    exact equality with builder-derived fixed, mapped-conditional, and dynamic ``Send``
    edges instead.
    """
    edges: set[tuple[str, str]] = {
        ("bootstrap", "route_resolution"),
        ("route_resolution", "resource_planner_delegate"),
    }
    for node in _SPECIALIST_NODE_NAMES:
        edges.add(("resource_planner_delegate", node))
        edges.add((node, "resource_planner_merge"))
    for target in ("prepare_rag_only", "composed_dispatch", "workflow_spl", "non_planned_finalize"):
        edges.add(("resource_planner_merge", target))
    edges.update(
        {
            ("non_planned_finalize", "finalize"),
            ("prepare_rag_only", "rag_early"),
            ("composed_dispatch", "spl_validate"),
            ("workflow_spl", "rag_early"),
            ("workflow_spl", "spl_source_resolve"),
            ("rag_early", "spl_validate"),
            ("rag_early", "spl_source_resolve"),
            ("spl_source_resolve", "mcp_execution_gate"),
            ("spl_validate", "mcp_execution_gate"),
            ("mcp_execution_gate", "context_sufficiency"),
            ("context_sufficiency", "decide_facts"),
            ("decide_facts", "answer_guard"),
            ("answer_guard", "human_review"),
            ("human_review", "policy_veto"),
            ("policy_veto", "finalize"),
            ("finalize", "validate_final_answer"),
        }
    )
    return edges


def resource_planner_graph_edges() -> set[tuple[str, str]]:
    """Runtime-derived topology only.

    ``get_graph()`` is not used: it omits every conditional destination and
    reports a phantom ``resource_planner_delegate -> __end__`` for the unmapped
    fan-out branch.
    """
    return (
        resource_planner_fixed_edges()
        | resource_planner_mapped_conditional_edges()
        | resource_planner_dynamic_send_edges()
    )


def resource_planner_governance_inbound_targets() -> dict[str, set[str]]:
    edges = resource_planner_graph_edges()
    inbound: dict[str, set[str]] = {name: set() for name in GOVERNANCE_NODE_NAMES}
    for source, target in edges:
        if target in inbound:
            inbound[target].add(source)
    return inbound
