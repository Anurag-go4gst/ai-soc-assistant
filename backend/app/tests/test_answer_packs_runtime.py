from __future__ import annotations

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query
from app.use_cases import answer_packs
from app.use_cases.answer_packs import answer_pack_summary, reviewed_answer_pack


def test_answer_packs_json_loads_reviewed_runtime_pack() -> None:
    answer_packs.load_answer_packs.cache_clear()
    pack = reviewed_answer_pack(case_id="q0.q046")
    assert pack is not None
    assert pack["review_status"] == "reviewed"
    assert "raw_llm_prose" not in pack
    summary = answer_pack_summary(pack)
    assert summary["runtime_authority"] == "evidence_plan_enrichment_only"
    assert summary["raw_llm_prose_loaded"] is False
    assert summary["mitre_candidate_status"] == "candidate_only"


def test_answer_pack_mitre_candidate_stays_candidate_without_evidence() -> None:
    answer_packs.load_answer_packs.cache_clear()
    query = "Which users have excessive failed logins?"
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)

    plan = plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
    )

    assert "T1110" in plan.mitre_candidates_metadata_only
    assert "T1110" not in plan.present_evidence_keys
    assert plan.answer_pack_summary is not None
    assert plan.answer_pack_summary["mitre_candidate_status"] == "candidate_only"


def test_answer_pack_spl_family_suggestion_requires_template_or_validator(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "case": {
                "case_id": "case",
                "review_status": "reviewed",
                "spl_family_suggestion": "unvalidated_family",
            }
        },
    )
    pack = reviewed_answer_pack(case_id="case")
    assert pack is not None
    assert "spl_family_suggestion" not in pack

    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "case": {
                "case_id": "case",
                "review_status": "reviewed",
                "spl_family_suggestion": "validated_family",
                "spl_validator_id": "validator.v1",
            }
        },
    )
    pack = reviewed_answer_pack(case_id="case")
    assert pack is not None
    assert pack["spl_family_suggestion"] == "validated_family"


def test_at_least_five_reviewed_weak_known_packs_load() -> None:
    answer_packs.load_answer_packs.cache_clear()
    packs = answer_packs.load_answer_packs()
    reviewed_ids = [
        key
        for key, pack in packs.items()
        if str(pack.get("review_status") or "").lower() == "reviewed" and key.startswith("q0.")
    ]
    assert len(reviewed_ids) >= 5
    for case_id in ("q0.q004", "q0.q006", "q0.q002", "q0.q003", "q0.q010"):
        assert reviewed_answer_pack(case_id=case_id) is not None


def test_q004_lookup_pack_enriches_evidence_plan_only() -> None:
    answer_packs.load_answer_packs.cache_clear()
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.query_understanding.parser import understand_query

    query = "Which hosts contacted known malicious IPs today?"
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    plan = plan_evidence(q2i.intent_classification, query_to_intent=q2i.model_dump(), query_understanding=understanding)
    assert plan.answer_pack_summary is not None
    assert "reviewed_answer_pack_projection" in plan.reasons
    assert "T1071" in plan.mitre_candidates_metadata_only
    assert "T1071" not in plan.present_evidence_keys
    assert "raw_llm_prose" not in (plan.answer_pack_summary or {})
