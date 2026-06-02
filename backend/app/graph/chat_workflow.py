"""Stage P1: LangGraph wrapper around the live /chat pipeline (parity only)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from app.chat.pipeline import (
    ChatPipelineState,
    build_live_chat_response,
    graph_node_context_finalize,
    graph_node_execution,
    graph_node_init_routing,
    graph_node_query_to_intent,
    graph_node_shadow_enrichment,
    graph_node_workflow_spl,
)
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


@lru_cache(maxsize=1)
def _compiled_chat_graph() -> Any:
    graph: StateGraph = StateGraph(ChatPipelineState)
    graph.add_node("init_routing", graph_node_init_routing)
    graph.add_node("query_to_intent", graph_node_query_to_intent)
    graph.add_node("shadow_enrichment", graph_node_shadow_enrichment)
    graph.add_node("workflow_spl", graph_node_workflow_spl)
    graph.add_node("execution", graph_node_execution)
    graph.add_node("context_finalize", graph_node_context_finalize)
    graph.set_entry_point("init_routing")
    graph.add_edge("init_routing", "query_to_intent")
    graph.add_edge("query_to_intent", "shadow_enrichment")
    graph.add_edge("shadow_enrichment", "workflow_spl")
    graph.add_edge("workflow_spl", "execution")
    graph.add_edge("execution", "context_finalize")
    graph.add_edge("context_finalize", END)
    return graph.compile()


def run_chat_via_langgraph(request: ChatRequest) -> PlaceholderResponse:
    """Run the same staged pipeline through LangGraph; behavior must match imperative path."""
    final_state = _compiled_chat_graph().invoke({"request": request})
    response = final_state.get("response")
    if response is None:
        return build_live_chat_response(request)
    note = response.note or ""
    suffix = "Orchestration: langgraph (parity mode)."
    if suffix not in note:
        response = response.model_copy(update={"note": f"{note} {suffix}".strip()})
    return response
