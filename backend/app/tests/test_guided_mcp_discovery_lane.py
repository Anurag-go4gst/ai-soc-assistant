from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_loop import ROUTE_EXECUTE, ROUTE_FINALIZE, assess_loop, initialize_loop, record_hop
from app.chat.evidence_planner import plan_evidence
from app.chat.guided_discovery_promotion import build_guided_discovery_promotion_offer
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import _mcp_evidence_loop_enabled
from app.config import settings
from app.planner.composer import build_guided_investigation_resource_decisions
from app.query_understanding.parser import understand_query


_GUIDED_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def _guided_plan(monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    understanding = understand_query(_GUIDED_QUERY)
    q2i = build_query_to_intent(query=_GUIDED_QUERY, query_understanding=understanding)
    return plan_evidence(
        q2i.intent_classification,
        q2i.model_dump(),
        routed={"skill": "guided_investigation"},
        query_understanding=understanding,
    )


def test_flag_defaults_off() -> None:
    assert settings.ai_soc_guided_mcp_discovery_enabled is False


def test_evidence_plan_discovery_allowed_unset_by_default() -> None:
    field = EvidencePlan.model_fields["discovery_allowed"]
    assert field.default is None


def test_guided_plan_discovery_allowed_follows_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_mcp_discovery_enabled", True)
    plan = _guided_plan(monkeypatch)
    assert plan.discovery_allowed is True
    assert plan.mcp_allowed is False
    assert plan.spl_allowed is False

    monkeypatch.setattr(settings, "ai_soc_guided_mcp_discovery_enabled", False)
    plan_off = _guided_plan(monkeypatch)
    assert plan_off.discovery_allowed is not True
    assert plan_off.mcp_allowed is False


def test_other_families_keep_discovery_allowed_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_mcp_discovery_enabled", True)
    policy_plan = plan_evidence(
        build_query_to_intent(
            query="What is the escalation policy for repeated failed login alerts?",
            query_understanding=understand_query(
                "What is the escalation policy for repeated failed login alerts?"
            ),
        ).intent_classification,
        routed={},
    )
    assert policy_plan.discovery_allowed is not True


def test_mcp_evidence_loop_enabled_for_guided_discovery_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    evidence = {
        "answer_mode": "guided_investigation",
        "mcp_allowed": False,
        "discovery_allowed": True,
        "needs_mcp": False,
        "rag_phase": "rag_only",
    }
    state = {"planning_decision": {"path_type": "guided_investigation"}}
    assert _mcp_evidence_loop_enabled(state, evidence) is True


def test_mcp_evidence_loop_disabled_when_discovery_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    evidence = {
        "answer_mode": "guided_investigation",
        "mcp_allowed": False,
        "discovery_allowed": False,
        "needs_mcp": False,
        "rag_phase": "rag_only",
    }
    state = {"planning_decision": {"path_type": "guided_investigation"}}
    assert _mcp_evidence_loop_enabled(state, evidence) is False


def test_assessor_never_executes_on_discovery_only_lane() -> None:
    chronology = [
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_run_query",
    ]
    state = {
        **initialize_loop(chronology),
        "mcp_discovery_only": True,
    }
    for tool in ["splunk_get_info", "splunk_get_indexes", "splunk_get_metadata"]:
        state = {**state, **record_hop(state, tool=tool, delivered=["x"])}
    decision = assess_loop(state)
    assert decision.route == ROUTE_FINALIZE
    assert decision.route != ROUTE_EXECUTE


def test_guided_resource_decisions_emit_planned_discovery_when_enabled() -> None:
    plan = EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        discovery_allowed=True,
    )
    decisions = build_guided_investigation_resource_decisions(plan)
    mcp = decisions["mcp"]
    assert mcp["needed"] is True
    assert mcp["allowed"] is False
    assert "splunk_get_info" in mcp["planned_discovery"]
    assert "splunk_get_knowledge_objects" in mcp["planned_discovery"]
    assert "splunk_run_query" not in mcp["planned_discovery"]


def test_guided_resource_decisions_unchanged_when_discovery_off() -> None:
    plan = EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        discovery_allowed=False,
    )
    decisions = build_guided_investigation_resource_decisions(plan)
    assert decisions["mcp"]["needed"] is False


def test_promotion_offer_on_knowledge_object_hit() -> None:
    offer = build_guided_discovery_promotion_offer(
        [
            {
                "tool": "splunk_get_knowledge_objects",
                "payload": {
                    "preview_rows": [{"name": "OT DNS Hunt", "object_type": "saved_search"}],
                },
            }
        ]
    )
    assert offer is not None
    assert offer["suggested_route"] == "spl_generation"
    assert offer["analyst_confirmation_required"] is True
    assert "OT DNS Hunt" in offer["message"]


def test_promotion_offer_absent_without_knowledge_hit() -> None:
    assert build_guided_discovery_promotion_offer([]) is None
    assert build_guided_discovery_promotion_offer(
        [{"tool": "splunk_get_indexes", "payload": {"preview_rows": []}}]
    ) is None


def test_planned_hop_excluded_from_collected_count() -> None:
    from app.evidence.source_evidence import append_mcp_loop_source_evidence

    merged = append_mcp_loop_source_evidence(
        [],
        trace_id="trace-guided",
        mcp_evidence=[
            {
                "tool": "splunk_get_info",
                "delivered": ["server_version"],
                "outcome": "planned",
                "payload": {"read_only": True},
            }
        ],
    )
    assert len(merged) == 1
    assert merged[0]["collection_status"] == "planned"
    assert merged[0]["source_type"] == "mcp_discovery"
