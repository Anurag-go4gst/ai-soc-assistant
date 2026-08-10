"""B0/B1: one canonical catalogue-tier and match-path authority."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.graph.resource_planner_graph import (
    rp_node_specialist_skill,
    run_resource_planner_graph,
)
from app.schemas.requests import ChatRequest


_APP_ROOT = Path(__file__).resolve().parents[1]

_PROBES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "cve_definition_t4_to_t0",
        "Explain CVE-2024-3400",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T4",
            "effective_match_path": "out_of_registry",
            "initial_tier": "T4",
            "resolved_tier": "T0",
            "accepted": False,
            "decision_reason": "no_catalogue_bind",
        },
    ),
    (
        "t1059_hunt_stays_t4",
        "Hunt for T1059 execution in our estate",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T4",
            "effective_match_path": "out_of_registry",
            "initial_tier": "T4",
            "resolved_tier": "T4",
            "accepted": False,
            "decision_reason": "no_catalogue_bind",
        },
    ),
    (
        "exact_row_t1",
        "What incident or alert network events are high or critical right now?",
        {
            "observed_match_path": "exact_105_question",
            "binding_candidate_tier": "T1",
            "effective_match_path": "exact_105_question",
            "initial_tier": "T1",
            "resolved_tier": "T1",
            "accepted": True,
            "decision_reason": "observed_catalogue_authority",
        },
    ),
    (
        "catalogue_row_t2",
        "Show failed login spike by user in the last 24 hours",
        {
            "observed_match_path": "use_case_catalog",
            "binding_candidate_tier": "T2",
            "effective_match_path": "use_case_catalog",
            "initial_tier": "T2",
            "resolved_tier": "T2",
            "accepted": True,
            "decision_reason": "observed_catalogue_authority",
        },
    ),
    (
        "accepted_alias_t3",
        "failed lgon spike top users last hour",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T3",
            "effective_match_path": "fuzzy_alias_catalog",
            "initial_tier": "T3",
            "resolved_tier": "T3",
            "accepted": True,
            "decision_reason": "bounded_alias_accepted",
        },
    ),
    (
        "non_soc_alias_not_promoted",
        "Show vacation policy for failed lgon spike",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T3",
            "effective_match_path": "out_of_registry",
            "initial_tier": "T4",
            "resolved_tier": "T4",
            "accepted": False,
            "decision_reason": "non_soc_candidate_rejected",
        },
    ),
    (
        "unsafe_alias_not_promoted",
        "Block the user after a failed lgon spike",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T3",
            "effective_match_path": "out_of_registry",
            "initial_tier": "T4",
            "resolved_tier": "T4",
            "accepted": False,
            "decision_reason": "unsafe_candidate_rejected",
        },
    ),
    (
        "ambiguous_alias_not_promoted",
        "failed lgon spike across firewall and vpn logs",
        {
            "observed_match_path": "out_of_registry",
            "binding_candidate_tier": "T3",
            "effective_match_path": "out_of_registry",
            "initial_tier": "T4",
            "resolved_tier": "T4",
            "accepted": False,
            "decision_reason": "ambiguous_candidate_rejected",
        },
    ),
)


def _fake_retrieve(**kwargs: Any) -> dict[str, Any]:
    return {
        "retrieval_status": "collected",
        "chunks": [{"doc_id": "tier-authority", "title": "Tier authority"}],
        "required_sources": kwargs.get("required_sources") or [],
    }


def _enable_offline_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.retrieve_soc_kb", _fake_retrieve)


def _skill_report(state: dict[str, Any]) -> dict[str, Any]:
    reports = state.get("specialist_reports") or []
    return next(
        report
        for report in reports
        if isinstance(report, dict) and report.get("specialist_id") == "skill"
    )


@pytest.mark.parametrize(
    ("probe_id", "query", "expected"),
    _PROBES,
    ids=[row[0] for row in _PROBES],
)
def test_canonical_tier_and_effective_match_path_contract(
    monkeypatch: pytest.MonkeyPatch,
    probe_id: str,
    query: str,
    expected: dict[str, Any],
) -> None:
    _enable_offline_control_plane(monkeypatch)

    state = run_resource_planner_graph(ChatRequest(message=query))
    canonical = state.get("canonical_planning_input")
    assert isinstance(canonical, dict), probe_id
    routing = canonical.get("routing")
    assert isinstance(routing, dict), probe_id
    candidate = state.get("catalogue_binding_candidate")
    assert isinstance(candidate, dict), probe_id

    assert candidate["binding_candidate_tier"] == expected["binding_candidate_tier"]
    assert candidate["observed_match_path"] == expected["observed_match_path"]
    assert candidate["effective_match_path"] == expected["effective_match_path"]
    assert candidate["accepted"] is expected["accepted"]
    assert candidate["decision_reason"] == expected["decision_reason"]
    assert state.get("effective_catalogue_match_path") == expected["effective_match_path"]

    assert routing["observed_match_path"] == expected["observed_match_path"]
    assert routing["effective_match_path"] == expected["effective_match_path"]
    assert routing["match_path"] == expected["effective_match_path"]
    assert routing["initial_tier"] == expected["initial_tier"]
    assert routing["resolved_tier"] == expected["resolved_tier"]
    assert routing["catalogue_tier"] == expected["resolved_tier"]
    assert _skill_report(state)["catalogue_tier"] == routing["catalogue_tier"]


def test_skill_specialist_fails_closed_without_canonical_routing() -> None:
    report = rp_node_specialist_skill(
        {
            "request": ChatRequest(message="Hunt for T1059 execution in our estate"),
            "routed": {"skill": "guided_investigation"},
        }
    )["specialist_reports"][0]

    assert report["catalogue_tier"] is None
    assert report["warnings"] == ["canonical_routing_unavailable"]


def test_legacy_tier_classifier_has_no_production_importers() -> None:
    importers: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(_APP_ROOT).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "app.catalogue.match_tiers":
                continue
            if any(alias.name == "match_catalogue_tier" for alias in node.names):
                importers.append(str(path.relative_to(_APP_ROOT)))

    assert importers == []
