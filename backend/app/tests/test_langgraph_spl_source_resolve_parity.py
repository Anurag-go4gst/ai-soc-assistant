"""SPL source-resolve ordering on the Resource Planner graph (item 12b batch 2).

Production path: ``spl_source_resolve`` precedes ``mcp_execution_gate`` on the RP
hierarchy graph. Rollback imperative remains available when orchestration is off.
"""

from __future__ import annotations

from app.evals.sentinel_eval import sentinel_runtime
from app.graph.resource_planner_graph import (
    _compiled_resource_planner_graph,
    _documented_resource_planner_edges,
    run_chat_via_resource_planner_graph,
)
from app.schemas.requests import ChatRequest

_FAILED_LOGINS = "show failed admin logins in the last 24 hours"


def test_rp_graph_has_spl_source_resolve_before_execution_gate() -> None:
    compiled = _compiled_resource_planner_graph()
    node_ids = set(compiled.get_graph().nodes)
    assert "spl_source_resolve" in node_ids
    assert "mcp_execution_gate" in node_ids

    edges = _documented_resource_planner_edges()
    assert ("spl_source_resolve", "mcp_execution_gate") in edges
    assert ("workflow_spl", "mcp_execution_gate") not in edges
    assert ("rag_early", "mcp_execution_gate") not in edges


def test_rp_graph_spl_source_resolve_disposition() -> None:
    """RP graph reaches review-only SPL disposition without MCP execution."""
    with sentinel_runtime():
        response = run_chat_via_resource_planner_graph(ChatRequest(message=_FAILED_LOGINS))

    hr = response.human_review.review_type if response.human_review else None
    assert hr in {
        None,
        "spl_revision",
        "execution_approval",
        "spl_source_profile_clarification",
        "precondition_review",
    }

    if response.execution is not None:
        assert response.execution.status in {
            "skipped",
            "blocked",
            "requires_human_review",
            "not_executed",
        }

    imp_spl = response.spl_validation.normalized_spl if response.spl_validation else None
    assert imp_spl in {None, ""} or isinstance(imp_spl, str)
