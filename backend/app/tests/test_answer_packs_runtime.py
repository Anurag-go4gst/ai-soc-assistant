from __future__ import annotations

import pytest

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

def test_answer_pack_cannot_override_user_explicit_bindings(monkeypatch) -> None:
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.query_understanding.parser import understand_query

    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "q0.q046": {
                "case_id": "q0.q046",
                "review_status": "reviewed",
                "required_evidence": ["pack_only_field"],
                "user_explicit_overrides": {"index": "pack_index"},
            }
        },
    )
    query = "Generate SPL for index=scada_perf by rtu_id over last 24h"
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    plan = plan_evidence(
        q2i.intent_classification,
        query_to_intent=q2i.model_dump(),
        query_understanding=understanding,
    )
    assert plan.normalized_slot_summary is not None
    assert plan.normalized_slot_summary["normalized_slots"]["index"] == "scada_perf"
    assert plan.normalized_slot_summary["slot_sources"]["index"] == "user_explicit"


def test_answer_pack_does_not_return_final_runtime_prose(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.use_cases.answer_packs.load_answer_packs",
        lambda: {
            "q0.q046": {
                "case_id": "q0.q046",
                "review_status": "reviewed",
                "final_answer": "Pack prose must never render as runtime authority.",
                "raw_llm_prose": "Also forbidden.",
                "required_evidence": ["failed_login_count"],
            }
        },
    )
    pack = reviewed_answer_pack(case_id="q0.q046")
    assert pack is not None
    assert "final_answer" not in pack
    assert "raw_llm_prose" not in pack


def test_answer_pack_does_not_bypass_run_contract_or_final_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.pipeline import build_live_chat_response
    from app.config import settings
    from app.schemas.requests import ChatRequest

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    payload = build_live_chat_response(
        ChatRequest(message="Which users have excessive failed logins?")
    ).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    assert payload.get("evidence_plan", {}).get("answer_pack_summary") is not None
    assert contract.get("authority_holder") == "canonical_run_contract" or (
        (contract.get("routing") or {}).get("authority_holder") == "canonical_run_contract"
    )
    assert contract.get("collected_evidence_count") == 0
    assert contract.get("allow_live_result_language") is False
    assert gate.get("collected_evidence_count") == contract.get("collected_evidence_count")
    assert gate.get("allow_live_result_language") is contract.get("allow_live_result_language")

