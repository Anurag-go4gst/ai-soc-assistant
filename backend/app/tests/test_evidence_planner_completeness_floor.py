"""Evidence planner wires completeness floor into live evidence_plan."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.select_route_from_understanding import select_route_from_understanding


def test_mitre_mapping_thin_plan_escalates_to_hybrid_with_spl(monkeypatch):
    class _Curated:
        spl_template_status = "active"
        mitre_candidates = ["T1110", "T1021"]

    monkeypatch.setattr(
        "app.chat.evidence_planner.get_runtime_curated_enrichment",
        lambda use_case_id: _Curated() if use_case_id == "auth_failed_login_spike" else None,
    )
    query = "Map this alert to MITRE techniques for lateral movement in OT segment 3"
    understanding = understand_query(query)
    understanding.soc_investigation_shaped = True
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    intent = q2i.intent_classification.model_copy(update={"intent_family": "mitre_mapping"})
    plan = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
        selected_use_case=SimpleNamespace(use_case_id="auth_failed_login_spike"),
    )
    assert plan.answer_mode == "hybrid"
    assert plan.needs_spl is True
    assert plan.spl_allowed is True
    assert "completeness_floor_escalated_thin_in_catalog_under_route" in plan.reasons


def test_completeness_floor_prevents_rag_only_route_adjudication(monkeypatch):
    class _Curated:
        spl_template_status = "active"
        mitre_candidates = ["T1110", "T1021"]

    monkeypatch.setattr(
        "app.chat.evidence_planner.get_runtime_curated_enrichment",
        lambda use_case_id: _Curated() if use_case_id == "auth_failed_login_spike" else None,
    )
    query = "Map this alert to MITRE techniques for lateral movement in OT segment 3"
    understanding = understand_query(query)
    understanding.soc_investigation_shaped = True
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    intent = q2i.intent_classification.model_copy(update={"intent_family": "mitre_mapping"})
    routed, _ = select_route_from_understanding(understanding, query)
    plan = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        routed=routed,
        query_understanding=understanding,
        selected_use_case=SimpleNamespace(use_case_id="auth_failed_login_spike"),
    )
    adjudicated = adjudicate_route(
        deterministic_route=routed["skill"],
        evidence_plan=plan,
        intent_classification=intent,
        query_understanding=understanding,
        query_to_intent=q2i.model_dump(),
    )
    assert adjudicated.authority_source != "evidence_plan_rag_only"
    assert plan.spl_allowed is True
    assert plan.answer_mode == "hybrid"
