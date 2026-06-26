"""P1 live-efficacy routing gates: floors, advisory guards, boundary rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.query_signals import extract_query_signals
from app.query_understanding.parser import understand_query
from app.routing.governance import LLMSemanticAdvisoryResult, normalize_assisted_selection
from app.routing.select_route_from_understanding import select_route_from_understanding

REPO = Path(__file__).resolve().parents[3]
BANK = REPO / "docs" / "evals" / "live_efficacy_100_bank.json"


def _bank_questions() -> dict[str, str]:
    return {row["id"]: row["question"] for row in json.loads(BANK.read_text())["questions"]}


def _validated_advisory(query: str) -> LLMSemanticAdvisoryResult:
    return LLMSemanticAdvisoryResult(
        raw_query=query,
        llm_selected_skill_candidate="spl_generation",
        llm_use_case_candidate="auth_privileged_login_anomaly",
        llm_question_ref_candidate="q0.q010",
        llm_confidence_metadata={"confidence": 0.9},
        registry_valid=True,
    )


@pytest.mark.parametrize(
    "row_id",
    ["eff.072", "eff.098"],
)
def test_boundary_rows_block_llm_advisory_promotion(row_id: str) -> None:
    questions = _bank_questions()
    query = questions[row_id]
    understanding = understand_query(query)
    base, _ = select_route_from_understanding(understanding, query)
    assert base["skill"] == "knowledge_recall"

    selected, selected_by, _, guards = normalize_assisted_selection(
        query=query,
        deterministic=base,
        advisory=_validated_advisory(query),
        understanding=understanding,
    )
    assert selected["skill"] == "knowledge_recall"
    assert selected_by == "deterministic"
    assert any("blocks_advisory_promotion" in item for item in guards)


def test_eff_098_detects_destructive_firewall_action() -> None:
    query = _bank_questions()["eff.098"]
    signals = extract_query_signals(query)
    assert signals["block_or_contain"] is True
    assert signals["action_or_containment_shaped"] is True


def test_eff_072_blocks_investigation_and_spl_floors() -> None:
    from app.query_understanding.soc_investigation_shape import (
        detect_investigation_request,
        detect_spl_artifact_request,
        is_unsafe_execution,
    )

    query = _bank_questions()["eff.072"]
    normalized = " ".join(query.lower().split())
    assert is_unsafe_execution(normalized)
    assert detect_investigation_request(query) is False
    assert detect_spl_artifact_request(query) is False
