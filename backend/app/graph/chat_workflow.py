"""Stage P1/4B: LangGraph wrapper around the live /chat pipeline.

Default (CONTROL_PLANE_ENABLED off): the linear parity graph — behavior must
match the imperative pipeline. With the control plane on, the graph gains the
Stage 4B governed evidence-collection loop: `evidence_planning` is the HUB and a
read-only `mcp_call` discovery hop loops back to it, bounded by a single counter.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from app.chat.evidence_loop import (
    MAX_MCP_HOPS,
    ROUTE_BROADEN,
    ROUTE_CAPABILITY_GAP,
    ROUTE_DISCOVERY_HOP,
    ROUTE_EXHAUSTED,
    ROUTE_FINALIZE,
    ROUTE_HUMAN_REVIEW,
    assess_loop,
    loop_initialized,
)
from app.chat.progress_context import bind_progress_reporter, emit_stage, reset_progress_reporter
from app.chat.progress_events import ProgressReporter
from datetime import UTC, datetime

from app.chat.pipeline import (
    ChatPipelineState,
    _dispatch_schedule_and_cursor,
    build_live_chat_response,
    finalize_chat_trace_from_state,
    graph_node_composed_dispatch,
    graph_node_context_finalize,
    graph_node_evidence_planning,
    graph_node_execution,
    graph_node_init_routing,
    graph_node_mcp_call,
    graph_node_prepare_rag_only,
    graph_node_query_to_intent,
    graph_node_rag_early,
    graph_node_reference_finalize,
    graph_node_route_contract,
    graph_node_route_resolution,
    graph_node_shadow_enrichment,
    graph_node_shadow_tail,
    graph_node_spl_source_resolve,
    graph_node_workflow_spl,
    dispatch_v2_route_after_shadow_tail,
    dispatch_v2_route_after_workflow_spl,
    graph_node_spl_postprocessor,
    dispatch_v2_route_after_spl_postprocessor,
)
from app.chat.contracts.pipeline_dispatch import PipelineStage, next_stage_after
from app.chat.decision_record import wrap_graph_node
from app.config import settings
from app.planner.executor import has_composed_plan
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse

# Two nodes per discovery iteration (evidence_planning + mcp_call), plus the
# linear chain and the execution loopback. Derived from the hop bound so the
# cyclic graph can never out-run termination.
_CP_RECURSION_LIMIT = MAX_MCP_HOPS * 2 + 30


def _add_linear_chain(graph: StateGraph) -> None:
    graph.add_conditional_edges(
        "shadow_tail",
        _after_shadow_tail,
        {"rag_only": "prepare_rag_only", "rag_early": "rag_early", "workflow_spl": "workflow_spl", "composed_dispatch": "composed_dispatch", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_edge("prepare_rag_only", "rag_early")
    # Non-rag-only path mirrors the imperative order: SPL → [pre-MCP RAG] →
    # spl_source_resolve → execution. spl_source_resolve must run before
    # execution so a placeholder index/sourcetype is resolved (or HIL raised)
    # on BOTH runtimes — the parity gap this step closes.
    graph.add_conditional_edges(
        "workflow_spl",
        _after_workflow_spl,
        {
            "rag_early": "rag_early",
            "spl_postprocessor": "spl_postprocessor",
            "spl_source_resolve": "spl_source_resolve",
        },
    )
    graph.add_conditional_edges(
        "spl_postprocessor",
        _after_spl_postprocessor,
        {"rag_early": "rag_early", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_conditional_edges(
        "rag_early",
        _after_rag_early,
        {
            "context_finalize": "context_finalize",
            "reference_finalize": "reference_finalize",
            "spl_source_resolve": "spl_source_resolve",
        },
    )
    graph.add_edge("spl_source_resolve", "execution")
    graph.add_edge("composed_dispatch", "context_finalize")
    graph.add_edge("reference_finalize", "context_finalize")
    graph.add_edge("context_finalize", END)


def _core_nodes(graph: StateGraph) -> None:
    graph.add_node("init_routing", wrap_graph_node("init_routing", graph_node_init_routing))
    graph.add_node("query_to_intent", wrap_graph_node("query_to_intent", graph_node_query_to_intent))
    graph.add_node("evidence_planning", wrap_graph_node("evidence_planning", graph_node_evidence_planning))
    graph.add_node("route_resolution", wrap_graph_node("route_resolution", graph_node_route_resolution))
    graph.add_node("route_contract", wrap_graph_node("route_contract", graph_node_route_contract))
    graph.add_node("shadow_tail", wrap_graph_node("shadow_tail", graph_node_shadow_tail))
    graph.add_node("shadow_enrichment", wrap_graph_node("shadow_enrichment", graph_node_shadow_enrichment))
    graph.add_node("prepare_rag_only", wrap_graph_node("prepare_rag_only", graph_node_prepare_rag_only))
    graph.add_node("rag_early", wrap_graph_node("rag_early", graph_node_rag_early))
    graph.add_node("reference_finalize", wrap_graph_node("reference_finalize", graph_node_reference_finalize))
    graph.add_node("workflow_spl", wrap_graph_node("workflow_spl", graph_node_workflow_spl))
    graph.add_node("spl_postprocessor", wrap_graph_node("spl_postprocessor", graph_node_spl_postprocessor))
    graph.add_node("spl_source_resolve", wrap_graph_node("spl_source_resolve", graph_node_spl_source_resolve))
    graph.add_node("execution", wrap_graph_node("execution", graph_node_execution))
    graph.add_node("composed_dispatch", wrap_graph_node("composed_dispatch", graph_node_composed_dispatch))
    graph.add_node("context_finalize", wrap_graph_node("context_finalize", graph_node_context_finalize))
    graph.set_entry_point("init_routing")
    graph.add_edge("init_routing", "query_to_intent")
    graph.add_edge("query_to_intent", "route_resolution")
    graph.add_edge("route_resolution", "route_contract")
    graph.add_edge("route_contract", "evidence_planning")


@lru_cache(maxsize=1)
def _compiled_chat_graph() -> Any:
    """Linear parity graph (control plane off)."""
    graph: StateGraph = StateGraph(ChatPipelineState)
    _core_nodes(graph)
    graph.add_edge("evidence_planning", "shadow_tail")
    graph.add_edge("execution", "context_finalize")
    _add_linear_chain(graph)
    return graph.compile()


@lru_cache(maxsize=1)
def _compiled_chat_graph_cp() -> Any:
    """Cyclic graph with the Stage 4B governed evidence-collection loop.

    `evidence_planning` is the HUB: it routes to the read-only `mcp_call`
    discovery hop (which loops back) until the planned chronology is exhausted,
    then enters the linear SPL/execution chain once. The gated `execution` node
    returns to the HUB, which forwards to `context_finalize`.
    """
    graph: StateGraph = StateGraph(ChatPipelineState)
    _core_nodes(graph)
    graph.add_node("mcp_call", wrap_graph_node("mcp_call", graph_node_mcp_call))
    graph.add_conditional_edges(
        "evidence_planning",
        _hub_route,
        {
            "mcp_call": "mcp_call",
            "shadow_tail": "shadow_tail",
            "context_finalize": "context_finalize",
        },
    )
    graph.add_edge("mcp_call", "evidence_planning")
    # Execution result returns to the HUB (plan 4B topology); the HUB forwards it
    # to context_finalize. Bounded by mcp_hops_done so it cannot spin.
    graph.add_edge("execution", "evidence_planning")
    _add_linear_chain(graph)
    return graph.compile()


def _evidence_plan(state: ChatPipelineState) -> dict[str, Any]:
    plan = state.get("evidence_plan")
    return plan if isinstance(plan, dict) else {}


# Execution-phase assessor verdicts all resolve at context_finalize, which is
# where broaden hand-off (pending_execution set by graph_node_execution), the HIL
# envelope, capability-gap honest degrade, and the negative/normal result are all
# rendered from state — there is no separate broaden/HIL node to route to. The
# map exists so the edge is driven by the assessor verdict (not a blind check)
# and so adding such nodes later is a one-line change.
_EXECUTION_ROUTE_TARGETS = {
    ROUTE_FINALIZE: "context_finalize",
    ROUTE_BROADEN: "context_finalize",
    ROUTE_HUMAN_REVIEW: "context_finalize",
    ROUTE_CAPABILITY_GAP: "context_finalize",
    ROUTE_EXHAUSTED: "context_finalize",
}


def _hub_route(state: ChatPipelineState) -> str:
    # The HUB already stored the assessor verdict in mcp_loop; consume it so the
    # edge is verdict-driven (decision B etc.), not a blind "execution in state".
    route = (state.get("mcp_loop") or {}).get("route")
    if "execution" in state:
        # Execution re-entry: the run_query result decides the forward route.
        return _EXECUTION_ROUTE_TARGETS.get(route, "context_finalize")
    # Discovery phase: drain the planned read-only hops, then enter the linear
    # chain exactly once. The verdict is non-discovery once the chronology is
    # exhausted or the hop bound is hit.
    if loop_initialized(state) and route == ROUTE_DISCOVERY_HOP:
        return "mcp_call"
    return "shadow_tail"


def _after_shadow_tail(state: ChatPipelineState) -> str:
    v2_route = dispatch_v2_route_after_shadow_tail(state)
    if v2_route is not None:
        return v2_route
    if _evidence_plan(state).get("answer_mode") == "rag_only":
        return "rag_only"
    if has_composed_plan(state):
        return "composed_dispatch"
    return "workflow_spl"


def _after_workflow_spl(state: ChatPipelineState) -> str:
    v2_route = dispatch_v2_route_after_workflow_spl(state)
    if v2_route is not None:
        return v2_route
    plan = _evidence_plan(state)
    if bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp":
        return "rag_early"
    return "spl_source_resolve"


def _after_spl_postprocessor(state: ChatPipelineState) -> str:
    v2_route = dispatch_v2_route_after_spl_postprocessor(state)
    if v2_route is not None:
        return v2_route
    return "spl_source_resolve"


def _after_rag_early(state: ChatPipelineState) -> str:
    dispatch = state.get("pipeline_dispatch")
    if isinstance(dispatch, dict):
        schedule, cursor = _dispatch_schedule_and_cursor(dispatch)
        if next_stage_after(schedule, cursor) is PipelineStage.reference_finalize:
            return "reference_finalize"
    # rag_only path already set `execution` in prepare_rag_only → finalize.
    if "execution" in state:
        return "context_finalize"
    return "spl_source_resolve"


def run_chat_via_langgraph(
    request: ChatRequest,
    *,
    progress: ProgressReporter | None = None,
    session_role: str | None = None,
    entrypoint: str = "chat",
) -> PlaceholderResponse:
    """Run the same staged pipeline through LangGraph; behavior must match imperative path."""
    token = bind_progress_reporter(progress) if progress is not None else None
    started_at = datetime.now(UTC)
    try:
        emit_stage("queued")
        if settings.control_plane_enabled:
            compiled = _compiled_chat_graph_cp()
            config = {"recursion_limit": _CP_RECURSION_LIMIT}
        else:
            compiled = _compiled_chat_graph()
            config = {}
        final_state = compiled.invoke(
            {"request": request, "session_role": session_role},
            config,
        )
        response = final_state.get("response")
        if response is None:
            return build_live_chat_response(
                request,
                progress=progress,
                session_role=session_role,
            )  # build_live_chat_response finalizes telemetry
        note = response.note or ""
        suffix = "Orchestration: langgraph (parity mode)."
        if suffix not in note:
            response = response.model_copy(update={"note": f"{note} {suffix}".strip()})
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
