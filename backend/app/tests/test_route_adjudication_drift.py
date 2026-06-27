from __future__ import annotations

from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import (
    _provisional_evidence_plan_for_adjudication,
    _route_adjudication_with_final_plan_drift,
)
from app.config import settings
from app.query_understanding.parser import understand_query


def test_provisional_adjudication_plan_carries_q046_weak_known_status() -> None:
    query = "Which users have excessive failed logins?"
    understanding = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=understanding,
        routed_skill="attack_discovery",
    )

    plan = _provisional_evidence_plan_for_adjudication(
        {
            "intent_classification": q2i.intent_classification.model_dump(),
            "query_to_intent": q2i.model_dump(),
            "query_understanding": understanding,
            "routed": {"skill": "attack_discovery"},
        }
    )

    assert plan is not None
    assert plan["row_authority_summary"]["question_ref"] == "q0.q046"
    assert plan["row_authority_summary"]["row_authority_status"] == "exact_known_weak_needs_enrichment"
    assert plan["row_authority_summary"]["s3_authority_ready"] is False


def test_final_plan_drift_narrows_mcp_without_route_replacement(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)

    adjudication = {
        "final_route": "spl_generation",
        "authority_source": "evidence_plan_live_or_hybrid",
    }
    updated = _route_adjudication_with_final_plan_drift(
        adjudication,
        {
            "answer_mode": "live_investigation",
            "needs_spl": True,
            "spl_allowed": True,
            "needs_mcp": True,
            "mcp_allowed": None,
            "row_authority_summary": {"row_authority_status": "exact_known_weak_needs_enrichment"},
        },
    )

    assert updated is not None
    assert updated["final_route"] == "spl_generation"
    drift = updated["final_evidence_plan_drift"]
    assert drift["status"] == "capability_narrowed"
    assert drift["route_preserved"] is True
    assert drift["selected_route"] == "spl_generation"
    assert drift["capabilities_narrowed"] == ["mcp_execution"]
    assert drift["mcp_allowed_normalized"]["source"] == "evidence_plan_null"
    assert drift["row_authority_status"] == "exact_known_weak_needs_enrichment"


def test_final_evidence_plan_route_drift_is_recorded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    adjudication = {
        "final_route": "attack_discovery",
        "authority_source": "evidence_plan_live_or_hybrid",
    }
    updated = _route_adjudication_with_final_plan_drift(
        adjudication,
        {
            "answer_mode": "live_investigation",
            "needs_spl": True,
            "spl_allowed": True,
            "needs_mcp": True,
            "mcp_allowed": None,
        },
    )
    drift = updated["final_evidence_plan_drift"]
    assert drift["route_preserved"] is True
    assert drift["selected_route"] == "attack_discovery"
    assert drift["status"] in {"capability_narrowed", "aligned"}
    assert "mcp_allowed_normalized" in drift
