"""S5 — split live route skill from planning skill (flag-gated parity)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.routes_chat import chat
from app.chat.routing_skill_nodes import (
    graph_node_load_skill_enrichment,
    graph_node_resolve_planning_skill,
    graph_node_route_live_skill,
)
from app.config import settings
from app.schemas.requests import ChatRequest


ALT_QUERY = (
    "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
    "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
    "I can review—but not execute"
)


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_live_chat_ec_parity_enabled", False)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)


def test_split_nodes_do_not_change_routed_skill() -> None:
    state = {
        "routed": {"skill": "attack_discovery"},
        "route_plan_shadow": {
            "route_authority_compare": {"planning_primary_skill": "auth_analytics"},
        },
        "selected_use_case": SimpleNamespace(use_case_id="auth_success_after_failure"),
    }
    after_live = graph_node_route_live_skill(state)
    after_planning = graph_node_resolve_planning_skill(after_live)
    after_enrichment = graph_node_load_skill_enrichment(after_planning)
    assert after_enrichment["routed"]["skill"] == "attack_discovery"
    assert after_enrichment["live_execution_skill"] == "attack_discovery"
    assert after_enrichment["planning_or_analytic_skill"] == "auth_analytics"
    trace = after_enrichment.get("split_routing_trace") or []
    assert {row["node_name"] for row in trace} == {
        "route_live_skill",
        "resolve_planning_skill",
        "load_skill_enrichment",
    }


def test_flag_off_selected_skill_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_split_routing_nodes_enabled", False)
    response = chat(ChatRequest(message=ALT_QUERY))
    assert response.selected_skill in {
        "alert_summary",
        "spl_generation",
        "attack_discovery",
        "knowledge_recall",
        "guided_investigation",
    }
    assert response.candidate_spl is not None or response.human_review is not None


def test_flag_on_final_route_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_split_routing_nodes_enabled", False)
    baseline = chat(ChatRequest(message=ALT_QUERY))
    monkeypatch.setattr(settings, "ai_soc_pipeline_split_routing_nodes_enabled", True)
    flagged = chat(ChatRequest(message=ALT_QUERY))
    assert flagged.selected_skill == baseline.selected_skill
    assert flagged.candidate_spl is not None or flagged.human_review is not None
