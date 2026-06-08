"""Phase 12: planner-led LangGraph shadow fan-out/fan-in (parity only).

Runs a topology aligned with the target planner-led architecture. Does not
replace the imperative ``/chat`` path unless ``LANGGRAPH_ORCHESTRATION_ENABLED``
is set separately for the legacy P1 parity wrapper.

Shadow execution requires ``AI_SOC_LANGGRAPH_SHADOW_ENABLED=true`` and is intended
for tests/trace — not default runtime cutover.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.chat.mitre_branch import run_mitre_evidence_branch
from app.chat.pipeline import (
    ChatPipelineState,
    graph_node_context_finalize,
    graph_node_evidence_planning,
    graph_node_execution,
    graph_node_init_routing,
    graph_node_prepare_rag_only,
    graph_node_query_to_intent,
    graph_node_rag_early,
    graph_node_shadow_enrichment,
    graph_node_workflow_spl,
)
from app.config import settings
from app.risk.severity_policy import decide_severity
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

BranchName = Literal[
    "rag",
    "spl",
    "evidence",
    "mitre",
    "severity",
    "hil",
    "clarification",
    "block",
    "unsafe_blocked",
]

_RAG_PIPELINE_PATH_TYPES = frozenset({"rag_only", "generic_soc_guidance"})


class PlannerLedShadowState(ChatPipelineState, total=False):
    branch_results: dict[str, Any]
    shadow_graph_trace: dict[str, Any]


def _planning(state: PlannerLedShadowState) -> dict[str, Any]:
    payload = state.get("planning_decision")
    return payload if isinstance(payload, dict) else {}


def _branches(state: PlannerLedShadowState) -> list[str]:
    raw = _planning(state).get("branches")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def _path_type(state: PlannerLedShadowState) -> str | None:
    value = _planning(state).get("path_type")
    return str(value) if isinstance(value, str) and value else None


def _branch_scheduled(state: PlannerLedShadowState, branch: BranchName) -> bool:
    branches = _branches(state)
    if branch in branches:
        return True
    if branch == "unsafe_blocked" and _path_type(state) == "unsafe_blocked":
        return True
    if branch == "block" and ("block" in branches or _path_type(state) == "unsafe_blocked"):
        return True
    return False


def _trace_append(state: PlannerLedShadowState, node: str) -> dict[str, Any]:
    trace = dict(state.get("shadow_graph_trace") or {})
    visited = list(trace.get("visited_nodes") or [])
    visited.append(node)
    trace["visited_nodes"] = visited
    trace["routing_authority"] = "planning_decision"
    return trace


def _query_signals(state: PlannerLedShadowState) -> dict[str, Any] | None:
    q2i = state.get("query_to_intent")
    if not isinstance(q2i, dict):
        return None
    signals = q2i.get("query_signals")
    return signals if isinstance(signals, dict) else None


def _use_case_id(state: PlannerLedShadowState) -> str | None:
    selected = state.get("selected_use_case")
    if selected is not None and getattr(selected, "use_case_id", None):
        return str(selected.use_case_id)
    value = _planning(state).get("use_case_id")
    return str(value) if isinstance(value, str) and value else None


def shadow_node_query_understanding(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_init_routing(state)
    state = graph_node_query_to_intent(state)
    trace = _trace_append(state, "query_understanding")
    return {**state, "shadow_graph_trace": trace, "branch_results": {}}


def shadow_node_planning(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_evidence_planning(state)
    trace = _trace_append(state, "planning")
    planning = _planning(state)
    trace["path_type"] = planning.get("path_type")
    trace["selected_branches"] = _branches(state)
    return {**state, "shadow_graph_trace": trace}


def shadow_node_route_setup(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_shadow_enrichment(state)
    return {**state, "shadow_graph_trace": _trace_append(state, "route_setup")}


def shadow_node_rag_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "rag"):
        plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
        results["rag_result"] = {
            "branch_scheduled": True,
            "needs_rag": plan.get("needs_rag"),
            "rag_phase": plan.get("rag_phase"),
            "answer_mode": plan.get("answer_mode"),
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "rag_branch")}


def shadow_node_spl_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "spl"):
        plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
        planning = _planning(state)
        results["spl_result"] = {
            "branch_scheduled": True,
            "spl_allowed": plan.get("spl_allowed"),
            "needs_spl": plan.get("needs_spl"),
            "execution_enabled": planning.get("execution_enabled", False),
            "blocked_tools": list(planning.get("blocked_tools") or []),
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "spl_branch")}


def shadow_node_evidence_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "evidence"):
        plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
        missing = plan.get("missing_fields") or plan.get("missing_evidence") or []
        results["evidence_plan"] = plan
        results["missing_evidence"] = list(missing) if isinstance(missing, list) else []
        results["limitations"] = list(plan.get("limitations") or [])
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "evidence_branch")}


def shadow_node_mitre_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "mitre"):
        request = state["request"]
        query = state.get("effective_query") or request.message
        _, decision, branch = run_mitre_evidence_branch(
            query=query,
            question_ref=_planning(state).get("question_ref"),
            use_case_id=_use_case_id(state),
            source_refs=[],
            intent_classification=state.get("intent_classification"),
            evidence_plan=state.get("evidence_plan"),
            planning_decision=state.get("planning_decision"),
            query_signals=_query_signals(state),
            source_evidence=[],
            structured_context={},
            alert_context_present=bool((_query_signals(state) or {}).get("alert_context_present")),
        )
        results["mitre_branch_result"] = {
            "branch": branch.model_dump(),
            "decision": decision,
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "mitre_branch")}


def shadow_node_severity_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "severity"):
        severity = decide_severity(_use_case_id(state), {}, [])
        results["severity_result"] = severity.model_dump()
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "severity_branch")}


def shadow_node_hil_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "hil"):
        planning = _planning(state)
        results["hil_status"] = {
            "hil_required": bool(planning.get("hil_required")),
            "clarification_needed": bool(planning.get("clarification_needed")),
            "authority_source": planning.get("authority_source"),
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "hil_branch")}


def shadow_node_unsafe_blocked_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "unsafe_blocked") or _branch_scheduled(state, "block"):
        planning = _planning(state)
        results["unsafe_status"] = {
            "path_type": planning.get("path_type"),
            "blocked_tools": list(planning.get("blocked_tools") or []),
            "execution_enabled": planning.get("execution_enabled", False),
            "unsafe_blocked": _path_type(state) == "unsafe_blocked",
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "unsafe_blocked_branch")}


def shadow_node_clarification_branch(state: PlannerLedShadowState) -> PlannerLedShadowState:
    results = dict(state.get("branch_results") or {})
    if _branch_scheduled(state, "clarification"):
        planning = _planning(state)
        results["clarification_status"] = {
            "clarification_needed": bool(planning.get("clarification_needed")),
            "path_type": planning.get("path_type"),
            "reason": planning.get("reason"),
        }
    return {**state, "branch_results": results, "shadow_graph_trace": _trace_append(state, "clarification_branch")}


def shadow_node_fan_in_aggregate(state: PlannerLedShadowState) -> PlannerLedShadowState:
    partial = dict(state.get("branch_results") or {})
    planning = _planning(state)
    aggregated = {
        "rag_result": partial.get("rag_result"),
        "spl_result": partial.get("spl_result"),
        "evidence_plan": partial.get("evidence_plan") or state.get("evidence_plan"),
        "mitre_branch_result": partial.get("mitre_branch_result"),
        "severity_result": partial.get("severity_result"),
        "hil_status": partial.get("hil_status"),
        "unsafe_status": partial.get("unsafe_status"),
        "clarification_status": partial.get("clarification_status"),
        "missing_evidence": list(partial.get("missing_evidence") or []),
        "limitations": list(partial.get("limitations") or []),
        "path_type": planning.get("path_type"),
        "selected_branches": _branches(state),
    }
    trace = _trace_append(state, "fan_in_aggregate")
    trace["fan_in_complete"] = True
    trace["branch_results_keys"] = sorted(k for k, v in aggregated.items() if v is not None)
    return {**state, "branch_results": aggregated, "shadow_graph_trace": trace}


def _shadow_pipeline_route(state: PlannerLedShadowState) -> str:
    path_type = _path_type(state)
    if path_type in _RAG_PIPELINE_PATH_TYPES:
        return "rag_pipeline"
    return "investigation_pipeline"


def _shadow_needs_pre_mcp_rag(state: PlannerLedShadowState) -> bool:
    if "rag" not in _branches(state):
        return False
    plan = state.get("evidence_plan")
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp"


def shadow_node_rag_pipeline_prepare(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_prepare_rag_only(state)
    return {**state, "shadow_graph_trace": _trace_append(state, "rag_pipeline_prepare")}


def shadow_node_rag_pipeline_retrieve(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_rag_early(state)
    return {**state, "shadow_graph_trace": _trace_append(state, "rag_pipeline_retrieve")}


def shadow_node_investigation_spl(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_workflow_spl(state)
    return {**state, "shadow_graph_trace": _trace_append(state, "investigation_spl")}


def _shadow_after_investigation_spl(state: PlannerLedShadowState) -> str:
    if _shadow_needs_pre_mcp_rag(state):
        return "pre_mcp_rag"
    return "execution"


def shadow_node_investigation_execution(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_execution(state)
    return {**state, "shadow_graph_trace": _trace_append(state, "investigation_execution")}


def shadow_node_finalize(state: PlannerLedShadowState) -> PlannerLedShadowState:
    state = graph_node_context_finalize(state)
    trace = _trace_append(state, "finalize")
    trace["topology"] = "planner_led_shadow_fan_out_fan_in"
    response = state.get("response")
    if response is not None:
        note = response.note or ""
        suffix = "Orchestration: planner-led shadow graph (Phase 12 parity)."
        if suffix not in note:
            response = response.model_copy(update={"note": f"{note} {suffix}".strip()})
        state = {**state, "response": response}
    return {**state, "shadow_graph_trace": trace}


@lru_cache(maxsize=1)
def _compiled_planner_led_shadow_graph() -> Any:
    graph: StateGraph = StateGraph(PlannerLedShadowState)
    graph.add_node("query_understanding", shadow_node_query_understanding)
    graph.add_node("planning", shadow_node_planning)
    graph.add_node("route_setup", shadow_node_route_setup)
    graph.add_node("rag_branch", shadow_node_rag_branch)
    graph.add_node("spl_branch", shadow_node_spl_branch)
    graph.add_node("evidence_branch", shadow_node_evidence_branch)
    graph.add_node("mitre_branch", shadow_node_mitre_branch)
    graph.add_node("severity_branch", shadow_node_severity_branch)
    graph.add_node("hil_branch", shadow_node_hil_branch)
    graph.add_node("unsafe_blocked_branch", shadow_node_unsafe_blocked_branch)
    graph.add_node("clarification_branch", shadow_node_clarification_branch)
    graph.add_node("fan_in_aggregate", shadow_node_fan_in_aggregate)
    graph.add_node("rag_pipeline_prepare", shadow_node_rag_pipeline_prepare)
    graph.add_node("rag_pipeline_retrieve", shadow_node_rag_pipeline_retrieve)
    graph.add_node("investigation_spl", shadow_node_investigation_spl)
    graph.add_node("investigation_rag", shadow_node_rag_pipeline_retrieve)
    graph.add_node("investigation_execution", shadow_node_investigation_execution)
    graph.add_node("finalize", shadow_node_finalize)

    graph.set_entry_point("query_understanding")
    graph.add_edge("query_understanding", "planning")
    graph.add_edge("planning", "route_setup")
    graph.add_edge("route_setup", "rag_branch")
    graph.add_edge("rag_branch", "spl_branch")
    graph.add_edge("spl_branch", "evidence_branch")
    graph.add_edge("evidence_branch", "mitre_branch")
    graph.add_edge("mitre_branch", "severity_branch")
    graph.add_edge("severity_branch", "hil_branch")
    graph.add_edge("hil_branch", "unsafe_blocked_branch")
    graph.add_edge("unsafe_blocked_branch", "clarification_branch")
    graph.add_edge("clarification_branch", "fan_in_aggregate")
    graph.add_conditional_edges(
        "fan_in_aggregate",
        _shadow_pipeline_route,
        {
            "rag_pipeline": "rag_pipeline_prepare",
            "investigation_pipeline": "investigation_spl",
        },
    )
    graph.add_edge("rag_pipeline_prepare", "rag_pipeline_retrieve")
    graph.add_edge("rag_pipeline_retrieve", "finalize")
    graph.add_conditional_edges(
        "investigation_spl",
        _shadow_after_investigation_spl,
        {"pre_mcp_rag": "investigation_rag", "execution": "investigation_execution"},
    )
    graph.add_edge("investigation_rag", "investigation_execution")
    graph.add_edge("investigation_execution", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def run_planner_led_shadow_graph(request: ChatRequest) -> PlannerLedShadowState:
    """Execute the Phase 12 shadow topology (tests/trace only by default)."""
    if not settings.ai_soc_langgraph_shadow_enabled:
        raise RuntimeError("planner_led_shadow_graph_disabled")
    return _compiled_planner_led_shadow_graph().invoke({"request": request})


def shadow_graph_response(state: PlannerLedShadowState) -> PlaceholderResponse:
    response = state.get("response")
    if response is None:
        raise RuntimeError("shadow graph did not produce a response")
    return response


def governance_snapshot_from_response(response: PlaceholderResponse) -> dict[str, Any]:
    planning = response.planning_decision if isinstance(response.planning_decision, dict) else {}
    mitre_visible = [
        getattr(item, "technique_id", None) or (item.get("technique_id") if isinstance(item, dict) else None)
        for item in (response.mitre_mappings or [])
    ]
    mitre_visible = [item for item in mitre_visible if item]
    spl_validation = response.spl_validation
    execution = response.execution
    human_review = response.human_review
    return {
        "use_case_id": (
            response.selected_use_case.use_case_id
            if response.selected_use_case is not None
            else planning.get("use_case_id")
        ),
        "path_type": planning.get("path_type"),
        "branches": list(planning.get("branches") or []),
        "severity_label": (
            response.severity_decision.severity_label if response.severity_decision is not None else None
        ),
        "mitre_visible": mitre_visible,
        "mitre_answer_visible": (
            response.mitre_decision.get("answer_visible")
            if isinstance(response.mitre_decision, dict)
            else None
        ),
        "spl_approved": spl_validation.approved if spl_validation is not None else None,
        "normalized_spl_present": bool(spl_validation and spl_validation.normalized_spl),
        "execution_status": execution.status if execution is not None else None,
        "execution_intent": execution.execution_intent if execution is not None else None,
        "hil_required": human_review.required if human_review is not None else None,
        "hil_review_type": human_review.review_type if human_review is not None else None,
        "candidate_spl_present": response.candidate_spl is not None,
        "answer_mode": (
            response.evidence_plan.get("answer_mode")
            if isinstance(response.evidence_plan, dict)
            else None
        ),
    }
