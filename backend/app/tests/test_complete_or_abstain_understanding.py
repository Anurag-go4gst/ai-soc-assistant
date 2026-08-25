"""P1 — T1-T3 complete-or-abstain acceptance gate.

Frozen architecture.md §2.2: T1-T3 either ACCEPT a complete, sufficiently
confident governed match (and T4 is skipped) or ABSTAIN completely. There is no
partial semantic contract for T4 to patch.

These tests pin the gate's decision surface, not any single query's phrasing —
no test here special-cases a user sentence.
"""

from __future__ import annotations

import pytest

from app.chat.complete_or_abstain_gate import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_MARGIN,
    MatchCandidate,
    UnderstandingAcceptance,
    evaluate_complete_or_abstain,
)


def _candidate(confidence: float = 0.95, cid: str = "c1", source: str = "lexical") -> MatchCandidate:
    return MatchCandidate(
        candidate_id=cid,
        match_path="exact_105_question",
        confidence=confidence,
        source=source,  # type: ignore[arg-type]
    )


# --- ACCEPT paths -----------------------------------------------------------


def test_exact_105_accepts_and_skips_t4() -> None:
    """T1 exact match, complete and confident -> ACCEPT, T4 skipped."""
    result = evaluate_complete_or_abstain(
        match_path="exact_105_question",
        candidates=[_candidate()],
    )
    assert result.is_accept
    assert result.tier == "T1"
    assert result.t4_permitted is False, "T4 must be skipped on ACCEPT"
    assert result.accepted_candidate_id == "c1"
    assert result.reason_codes == ("complete_governed_match",)


@pytest.mark.parametrize(
    ("match_path", "expected_tier"),
    [
        ("exact_105_question", "T1"),
        ("use_case_catalog", "T2"),
        ("near_105_question", "T3"),
        ("semantic_105_question", "T3"),
    ],
)
def test_strong_governed_paraphrase_accepts_across_tiers(match_path: str, expected_tier: str) -> None:
    """A strong catalogue paraphrase accepts on any governed tier, not just T1."""
    result = evaluate_complete_or_abstain(
        match_path=match_path,
        candidates=[MatchCandidate(candidate_id="c1", match_path=match_path, confidence=0.92)],
    )
    assert result.is_accept
    assert result.tier == expected_tier


def test_accept_requires_no_unresolved_and_no_missing() -> None:
    result = evaluate_complete_or_abstain(
        match_path="use_case_catalog",
        candidates=[_candidate(0.9)],
        unresolved_fields=(),
        missing_required_fields=(),
        completeness_status="complete",
    )
    assert result.is_accept


# --- ABSTAIN paths ----------------------------------------------------------


def test_unclear_objective_abstains_completely() -> None:
    """Incomplete understanding abstains; it never emits a partial contract."""
    result = evaluate_complete_or_abstain(
        match_path="use_case_catalog",
        candidates=[_candidate(0.9)],
        completeness_status="incomplete",
    )
    assert result.is_abstain
    assert result.t4_permitted is True
    assert "completeness_incomplete" in result.reason_codes
    assert result.accepted_candidate_id is None, "abstain must commit nothing"


def test_unknown_soc_ask_abstains() -> None:
    """Out-of-registry with no complete deterministic contract abstains."""
    result = evaluate_complete_or_abstain(
        match_path="out_of_registry",
        candidates=[],
    )
    assert result.is_abstain
    assert result.tier == "T4"
    assert "not_governed_tier" in result.reason_codes


def test_complete_deterministic_out_of_registry_accepts_and_skips_t4() -> None:
    """Fully resolved DET understanding ACCEPTs even without a catalogue tier."""
    result = evaluate_complete_or_abstain(
        match_path="out_of_registry",
        candidates=[],
        semantic_contract_complete=True,
    )
    assert result.is_accept
    assert result.t4_permitted is False
    assert result.reason_codes == ("complete_deterministic_understanding",)


def test_single_generic_token_cannot_bind_rich_detection() -> None:
    """A thin, ambiguous winner must not bind a rich governed detection.

    Modelled generically: a low-confidence winner in a crowded candidate field.
    """
    result = evaluate_complete_or_abstain(
        match_path="use_case_catalog",
        candidates=[
            MatchCandidate(candidate_id="generic", match_path="use_case_catalog", confidence=0.41),
            MatchCandidate(candidate_id="rich", match_path="use_case_catalog", confidence=0.39),
        ],
    )
    assert result.is_abstain
    assert "low_confidence" in result.reason_codes
    assert "low_margin" in result.reason_codes


