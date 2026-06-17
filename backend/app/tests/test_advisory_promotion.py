"""T1.3 — advisory promotion: LLM suggests, deterministic validation approves."""

from __future__ import annotations

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.intent_classifier import build_query_to_intent
from app.chat.llm_intent_advisor import apply_advisory_promotion
from app.query_understanding.parser import understand_query

# Out-of-registry phrasing whose semantic candidates include q0.q010.
OUT_OF_SET_QUERY = "top SMB talkers by host"


def _advisory(**overrides) -> LLMIntentAdvisory:
    base = dict(
        question_ref_candidate="q0.q010",
        confidence_metadata={"confidence": 0.85},
        llm_called=True,
        adjudication_status="accepted",
    )
    base.update(overrides)
    return LLMIntentAdvisory(**base)


def _mappings(match_path: str = "out_of_registry") -> dict:
    return {"question_ref": None, "use_case_ids": [], "match_path": match_path, "legacy_skill_hint": None}


def _promote(advisory, mappings=None, *, clar=False, hil=False, query=OUT_OF_SET_QUERY):
    return apply_advisory_promotion(
        advisory=advisory,
        candidate_mappings=mappings or _mappings(),
        intent_requires_clarification=clar,
        intent_requires_hil=hil,
        query=query,
    )


def test_promotion_happy_path() -> None:
    mappings, advisory = _promote(_advisory())
    assert mappings["match_path"] == "llm_promoted_with_registry_validation"
    assert mappings["question_ref"] == "q0.q010"
    assert advisory.adjudication_status == "promoted"


def test_no_promotion_on_exact_or_catalog_paths() -> None:
    for path in ("exact_105_question", "exact_105_plus_use_case_catalog", "use_case_catalog", "near_105_question", "semantic_105_question"):
        mappings, advisory = _promote(_advisory(), _mappings(path))
        assert mappings["match_path"] == path
        assert advisory.adjudication_status == "accepted"


def test_no_promotion_below_confidence() -> None:
    mappings, advisory = _promote(_advisory(confidence_metadata={"confidence": 0.6}))
    assert mappings["match_path"] == "out_of_registry"
    assert advisory.adjudication_status == "accepted"


def test_no_promotion_for_unknown_registry_ref() -> None:
    mappings, _ = _promote(_advisory(question_ref_candidate="q0.q999"))
    assert mappings["match_path"] == "out_of_registry"


def test_no_promotion_when_semantic_candidates_disagree(monkeypatch) -> None:
    # Candidates present but exclude the advisory ref -> semantic disagrees -> no promotion.
    import app.coverage.semantic_question_index as sqi

    monkeypatch.setattr(
        sqi, "semantic_candidates", lambda query, **kw: [{"question_ref": "q0.q010", "question": "x", "_semantic_match_score": 0.5}]
    )
    mappings, _ = _promote(_advisory(question_ref_candidate="q0.q049"))
    assert mappings["match_path"] == "out_of_registry"


def test_promotion_allowed_when_semantic_abstains(monkeypatch) -> None:
    import app.coverage.semantic_question_index as sqi

    monkeypatch.setattr(sqi, "semantic_candidates", lambda query, **kw: [])
    mappings, advisory = _promote(_advisory(question_ref_candidate="q0.q049"))
    assert mappings["match_path"] == "llm_promoted_with_registry_validation"
    assert advisory.adjudication_status == "promoted"


def test_unsafe_and_clarification_veto_promotion() -> None:
    mappings, _ = _promote(_advisory(), clar=True)
    assert mappings["match_path"] == "out_of_registry"
    mappings, _ = _promote(_advisory(), hil=True)
    assert mappings["match_path"] == "out_of_registry"


def test_non_accepted_advisory_never_promotes() -> None:
    for status in ("skipped", "rejected", "corrected"):
        mappings, _ = _promote(_advisory(adjudication_status=status))
        assert mappings["match_path"] == "out_of_registry"


def test_use_case_candidate_promotes_via_catalog() -> None:
    advisory = _advisory(question_ref_candidate=None, use_case_id_candidate="auth_privileged_login_anomaly")
    mappings, adv = _promote(advisory)
    assert mappings["match_path"] == "llm_promoted_with_registry_validation"
    assert "auth_privileged_login_anomaly" in mappings["use_case_ids"]
    assert adv.adjudication_status == "promoted"


def test_end_to_end_promotion_through_build_query_to_intent() -> None:
    understanding = understand_query(OUT_OF_SET_QUERY)
    assert understanding.deterministic_match_path == "out_of_registry"
    result = build_query_to_intent(
        query=OUT_OF_SET_QUERY,
        query_understanding=understanding,
        llm_intent_advisory=_advisory(adjudication_status="skipped"),
    )
    assert result.candidate_mappings["match_path"] == "llm_promoted_with_registry_validation"
    assert result.candidate_mappings["question_ref"] == "q0.q010"
    assert result.llm_intent_advisory.adjudication_status == "promoted"
    # §10.2 post-promotion intent reconcile: the promoted route must reach
    # intent_classification, not just candidate_mappings. q0.q010 is a
    # top_n_aggregation / aggregate_and_rank skill -> spl_generation_only.
    assert result.intent_classification.intent_family == "spl_generation_only"
    assert result.intent_classification.intent_family != "clarification_required"
    assert result.intent_classification.requires_clarification is False


def test_no_advisory_means_behavior_unchanged() -> None:
    understanding = understand_query(OUT_OF_SET_QUERY)
    result = build_query_to_intent(query=OUT_OF_SET_QUERY, query_understanding=understanding)
    assert result.candidate_mappings["match_path"] == "out_of_registry"
