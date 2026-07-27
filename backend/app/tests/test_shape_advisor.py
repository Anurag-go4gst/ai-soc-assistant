from __future__ import annotations

import pytest

from app.chat.pipeline import graph_node_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.chat.shape_advisor import ShapeAdvisoryResult, apply_shape_advisory_promotion
from app.config import settings
from app.llm.turn_llm_budget import TurnLlmBudget
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest


PARTIAL_REFERENCE = "Prompt injection against our LLM agent using MCP tools"
DETERMINISTIC_REFERENCE = "Explain CVE-2024-3400."
NEGATIVE_LIVE = "Search our logs for CVE-2024-3400 exploitation attempts"


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)


def _state(query: str, *, max_sidecars: int = 3) -> dict:
    return {
        "request": ChatRequest(message=query),
        "effective_query": query,
        "query_understanding": understand_query(query),
        "routed": {"skill": "guided_investigation", "tool_plan": []},
        "llm_turn_budget": TurnLlmBudget(max_sidecar_calls=max_sidecars, deadline_seconds=30.0),
    }


def _advisory(shape: str, deterministic: str = "hunt") -> ShapeAdvisoryResult:
    return ShapeAdvisoryResult(
        suggested_shape=shape,
        confidence=0.92,
        rationale="test",
        llm_called=True,
        provider_label="fake",
        deterministic_shape=deterministic,
    )


def test_partial_signal_promotion_to_reference_taxonomy() -> None:
    promoted = apply_shape_advisory_promotion(PARTIAL_REFERENCE, _advisory("reference_taxonomy"))
    assert promoted.used is True
    assert promoted.promoted_shape == "reference_taxonomy"


def test_deterministic_match_wins_over_conflicting_advisory() -> None:
    ignored = apply_shape_advisory_promotion(DETERMINISTIC_REFERENCE, _advisory("hunt", "reference_taxonomy"))
    assert ignored.used is False
    assert ignored.ignored_reason == "advisory_ignored_deterministic_match"


def test_negative_live_data_signal_blocks_reference_promotion() -> None:
    ignored = apply_shape_advisory_promotion(NEGATIVE_LIVE, _advisory("reference_taxonomy"))
    assert ignored.used is False
    assert ignored.ignored_reason == "reference_taxonomy_negative_signal"


def test_query_to_intent_records_mismatch_without_using_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline.generate_shape_advisory",
        lambda *args, **kwargs: _advisory("hunt", "reference_taxonomy"),
    )
    out = graph_node_query_to_intent(_state(DETERMINISTIC_REFERENCE))
    trace = out["shape_advisory"]
    assert trace["used"] is False
    assert trace["ignored_reason"] == "advisory_ignored_deterministic_match"
    assert out["intent_classification"]["intent_family"] == "reference_knowledge"


def test_query_to_intent_consumes_guarded_reference_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline.generate_shape_advisory",
        lambda *args, **kwargs: _advisory("reference_taxonomy", "hunt"),
    )
    out = graph_node_query_to_intent(_state(PARTIAL_REFERENCE))
    assert out["shape_advisory"]["used"] is True
    assert out["shape_advisory"]["promoted_shape"] == "reference_taxonomy"
    assert out["routed"]["skill"] == "knowledge_recall"
    assert out["intent_classification"]["intent_family"] == "reference_knowledge"


def test_budget_exhaustion_records_skip_and_keeps_deterministic_path() -> None:
    out = graph_node_query_to_intent(_state(PARTIAL_REFERENCE, max_sidecars=0))
    assert out["shape_advisory"]["skipped_reason"] == "turn_budget_exhausted"
    assert out["shape_advisory"]["used"] is False


@pytest.mark.parametrize(
    "query",
    [
        "Map this alert to MITRE: 5 failed logins then success on DC-01",
        "Give me SPL to detect brute force",
        "Search our logs for CVE-2024-3400 exploitation attempts",
        "Which users have excessive failed logins?",
    ],
)
def test_recorded_unused_advisory_does_not_change_visible_answer(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    def answer_view() -> dict:
        payload = build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")
        candidate_spl = dict(payload.get("candidate_spl") or {})
        candidate_spl_view = {
            key: candidate_spl.get(key)
            for key in (
                "candidate_spl",
                "generation_mode",
                "confidence",
                "template_id",
                "candidate_spl_generated",
                "validation_required",
                "execution_eligible",
                "warnings",
            )
        }
        return {
            "message": payload.get("message"),
            "selected_skill": payload.get("selected_skill"),
            "answer_mode": (payload.get("evidence_plan") or {}).get("answer_mode"),
            "human_review": payload.get("human_review"),
            "analyst_response": payload.get("analyst_response"),
            "candidate_spl": candidate_spl_view,
        }

    monkeypatch.setattr(
        "app.chat.pipeline.generate_shape_advisory",
        lambda *args, **kwargs: ShapeAdvisoryResult(
            suggested_shape="none",
            llm_called=True,
            provider_label="fake",
            deterministic_shape="hunt",
        ),
    )
    with_advisory = answer_view()

    monkeypatch.setattr(
        "app.chat.pipeline.generate_shape_advisory",
        lambda *args, **kwargs: ShapeAdvisoryResult(
            deterministic_shape="hunt",
            skipped_reason="test_skip",
        ),
    )
    without_used_advisory = answer_view()
    assert with_advisory == without_used_advisory