def test_low_margin_abstains_even_when_confident() -> None:
    """Clearing the confidence floor is not enough when candidates are crowded."""
    result = evaluate_complete_or_abstain(
        match_path="use_case_catalog",
        candidates=[
            MatchCandidate(candidate_id="a", match_path="use_case_catalog", confidence=0.95),
            MatchCandidate(candidate_id="b", match_path="use_case_catalog", confidence=0.94),
        ],
    )
    assert result.is_abstain
    assert result.reason_codes == ("low_margin",)
    assert result.winner_confidence == pytest.approx(0.95)
    assert result.winner_margin == pytest.approx(0.01)


def test_unresolved_field_forces_full_abstain_not_partial_commit() -> None:
    """The partial-contract signal must produce a *complete* abstain."""
    result = evaluate_complete_or_abstain(
        match_path="exact_105_question",
        candidates=[_candidate()],
        unresolved_fields=("semantic_goal",),
    )
    assert result.is_abstain
    assert "unresolved_semantic_fields" in result.reason_codes
    assert result.accepted_candidate_id is None


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"clarification_required": True}, "clarification_required"),
        ({"policy_blocked": True}, "policy_blocked"),
        ({"missing_required_fields": ("index",)}, "missing_required_fields"),
        ({"semantically_compatible": False}, "semantic_incompatibility"),
        ({"fully_governed": False}, "not_fully_governed"),
        ({"completeness_status": "clarification_required"}, "clarification_required"),
    ],
)
def test_each_architecture_abstain_trigger(kwargs: dict, expected_reason: str) -> None:
    result = evaluate_complete_or_abstain(
        match_path="exact_105_question",
        candidates=[_candidate()],
        **kwargs,
    )
    assert result.is_abstain
    assert expected_reason in result.reason_codes


def test_governed_tier_with_no_candidate_abstains() -> None:
    result = evaluate_complete_or_abstain(match_path="exact_105_question", candidates=[])
    assert result.is_abstain
    assert "no_candidate" in result.reason_codes


# --- gate properties --------------------------------------------------------


def test_decision_is_binary_never_partial() -> None:
    """The gate has exactly two outcomes; ACCEPT and ABSTAIN are complementary."""
    for kwargs in (
        {"candidates": [_candidate()]},
        {"candidates": [_candidate(0.2)]},
        {"candidates": []},
        {"candidates": [_candidate()], "policy_blocked": True},
    ):
        result = evaluate_complete_or_abstain(match_path="exact_105_question", **kwargs)
        assert result.decision in {"ACCEPT", "ABSTAIN"}
        assert result.is_accept is not result.is_abstain
        assert result.t4_permitted is result.is_abstain


def test_all_applicable_reasons_collected_not_short_circuited() -> None:
    result = evaluate_complete_or_abstain(
        match_path="out_of_registry",
        candidates=[],
        clarification_required=True,
        policy_blocked=True,
    )
    assert {"not_governed_tier", "clarification_required", "policy_blocked"} <= set(result.reason_codes)


def test_reason_codes_sorted_and_deduplicated() -> None:
    result = evaluate_complete_or_abstain(
        match_path="out_of_registry",
        candidates=[],
        policy_blocked=True,
        clarification_required=True,
    )
    assert list(result.reason_codes) == sorted(set(result.reason_codes))


def test_embedding_candidates_share_the_same_gate_without_new_authority() -> None:
    """Future T3 embedding candidates are a *source*, never an authority tier.

    An embedding candidate is subject to the identical confidence/margin rules,
    so it cannot rescue an otherwise-abstaining match.
    """
    weak = evaluate_complete_or_abstain(
        match_path="near_105_question",
        candidates=[
            MatchCandidate(
                candidate_id="emb", match_path="near_105_question", confidence=0.5, source="embedding"
            )
        ],
    )
    assert weak.is_abstain
    assert "low_confidence" in weak.reason_codes

    strong = evaluate_complete_or_abstain(
        match_path="near_105_question",
        candidates=[
            MatchCandidate(
                candidate_id="emb", match_path="near_105_question", confidence=0.93, source="embedding"
            )
        ],
    )
    assert strong.is_accept
    assert strong.candidate_sources == ("embedding",)


def test_gate_thresholds_are_overridable_but_default_to_routing_floor() -> None:
    assert DEFAULT_MIN_CONFIDENCE == 0.70
    assert DEFAULT_MIN_MARGIN == 0.10
    strict = evaluate_complete_or_abstain(
        match_path="exact_105_question",
        candidates=[_candidate(0.80)],
        min_confidence=0.90,
    )
    assert strict.is_abstain
    assert "low_confidence" in strict.reason_codes


def test_result_is_immutable() -> None:
    result = evaluate_complete_or_abstain(
        match_path="exact_105_question", candidates=[_candidate()]
    )
    assert isinstance(result, UnderstandingAcceptance)
    with pytest.raises(Exception):
        result.decision = "ABSTAIN"  # type: ignore[misc]
