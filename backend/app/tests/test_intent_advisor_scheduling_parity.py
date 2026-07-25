"""PR #58 — intent advisor skip parity for universal utility SPL authoring only."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.pipeline import graph_node_query_to_intent
from app.chat.query_signals import extract_query_signals
from app.chat.spl_authoring_intent import should_skip_intent_for_universal_utility_spl
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest

_WEEKEND_QUERY = (
    "Without using any specific company templates, write a standard, universal SPL block "
    "that extracts the hour of the day and day of the week from an event timestamp, "
    "filtering only for weekend events."
)
_SCADA_QUERY = (
    "Provide a complete SPL query for index=scada_perf using earliest=-30d to "
    "compute eventstats stdev baseline by rtu_id and filter anomalies in last 24h "
    "using transmission_error_count."
)
_ASA_QUERY = (
    "Generate SPL to correlate power_sector_iocs.csv indicator_ip with Cisco ASA "
    "traffic in index=cisco_asa against dest_ip for last 24h."
)
_SMB_TOP_TALKERS = "Which hosts are generating the most SMB traffic?"
_GUIDED_HUNT = "Hunt for CI/CD supply-chain compromise indicators across our environment"
_Q046 = "Which users have excessive failed logins?"
_STRFTIME_KNOWLEDGE = "What does strftime do in SPL?"
_EXPLICIT_SPL_NO_UNIVERSAL = "Write me a SPL query for failed logins"


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_skip_intent_advisor", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


def _skip_decision(query: str) -> tuple[bool, str | None]:
    signals = extract_query_signals(query)
    return should_skip_intent_for_universal_utility_spl(query, signals)


@pytest.mark.parametrize(
    "query",
    [
        _SCADA_QUERY,
        _ASA_QUERY,
        _SMB_TOP_TALKERS,
        _GUIDED_HUNT,
        _Q046,
        _STRFTIME_KNOWLEDGE,
    ],
)
def test_non_universal_queries_do_not_skip_intent_advisor(query: str) -> None:
    skip, reason = _skip_decision(query)
    assert skip is False
    assert reason is None


def test_weekend_universal_utility_skips_intent_advisor() -> None:
    skip, reason = _skip_decision(_WEEKEND_QUERY)
    assert skip is True
    assert reason == "intent_advisory_not_required_for_universal_utility_route"


def test_weekend_query_runs_intent_when_skip_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_skip_intent_advisor", False)
    mock_advisor = MagicMock(
        return_value=LLMIntentAdvisory(llm_called=True, adjudication_status="accepted")
    )
    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", mock_advisor)

    qu = understand_query(_WEEKEND_QUERY)
    route, _ = select_route_from_understanding(qu, _WEEKEND_QUERY)
    graph_node_query_to_intent(
        {
            "request": ChatRequest(message=_WEEKEND_QUERY),
            "effective_query": _WEEKEND_QUERY,
            "query_understanding": qu,
            "routed": {"skill": route["skill"]},
        }
    )
    mock_advisor.assert_called_once()


def test_explicit_spl_without_universal_phrasing_does_not_skip_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skip, reason = _skip_decision(_EXPLICIT_SPL_NO_UNIVERSAL)
    assert skip is False
    assert reason is None

    mock_advisor = MagicMock(
        return_value=LLMIntentAdvisory(llm_called=True, adjudication_status="accepted")
    )
    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", mock_advisor)

    qu = understand_query(_EXPLICIT_SPL_NO_UNIVERSAL)
    route, _ = select_route_from_understanding(qu, _EXPLICIT_SPL_NO_UNIVERSAL)
    graph_node_query_to_intent(
        {
            "request": ChatRequest(message=_EXPLICIT_SPL_NO_UNIVERSAL),
            "effective_query": _EXPLICIT_SPL_NO_UNIVERSAL,
            "query_understanding": qu,
            "routed": {"skill": route["skill"]},
        }
    )
    mock_advisor.assert_called_once()
