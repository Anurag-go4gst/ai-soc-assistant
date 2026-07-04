"""pk.001 slice — containment decision-support vs enforcement command split."""

from __future__ import annotations

from app.chat.intent_classifier import build_query_to_intent
from app.chat.query_signals import extract_query_signals
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding

_DECISION = (
    "Ransomware just hit our corporate IT domain controller. Should we isolate the OT "
    "network from IT right now, and what exact steps should the SOC take to protect the "
    "SCADA environment without tripping the grid?"
)
_ENFORCE_NOW = "Isolate the OT host now."
_ENFORCE_ACCOUNT = "Disable the account for user jdoe."


def test_decision_support_question_flagged() -> None:
    signals = extract_query_signals(_DECISION)
    assert signals["block_or_contain"] is True
    assert signals["containment_decision_support"] is True


def test_decision_support_routes_guided_review_only(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    understanding = understand_query(_DECISION)
    route, _ = select_route_from_understanding(understanding, _DECISION)
    assert route["skill"] == "guided_investigation"

    qi = build_query_to_intent(
        query=_DECISION,
        query_understanding=understanding,
        routed_skill=route["skill"],
    )
    assert qi.intent_classification.intent_family == "guided_investigation"
    assert qi.intent_classification.action_mode == "recommend_only"


def test_enforcement_imperative_not_decision_support() -> None:
    signals = extract_query_signals(_ENFORCE_NOW)
    assert signals["block_or_contain"] is True
    assert signals["containment_decision_support"] is False


def test_account_disable_command_not_decision_support() -> None:
    signals = extract_query_signals(_ENFORCE_ACCOUNT)
    assert signals["block_or_contain"] is True
    assert signals["containment_decision_support"] is False
