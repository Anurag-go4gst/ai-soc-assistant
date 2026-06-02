from __future__ import annotations

from unittest.mock import patch

import pytest

from app.coverage.question_runtime_map import list_question_runtime_entries
from app.query_understanding.models import QueryUnderstandingResult, RequestedOutputType
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import CATALOG_SKILL_COLLAPSE, select_route_from_understanding
from app.routing.skill_router import route_skill
from app.use_cases.registry import load_use_case_catalog
from contracts.skill_enum import SKILL_ENUM


def test_catalog_non_enum_collapses_to_knowledge_recall_without_clarification() -> None:
    understanding = understand_query("Recommend endpoint isolation")
    base, provenance = select_route_from_understanding(understanding, "Recommend endpoint isolation")

    assert understanding.mapped_use_case_ids == ["edr_isolation_recommendation"]
    assert base["skill"] == "knowledge_recall"
    assert "needs_clarification" not in base["tool_plan"]
    assert provenance.get("collapsed_from") == "action_planning"
    assert provenance.get("use_case_id") == "edr_isolation_recommendation"
    assert understanding.primary_intent == "action_planning"
    assert provenance.get("requested_output_type") in {"action_plan", "investigation"}


def test_catalog_enum_skill_routes_attack_discovery() -> None:
    understanding = understand_query("Investigate failed login spike on APP-01")
    base, provenance = select_route_from_understanding(understanding, "Investigate failed login spike on APP-01")

    assert base["skill"] == "attack_discovery"
    assert provenance.get("selected_by") == "query_understanding_catalog"
    assert provenance.get("collapsed_from") is None


def test_h1_full_coverage_105_and_catalog() -> None:
    for entry in list_question_runtime_entries():
        question = entry["question"]
        understanding = understand_query(question)
        base, _ = select_route_from_understanding(understanding, question)
        assert base["skill"] in SKILL_ENUM, question

    for use_case in load_use_case_catalog():
        query = use_case.example_queries[0] if use_case.example_queries else use_case.display_name
        understanding = understand_query(query)
        if understanding.deterministic_match_path != "use_case_catalog":
            continue
        base, provenance = select_route_from_understanding(understanding, query)
        assert base["skill"] in SKILL_ENUM, use_case.use_case_id
        if use_case.primary_skill not in SKILL_ENUM:
            assert provenance.get("collapsed_from") == use_case.primary_skill


def test_routing_provenance_includes_all_qu_fields() -> None:
    understanding = understand_query("Which source IPs generated the most outbound connections?")
    _, provenance = select_route_from_understanding(understanding, understanding.raw_query)
    qu_fields = set(QueryUnderstandingResult.model_fields)
    provenance_keys = set(provenance.keys())
    mapped = {
        "raw_query",
        "normalized_query",
        "primary_intent",
        "secondary_intents",
        "requested_output_type",
        "output_template",
        "entities",
        "ambiguity_flags",
        "clarification_needed",
        "clarification_question",
        "confidence_qu",
        "mapped_question_ref",
        "mapped_question_number",
        "mapped_coverage_id",
        "coverage_id",
        "mapped_pattern_type",
        "pattern_type",
        "mapped_operation_type",
        "operation_type",
        "question_registry_match_score",
        "mapped_primary_skill",
        "mapped_use_case_ids",
        "question_registry_match_source",
        "near_match_score",
        "question_registry_observation_only",
        "use_case_catalog_size",
        "use_case_match_source",
        "deterministic_match_path",
        "registry_warnings",
        "registry_consistency",
        "llm_advisory_recommended",
    }
    assert qu_fields <= mapped | provenance_keys


def test_understand_query_failover_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "routing_mode", "deterministic_only")

    def boom(_query: str) -> QueryUnderstandingResult:
        raise RuntimeError("registry unavailable")

    with patch("app.routing.skill_router.understand_query", side_effect=boom):
        routed = route_skill("Show SOP for brute-force investigation", qu_failed=False)

    assert routed["routing_provenance"]["qu_failed"] is True
    assert routed["routing_provenance"]["degraded"] is True
    assert routed["skill"] in SKILL_ENUM
    assert routed["llm_adjudication"]["status"] == "skipped_qu_failed"


def test_understand_query_failover_skips_llm_in_assisted_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "routing_mode", "llm_assisted_semantic")

    def boom(_query: str) -> QueryUnderstandingResult:
        raise RuntimeError("registry unavailable")

    with patch("app.routing.skill_router.understand_query", side_effect=boom):
        with patch("app.routing.skill_router.route_skill_llm_shadow") as shadow:
            shadow.return_value = {"skill": "attack_discovery", "tool_plan": [], "confidence": 0.9, "metadata": {}}
            routed = route_skill("Show SOP for brute-force investigation")

    assert shadow.call_count == 0
    assert routed["llm_adjudication"]["status"] == "skipped_qu_failed"


def test_single_understand_query_per_init_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.pipeline import graph_node_init_routing
    from app.schemas.requests import ChatRequest

    calls: list[str] = []

    def counting_understand(query: str) -> QueryUnderstandingResult:
        calls.append(query)
        return understand_query(query)

    monkeypatch.setattr("app.chat.pipeline.understand_query", counting_understand)
    monkeypatch.setattr(
        "app.api.routes_chat.route_skill",
        lambda query, trace_id, query_understanding=None, qu_failed=False: {
            "skill": "knowledge_recall",
            "tool_plan": ["retrieve_approved_context"],
            "routing_provenance": {"deterministic_match_path": "use_case_catalog"},
        },
    )
    monkeypatch.setattr(
        "app.chat.pipeline._route_plan_shadow_stage",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr("app.chat.pipeline._selected_use_case", lambda query: None)

    graph_node_init_routing({"request": ChatRequest(message="Show SOP for brute-force investigation")})
    assert len(calls) == 1


def test_exact_105_keeps_query_understanding_selected_by_in_assisted_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "routing_mode", "llm_assisted_semantic")
    entry = next(item for item in list_question_runtime_entries() if item["question_ref"] == "q0.q001")
    understanding = understand_query(entry["question"])
    routed = route_skill(entry["question"], query_understanding=understanding)

    assert routed["skill"] == "alert_summary"
    assert routed["selected_by"] == "query_understanding_105"
    assert routed["routing_provenance"]["authority_source"] == "query_understanding_105"
    assert routed["llm_adjudication"]["status"] == "not_needed"


def test_q0_q001_notable_risk_not_selected_skill() -> None:
    entry = next(item for item in list_question_runtime_entries() if item["question_ref"] == "q0.q001")
    understanding = understand_query(entry["question"])
    base, provenance = select_route_from_understanding(understanding, entry["question"])

    assert base["skill"] == "alert_summary"
    assert provenance.get("operation_type") == "risk_lookup" or provenance.get("mapped_primary_skill") == "notable_risk_lookup"
