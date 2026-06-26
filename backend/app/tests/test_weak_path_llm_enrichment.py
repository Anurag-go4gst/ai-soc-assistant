"""Weak-path LLM composition — low-confidence and query_understanding_weak."""

from __future__ import annotations

import pytest

from app.chat.contracts.answer_contract import AnswerContract
from app.synthesis.composition_confidence import qualifies_for_weak_case_composition


def test_query_understanding_weak_match_path_qualifies() -> None:
    contract = AnswerContract(missing_evidence=[], hil_status="not_required")
    assert qualifies_for_weak_case_composition(
        contract,
        match_path="query_understanding_weak",
    )


def test_low_router_confidence_qualifies() -> None:
    contract = AnswerContract(missing_evidence=[], hil_status="not_required")
    assert qualifies_for_weak_case_composition(
        contract,
        router_confidence=0.2,
    )


def test_high_confidence_catalog_path_does_not_qualify() -> None:
    contract = AnswerContract(
        missing_evidence=[],
        hil_status="not_required",
        intent_family="auth_failed_login",
        answer_mode="evidence_backed",
    )
    assert not qualifies_for_weak_case_composition(
        contract,
        match_path="use_case",
        router_confidence=0.9,
    )


def test_clarification_turn_qualifies() -> None:
    contract = AnswerContract(
        missing_evidence=[],
        hil_status="not_required",
        answer_mode="clarification",
    )
    assert qualifies_for_weak_case_composition(
        contract,
        needs_clarification=True,
    )
