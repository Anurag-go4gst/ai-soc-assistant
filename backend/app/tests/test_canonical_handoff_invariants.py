"""Invariant tests for canonical planning architecture (rev 4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.contracts.gap_resolution import FieldProvenance, GapResolutionResult
from app.chat.contracts.knowledge_recall import KnowledgeRecallResult
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.known_detail_completion import KnownCompletenessResult, evaluate_known_detail_completion
from app.chat.lane_router import initial_tier_for_match_path, is_known_catalogue_match, lane_for_match_path
from app.chat.post_guided_completeness import evaluate_post_guided_completeness
from app.chat.reference_qualification import qualify_reference_query
from app.chat.select_detail_tools import select_detail_tools
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.config import settings
from app.query_understanding.parser import understand_query


@pytest.fixture(autouse=True)
def _enable_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    reset_planning_telemetry_for_tests()
    clear_all_handoffs_for_tests()


def test_t1_t3_map_to_known_lane() -> None:
    for path in ("exact_105_question", "use_case_catalog", "near_105_question", "semantic_105_question"):
        assert is_known_catalogue_match(path)
        _, _, lane = lane_for_match_path(path)
        assert lane == "known"


def test_no_match_enters_t4() -> None:
    for path in ("out_of_registry", "query_understanding_weak", ""):
        assert initial_tier_for_match_path(path) == "T4"


def test_identifier_alone_not_t0() -> None:
    for query in (
        "CVE-2026-12345",
        "MITRE T1059",
        "AML.T0051",
        "Are we affected by CVE-2026-12345?",
    ):
        q = qualify_reference_query(query)
        if "affected" in query.lower() or "are we" in query.lower():
            assert not q.resolves_to_t0
        elif query.startswith("CVE") or query.startswith("MITRE") or query.startswith("AML"):
            assert not q.resolves_to_t0


def test_guided_planner_never_selects_zero_tools_without_explicit_status() -> None:
    tools = select_detail_tools(
        intent_family="live_investigation",
        answer_goal="live_investigation",
        missing_categories={},
        reference_ids=["CVE-2026-1"],
    )
    assert tools
    gap = run_guided_detail_resolution(
        query="test",
        handoff_id="h1",
        intent_family="live_investigation",
        answer_goal="live_investigation",
        completeness=KnownCompletenessResult(
            required_fields=[],
            present_fields=[],
            missing_fields=[],
            missing_field_categories={},
            completeness_status="complete",
        ),
        reference_ids=["CVE-2026-1"],
    )
    assert gap.selected_tools or gap.resolution_status in {
        "resolved_without_tools",
        "clarification_required",
        "policy_blocked",
    }


def test_tool_failure_not_success() -> None:
    completeness = KnownCompletenessResult(
        required_fields=["cve_context"],
        present_fields=[],
        missing_fields=["cve_context"],
        missing_field_categories={"cve_context": "tool_discoverable"},
        completeness_status="incomplete",
        divert_to_guided=True,
    )
    error_result = KnowledgeRecallResult(status="error", errors=["source_unavailable"])
    with patch("app.chat.guided_detail_resolution.run_knowledge_recall", return_value=error_result):
        gap = run_guided_detail_resolution(
            query="What is CVE-2026-12345?",
            handoff_id="h2",
            intent_family="reference_knowledge",
            answer_goal="reference_explanation",
            completeness=completeness,
            reference_ids=["CVE-2026-12345"],
        )
    assert gap.tool_statuses.get("knowledge_recall") == "error"
    assert gap.resolution_status != "complete"


def test_unresolved_planner_required_blocks_execution() -> None:
    gap = GapResolutionResult(
        resolution_id="gr:x",
        handoff_id="h3",
        unresolved_details=["user"],
        resolution_status="resolution_failed",
    )
    post = evaluate_post_guided_completeness(
        gap,
        planner_required_fields=["user"],
        user_only_fields=[],
    )
    assert post.clarification_required
    assert post.status == "clarification_required"


def test_equivalent_semantic_canonical_input() -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    intent = {
        "intent_family": "reference_knowledge",
        "primary_intent": "knowledge_recall",
        "answer_goal_primary": "reference_explanation",
        "answer_goal": ["reference_lookup"],
        "llm_intent_status": "classifier",
    }
    routed = {"skill": "knowledge_recall", "reasons": ["test"]}
    a = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed=routed,
        intent_classification=intent,
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        route_reason="t4_resolved_t0",
        handoff_id="cpi:fixed",
    )
    b = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed=routed,
        intent_classification=intent,
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        route_reason="t4_resolved_t0",
        handoff_id="cpi:fixed",
    )
    assert a.model_dump() == b.model_dump()


def test_governance_booleans_not_opened_by_tools() -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification={
            "intent_family": "reference_knowledge",
            "primary_intent": "knowledge_recall",
            "answer_goal_primary": "reference_explanation",
            "answer_goal": ["reference_lookup"],
        },
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
    )
    assert canonical.governance.spl_execution_allowed is False
    assert canonical.governance.action_allowed is False
    assert canonical.governance.remediation_allowed is False


def test_known_diversion_preserves_original_skill() -> None:
    completeness = evaluate_known_detail_completion(
        use_case_id="auth_failed_login_spike",
        query_to_intent={},
        query_understanding=understand_query("Investigate failed login spike for host:WRONG-99"),
    )
    gap = run_guided_detail_resolution(
        query="Investigate failed login spike for host:WRONG-99",
        handoff_id="h4",
        intent_family="live_investigation",
        answer_goal="live_investigation",
        completeness=completeness,
        original_skill="attack_discovery",
        original_answer_goal="live_investigation",
    )
    assert gap.original_skill == "attack_discovery"
    assert gap.original_answer_goal == "live_investigation"
