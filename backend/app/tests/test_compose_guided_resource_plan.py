"""REV4 batch 1 P4 — compose_guided_resource_plan and evidence planner deferral."""

from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_planner import plan_evidence
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.intent_classifier import build_query_to_intent
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.config import settings
from app.planner.composer import compose_guided_resource_plan, compose_resource_plan
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)
_KNOWLEDGE_QUERY = "What is the escalation policy for repeated failed login alerts?"


def _guided_evidence_plan(monkeypatch: pytest.MonkeyPatch, *, hybrid_flag: bool) -> EvidencePlan:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", hybrid_flag)
    understanding = understand_query(SAMPLE_QUERY)
    base, provenance = select_route_from_understanding(understanding, SAMPLE_QUERY)
    routed = {**base, "routing_provenance": provenance}
    query_to_intent = build_query_to_intent(
        query=SAMPLE_QUERY,
        query_understanding=understanding,
        routed_skill=base["skill"],
    )
    return plan_evidence(
        query_to_intent.intent_classification,
        query_to_intent=query_to_intent.model_dump(),
        routed=routed,
        query_understanding=understanding,
    )


def test_compose_guided_resource_plan_maps_validated_investigation_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _guided_evidence_plan(monkeypatch, hybrid_flag=True)
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    validated = validate_investigation_plan(
        baseline.model_copy(
            update={
                "read_only_tool_requests": ["mcp_tool:splunk_get_info"],
                "safe_spl_template_requests": ["dns_beaconing_candidate"],
            }
        )
    )
    plan = compose_guided_resource_plan(evidence, validated, match_path="out_of_registry")
    step_ids = [step.step_id for step in plan.steps]
    assert step_ids[0] == "rag"
    assert "discovery_0" in step_ids
    assert any(step.resource_id == "mcp_tool:splunk_get_info" for step in plan.steps)
    assert "evidence" in step_ids and "sufficiency" in step_ids and "narration" in step_ids
    assert plan.provenance.get("composer") == "guided_hybrid_v1"
    assert "resource_decisions" not in plan.provenance


def test_guided_hybrid_flag_on_defers_compose_at_evidence_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _guided_evidence_plan(monkeypatch, hybrid_flag=True)
    assert evidence.investigation_planning_enabled is True
    assert evidence.discovery_allowed is True
    assert evidence.safe_spl_execution_allowed is False
    assert evidence.resource_plan is None


def test_guided_flag_off_still_composes_at_evidence_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _guided_evidence_plan(monkeypatch, hybrid_flag=False)
    assert evidence.resource_plan is not None
    assert evidence.investigation_planning_enabled is None
    payload = evidence.model_dump(exclude_none=True)
    for key in (
        "discovery_allowed",
        "investigation_planning_enabled",
        "spl_review_allowed",
        "safe_spl_execution_allowed",
    ):
        assert key not in payload


def test_knowledge_recall_still_uses_legacy_compose_resource_plan() -> None:
    evidence = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=True,
        policy_context_recommended=False,
        reasons=["policy_context_required"],
    )
    plan = compose_resource_plan(evidence, intent_family="policy_knowledge")
    assert [step.step_id for step in plan.steps] == ["rag", "narration"]
    assert plan.provenance.get("composer") == "deterministic_v1"
