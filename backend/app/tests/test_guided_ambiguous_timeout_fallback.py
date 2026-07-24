"""Guided/ambiguous hunt guidance must not block on SPL+LLM producer timeouts."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.query_understanding.parser import understand_query
from app.query_understanding.soc_investigation_shape import (
    detect_broad_hunt_guidance_request,
    detect_spl_artifact_request,
)
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest

_AMBIGUOUS = "Hunt for CI/CD supply-chain compromise indicators across our environment"
_Q046 = "Which users have excessive failed logins?"
_KNOWLEDGE = "What is MITRE technique T1078 and when should analysts use it?"
_BLOCK_IP = "Block IP 10.0.0.5 immediately"


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)


def test_broad_hunt_guidance_is_not_spl_artifact_request() -> None:
    assert detect_broad_hunt_guidance_request(_AMBIGUOUS)
    assert not detect_spl_artifact_request(_AMBIGUOUS)


def test_ambiguous_supply_chain_routes_guided_investigation() -> None:
    understanding = understand_query(_AMBIGUOUS)
    route, _ = select_route_from_understanding(understanding, _AMBIGUOUS)
    assert route["skill"] == "guided_investigation"


def test_ambiguous_guided_resource_planner_returns_fast_without_spl_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    def _hang(**_kwargs):  # noqa: ANN003
        time.sleep(60)
        return None

    with patch("app.spl.llm_plan_compiler.generate_llm_spl_via_plan", side_effect=_hang):
        started = time.monotonic()
        response = run_chat_via_resource_planner_graph(ChatRequest(message=_AMBIGUOUS))
        elapsed = time.monotonic() - started

    assert elapsed < 30.0
    assert response.selected_skill == "guided_investigation"
    rc = response.run_contract or {}
    assert rc.get("execution_authorized") is False
    assert rc.get("mcp_allowed") is False
    assert response.candidate_spl is None or not str(
        getattr(response.candidate_spl, "candidate_spl", "") or ""
    ).strip()
    trace = response.control_plane_trace or {}
    composer = trace.get("llm_composer") or {}
    assert composer.get("deterministic_guided_fallback") is True


def test_q046_template_review_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    hr = payload.get("human_review") or {}
    assert hr.get("review_type") == "spl_revision"
    assert hr.get("reason") == "template_review_required"


def test_knowledge_only_stays_knowledge_recall() -> None:
    response = build_live_chat_response(ChatRequest(message=_KNOWLEDGE))
    assert response.selected_skill == "knowledge_recall"


def test_unsafe_block_ip_still_blocked() -> None:
    response = build_live_chat_response(ChatRequest(message=_BLOCK_IP))
    hr = response.human_review
    assert hr is not None
    assert hr.reason == "unsafe_action_blocked"
    rc = response.run_contract or {}
    assert rc.get("execution_authorized") is False
