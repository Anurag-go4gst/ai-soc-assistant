"""A1: specialist fan-in is exact, idempotent, and content-preserving."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.chat.session_context import resolve_session_context
from app.config import settings
from app.graph.resource_planner_graph import (
    _SPECIALIST_NODE_NAMES,
    _reduce_specialist_reports,
    rp_node_bootstrap,
    rp_node_resource_planner_delegate,
    rp_node_route_resolution,
    resource_planner_graph_edges,
    rp_node_specialist_knowledge,
    rp_node_specialist_mcp,
    rp_node_specialist_skill,
    rp_node_specialist_spl,
    run_resource_planner_graph,
)
from app.schemas.requests import ChatRequest


_PROBES: tuple[tuple[str, str], ...] = (
    ("t0_reference", "What is AML.T0043?"),
    ("t2_catalogue", "Show failed login spike by user in the last 24 hours"),
    ("t3_fuzzy_alias", "failed lgon spike top users last hour"),
    (
        "t4_guided",
        "How should I investigate unusual outbound traffic from an OT host overnight?",
    ),
)

_LANE_BUILDERS: tuple[Callable[[Any], dict[str, Any]], ...] = (
    rp_node_specialist_skill,
    rp_node_specialist_knowledge,
    rp_node_specialist_mcp,
    rp_node_specialist_spl,
)


def _fake_retrieve(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "specialist-cardinality", "title": "Probe"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


def _enable_offline_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)


def _by_specialist(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(report["specialist_id"]): report for report in reports}


def _fan_out_reports(request: ChatRequest) -> list[dict[str, Any]]:
    """Capture the immutable specialist payload before fan-in and downstream mutation."""
    session_resolution = resolve_session_context(request)
    state = {
        "request": request,
        "session_role": None,
        "session_id": session_resolution.session_id,
        "session_pins": session_resolution.pins,
        "session_context_resolution": session_resolution,
        "effective_query": session_resolution.effective_query,
        "handoff_resume": session_resolution.handoff_resume,
    }
    state = rp_node_bootstrap(state)
    state = rp_node_route_resolution(state)
    state = rp_node_resource_planner_delegate(state)
    return [builder(state)["specialist_reports"][0] for builder in _LANE_BUILDERS]


@pytest.mark.parametrize(("probe_id", "query"), _PROBES, ids=[row[0] for row in _PROBES])
def test_specialist_reports_are_exact_and_content_preserving_across_paths(
    monkeypatch: pytest.MonkeyPatch,
    probe_id: str,
    query: str,
) -> None:
    _enable_offline_control_plane(monkeypatch)

    request = ChatRequest(message=query)
    expected_reports = _fan_out_reports(request)
    state = run_resource_planner_graph(request)
    reports = [
        report
        for report in state.get("specialist_reports") or []
        if isinstance(report, dict)
    ]

    assert len(reports) == 4, f"{probe_id}: fan-in must contain exactly four reports"
    assert {report["specialist_id"] for report in reports} == {
        "skill",
        "knowledge",
        "mcp",
        "spl",
    }

    assert _by_specialist(reports) == _by_specialist(expected_reports), (
        f"{probe_id}: reducer changed or dropped per-lane report content"
    )

    iteration = state.get("planner_iteration")
    assert isinstance(iteration, dict)
    iteration_reports = iteration.get("reports") or []
    assert len(iteration_reports) == 4
    assert _by_specialist(iteration_reports) == _by_specialist(expected_reports), (
        f"{probe_id}: planner iteration dropped specialist subtype content"
    )

    bundle = state.get("work_bundle")
    assert isinstance(bundle, dict)
    bundle_reports = bundle.get("specialist_reports") or []
    assert len(bundle_reports) == 4
    assert _by_specialist(bundle_reports) == _by_specialist(expected_reports), (
        f"{probe_id}: work bundle dropped specialist subtype content"
    )


def test_resource_planner_edges_document_all_four_send_branches() -> None:
    edges = resource_planner_graph_edges()

    assert {
        ("resource_planner_delegate", specialist)
        for specialist in _SPECIALIST_NODE_NAMES
    }.issubset(edges)
    assert {
        (specialist, "resource_planner_merge")
        for specialist in _SPECIALIST_NODE_NAMES
    }.issubset(edges)


def test_specialist_report_reducer_is_idempotent_for_identical_replays() -> None:
    report = {
        "delegation_id": "del:skill",
        "specialist_id": "skill",
        "decision_reason": "route_lane",
    }

    assert _reduce_specialist_reports([report], [dict(report)]) == [report]


def test_specialist_report_reducer_fails_closed_on_conflict() -> None:
    original = {
        "delegation_id": "del:skill",
        "specialist_id": "skill",
        "decision_reason": "route_lane",
    }
    conflicting = {**original, "decision_reason": "different_route_lane"}

    with pytest.raises(ValueError, match="conflicting specialist reports"):
        _reduce_specialist_reports([original], [conflicting])
