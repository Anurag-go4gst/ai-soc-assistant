"""Stage P1: LangGraph wrapper around the live /chat pipeline (parity only)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from app.chat.pipeline import (
    ChatPipelineState,
    build_live_chat_response,
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
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


@lru_cache(maxsize=1)
def _compiled_chat_graph() -> Any:
    graph: StateGraph = StateGraph(ChatPipelineState)
    graph.add_node("init_routing", graph_node_init_routing)
    graph.add_node("query_to_intent", graph_node_query_to_intent)
    graph.add_node("evidence_planning", graph_node_evidence_planning)
    graph.add_node("shadow_enrichment", graph_node_shadow_enrichment)
    graph.add_node("prepare_rag_only", graph_node_prepare_rag_only)
    graph.add_node("rag_early", graph_node_rag_early)
    graph.add_node("workflow_spl", graph_node_workflow_spl)
    graph.add_node("spl_source_resolve", graph_node_spl_source_resolve)
    graph.add_node("execution", graph_node_execution)
    graph.add_node("context_finalize", graph_node_context_finalize)
    graph.set_entry_point("init_routing")
    graph.add_edge("init_routing", "query_to_intent")
    graph.add_edge("query_to_intent", "evidence_planning")
    graph.add_edge("evidence_planning", "shadow_enrichment")
    graph.add_conditional_edges(
        "shadow_enrichment",
        _after_shadow_enrichment,
        {"rag_only": "prepare_rag_only", "workflow_spl": "workflow_spl"},
    )
    graph.add_edge("prepare_rag_only", "rag_early")
    # Non-rag-only path mirrors the imperative order: SPL → [pre-MCP RAG] →
    # spl_source_resolve → execution. spl_source_resolve must run before
    # execution so a placeholder index/sourcetype is resolved (or HIL raised)
    # on BOTH runtimes — the parity gap this step closes.
    graph.add_conditional_edges(
        "workflow_spl",
        _after_workflow_spl,
        {"rag_early": "rag_early", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_conditional_edges(
        "rag_early",
        _after_rag_early,
        {"context_finalize": "context_finalize", "spl_source_resolve": "spl_source_resolve"},
    )
    graph.add_edge("spl_source_resolve", "execution")
    graph.add_edge("execution", "context_finalize")
    graph.add_edge("context_finalize", END)
    return graph.compile()


def _evidence_plan(state: ChatPipelineState) -> dict[str, Any]:
    plan = state.get("evidence_plan")
    return plan if isinstance(plan, dict) else {}


def _after_shadow_enrichment(state: ChatPipelineState) -> str:
    if _evidence_plan(state).get("answer_mode") == "rag_only":
        return "rag_only"
    return "workflow_spl"


def _after_workflow_spl(state: ChatPipelineState) -> str:
    plan = _evidence_plan(state)
    if bool(plan.get("needs_rag")) and plan.get("rag_phase") == "pre_mcp":
        return "rag_early"
    return "spl_source_resolve"


def _after_rag_early(state: ChatPipelineState) -> str:
    # rag_only path already set `execution` in prepare_rag_only → finalize.
    if "execution" in state:
        return "context_finalize"
    return "spl_source_resolve"


def run_chat_via_langgraph(
    request: ChatRequest,
    *,
    session_role: str | None = None,
) -> PlaceholderResponse:
    """Run the same staged pipeline through LangGraph; behavior must match imperative path."""
    final_state = _compiled_chat_graph().invoke(
        {"request": request, "session_role": session_role},
    )
    response = final_state.get("response")
    if response is None:
        return build_live_chat_response(request, session_role=session_role)
    note = response.note or ""
    suffix = "Orchestration: langgraph (parity mode)."
    if suffix not in note:
        response = response.model_copy(update={"note": f"{note} {suffix}".strip()})
    return response
