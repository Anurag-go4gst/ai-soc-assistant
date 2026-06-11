"""T1.1 — semantic 105-question match tier."""

from __future__ import annotations

from app.coverage.semantic_question_index import (
    SEMANTIC_MATCH_MARGIN,
    SEMANTIC_MATCH_THRESHOLD,
    clear_semantic_index_cache,
    semantic_question_match,
)
from app.query_understanding.parser import understand_query


def test_close_paraphrase_matches_canonical_row() -> None:
    match = semantic_question_match("Which endpoints ran suspicious powershell commands?")
    assert match is not None
    assert match["question_ref"] == "q0.q049"
    assert match["_semantic_match_score"] >= SEMANTIC_MATCH_THRESHOLD


def test_unrelated_query_does_not_match() -> None:
    assert semantic_question_match("best pasta recipe for dinner tonight") is None


def test_empty_query_does_not_match() -> None:
    assert semantic_question_match("") is None
    assert semantic_question_match("the of and") is None


def test_ambiguity_margin_blocks_near_ties() -> None:
    # With margin forced huge, even a confident winner must be rejected when
    # a runner-up exists — proves the margin gate is active.
    confident = "Which endpoints ran suspicious powershell commands?"
    assert semantic_question_match(confident, margin=1.0) is None
    assert semantic_question_match(confident, margin=SEMANTIC_MATCH_MARGIN) is not None


def test_match_returns_registry_row_never_invents() -> None:
    match = semantic_question_match("Which endpoints ran suspicious powershell commands?")
    assert match is not None
    # Carries the canonical registry fields, not synthesized ones.
    for key in ("question_ref", "question", "pattern_type", "proposed_primary_skill"):
        assert key in match


def test_ladder_order_exact_still_wins() -> None:
    result = understand_query("Which hosts are generating the most SMB traffic?")
    assert result.deterministic_match_path in {"exact_105_question", "exact_105_plus_use_case_catalog"}
    assert result.question_registry_match_source == "question_runtime_map_105_exact"


def test_ladder_order_near_token_outranks_semantic() -> None:
    result = understand_query("Which systems generated huge outbound data transfers yesterday?")
    assert result.deterministic_match_path != "semantic_105_question"
    assert result.mapped_question_ref == "q0.q013"


def test_catalog_match_still_inherits_semantic_question_ref() -> None:
    # "suspicious powershell" hits the use-case catalog (higher rung), but the
    # semantic row still populates mapped_question_ref — paraphrases inherit
    # the known 105 direction even when the catalog wins the path label.
    result = understand_query("Which endpoints ran suspicious powershell commands?")
    assert result.deterministic_match_path == "use_case_catalog"
    assert result.mapped_question_ref == "q0.q049"
    assert result.question_registry_match_source == "question_runtime_map_105_semantic"


def test_parser_surfaces_semantic_path_when_threshold_met(monkeypatch) -> None:
    import app.coverage.semantic_question_index as sqi

    monkeypatch.setattr(sqi, "SEMANTIC_MATCH_THRESHOLD", 0.60)
    result = understand_query("Whcih hosts are generatng the most SMB trafic?")
    assert result.deterministic_match_path == "semantic_105_question"
    assert result.question_registry_match_source == "question_runtime_map_105_semantic"
    assert result.mapped_question_ref == "q0.q010"
    assert result.question_registry_match_score is not None
    assert result.llm_advisory_recommended is True


def test_out_of_registry_unchanged_for_truly_unmatched() -> None:
    result = understand_query("completely unrelated cooking recipe question")
    assert result.deterministic_match_path == "out_of_registry"
    assert result.mapped_question_ref is None


def test_index_cache_clear_rebuilds() -> None:
    clear_semantic_index_cache()
    assert semantic_question_match("Which endpoints ran suspicious powershell commands?") is not None
