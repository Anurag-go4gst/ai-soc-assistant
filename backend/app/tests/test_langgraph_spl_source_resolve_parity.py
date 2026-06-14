"""Step 1 — LangGraph runs spl_source_resolve before execution (parity).

Closes the confirmed runtime gap: the imperative path resolves SPL source
profiles before the execution gate; the LangGraph path previously skipped it,
so a placeholder index/sourcetype could reach execution on one runtime only.
"""

from __future__ import annotations

from app.graph.chat_workflow import _compiled_chat_graph, run_chat_via_langgraph
from app.chat.pipeline import build_live_chat_response
from app.schemas.requests import ChatRequest


def test_graph_has_spl_source_resolve_before_execution() -> None:
    compiled = _compiled_chat_graph()
    graph = compiled.get_graph()
    node_ids = set(graph.nodes)
    assert "spl_source_resolve" in node_ids

    # An edge must flow spl_source_resolve -> execution (resolve precedes the gate).
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("spl_source_resolve", "execution") in edges
    # And execution is never entered directly from workflow_spl / rag_early.
    assert ("workflow_spl", "execution") not in edges
    assert ("rag_early", "execution") not in edges


def test_imperative_and_langgraph_resolve_identically() -> None:
    request = ChatRequest(message="show failed admin logins in the last 24 hours")

    imperative = build_live_chat_response(request)
    langgraph = run_chat_via_langgraph(request)

    # Both runtimes must reach the same SPL/execution disposition now that
    # spl_source_resolve runs on both.
    imp_review = imperative.human_review.review_type if imperative.human_review else None
    lg_review = langgraph.human_review.review_type if langgraph.human_review else None
    assert imp_review == lg_review

    if imperative.execution is not None and langgraph.execution is not None:
        assert imperative.execution.block_reason == langgraph.execution.block_reason
        assert imperative.execution.status == langgraph.execution.status

    imp_spl = imperative.spl_validation.normalized_spl if imperative.spl_validation else None
    lg_spl = langgraph.spl_validation.normalized_spl if langgraph.spl_validation else None
    assert imp_spl == lg_spl
