"""pk.001 slice — containment decision-support vs enforcement command split."""

from __future__ import annotations

from app.chat.query_signals import extract_query_signals

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


def test_enforcement_imperative_not_decision_support() -> None:
    signals = extract_query_signals(_ENFORCE_NOW)
    assert signals["block_or_contain"] is True
    assert signals["containment_decision_support"] is False


def test_account_disable_command_not_decision_support() -> None:
    signals = extract_query_signals(_ENFORCE_ACCOUNT)
    assert signals["block_or_contain"] is True
    assert signals["containment_decision_support"] is False
