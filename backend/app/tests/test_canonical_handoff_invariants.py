"""Invariant tests for canonical planning architecture (rev 4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.canonical_mode import build_non_planned_dispatch_state
from app.chat.contracts.gap_resolution import FieldProvenance, GapResolutionResult
from app.chat.contracts.knowledge_recall import KnowledgeRecallResult
from app.chat.guided_detail_resolution import run_guided_detail_resolution
from app.chat.known_detail_completion import KnownCompletenessResult, evaluate_known_detail_completion
from app.chat.lane_router import initial_tier_for_match_path, is_known_catalogue_match, lane_for_match_path
from app.chat.post_guided_completeness import evaluate_post_guided_completeness
from app.chat.reference_qualification import qualify_reference_query
from app.chat.select_detail_tools import select_detail_tools
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.pipeline import _response_answer_mode
from app.chat.planning_telemetry import reset_planning_telemetry_for_tests
from app.api.routes_chat import chat
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest


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


@pytest.mark.parametrize(
    "query",
    (
        "What is T1059 over the last four hours?",
        "Explain T1059 from an hour ago",
        "Describe T1059 for your team",
        "What is T1059 in a flour mill?",
        "Explain why a component is vulnerable to CVE-2026-12345",
    ),
)
def test_reference_knowledge_markers_use_phrase_boundaries(query: str) -> None:
    qualified = qualify_reference_query(query, intent_family="reference_knowledge")

    assert qualified.resolves_to_t0
    assert qualified.requested_scopes == ["knowledge_only"]
    assert qualified.environment_scope_present is False


@pytest.mark.parametrize(
    ("query", "expected_scope"),
    (
        ("Are we vulnerable to CVE-2026-12345?", "environment_status"),
        ("What is our exposure to CVE-2026-12345?", "environment_status"),
        ("Explain CVE-2026-12345 and hunt for related activity", "investigation"),
        (
            "Explain CVE-2026-12345 and contain the affected host",
            "remediation_recommendation",
        ),
    ),
)
def test_reference_status_action_and_investigation_phrases_are_bounded(
    query: str,
    expected_scope: str,
) -> None:
    qualified = qualify_reference_query(query, intent_family="reference_knowledge")

    assert qualified.resolves_to_t0 is False
    assert qualified.requested_scopes == [expected_scope]


@pytest.mark.parametrize(
    "query",
    (
        "Explain T1059 blockchain telemetry",
        "Explain T1059 containment guidance",
        "Explain T1059 for threat hunters",
        "Explain T1059 unusually clearly",
    ),
)
def test_action_and_investigation_substrings_do_not_change_reference_scope(
    query: str,
) -> None:
    qualified = qualify_reference_query(query, intent_family="reference_knowledge")

    assert qualified.resolves_to_t0
    assert qualified.requested_scopes == ["knowledge_only"]


@pytest.mark.parametrize("signal", ("explicit_log_search", "live_data_request"))
def test_allowlisted_live_signals_deny_knowledge_short_circuit(signal: str) -> None:
    qualified = qualify_reference_query(
        "Explain T1059 in our environment",
        intent_family="reference_knowledge",
        signals={signal: True, "unrelated_hint": False},
    )

    assert qualified.resolves_to_t0 is False
    assert qualified.requested_scopes == ["composite"]


def test_reference_qualification_clarification_projects_closed_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    state = build_non_planned_dispatch_state(
        {"intent_classification": {"requested_output_type": None}},
        status="clarification_required",
    )

    assert state["pipeline_dispatch"]["decision"]["request_mode"] == "clarification"
    assert state["pipeline_dispatch"]["decision"]["stage_schedule"] == []
    assert _response_answer_mode(
        {"canonical_planning_outcome": {"status": "clarification_required"}}
    ) == "clarification"


def test_reference_qualification_mitre_clarification_keeps_safe_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    base = {
        "intent_classification": {"requested_output_type": "MITRE_MAPPING"},
        "canonical_planning_outcome": {"status": "clarification_required"},
    }
    state = build_non_planned_dispatch_state(base, status="clarification_required")

    assert state["pipeline_dispatch"]["decision"]["request_mode"] == "mitre_knowledge"
    assert state["pipeline_dispatch"]["decision"]["stage_schedule"] == ["mitre_finalize"]
    assert _response_answer_mode(state) == "live_investigation"


def test_reference_qualification_p5_mitre_panel_is_candidate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)

    response = chat(
        ChatRequest(
            message="Map this alert to MITRE: 5 failed logins then success on DC-01"
        )
    )

    assert response.mitre_mappings
    assert {
        mapping.technique_id for mapping in response.mitre_mappings
    } == {"T1110", "T1110.001", "T1110.003"}
    statuses = {mapping.status for mapping in response.mitre_mappings}
    evidence_statuses = {mapping.evidence_status for mapping in response.mitre_mappings}
    assert statuses == {"candidate", "requires_validation"}
    assert evidence_statuses == {"candidate", "requires_validation"}
    assert statuses.isdisjoint({"supported", "confirmed", "evidence_supported"})
    assert all(mapping.evidence_keys == [] for mapping in response.mitre_mappings)
    assert response.mitre_decision is not None
    assert response.mitre_decision["mitre_status"] == "candidate"
    assert response.mitre_decision["requires_more_context_for_supported_mapping"] is False

    assert response.workflow_plan is not None
    assert response.workflow_plan.execution_enabled is False
    assert response.execution is not None
    assert response.execution.status == "skipped"
    assert response.execution.executed_spl is None
    assert response.answer_contract is not None
    assert response.answer_contract["spl_execution_eligible"] is False
    assert response.structured_context is not None
    assert response.structured_context.final_evidence_gate is not None
    gate = response.structured_context.final_evidence_gate
    assert gate["allow_mitre_mapping"] is False
    assert gate["collected_evidence_count"] == 0
    assert gate["candidate_claim_count"] == 0
    review_refs = set(gate["review_artifact_refs"])
    assert review_refs
    assert all(set(mapping.source_refs) <= review_refs for mapping in response.mitre_mappings)


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
