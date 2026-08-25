"""S6 — adjacent unseen variants and the required negative-loss matrix."""

from __future__ import annotations

import pytest

from app.config import settings
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity, validate_spl_structure
from app.spl.utility_spl_authoring import MAX_SPL_LLM_REPAIRS, attempt_bounded_utility_spl_llm_draft

_THREE_REPROS = (
    "one source IP attacking multiple distinct accounts over a rolling 10-minute window",
    "hourly failed-login trend over the last 24 hours",
    "password change followed by successful login within 5 minutes",
)
_ADJACENT = (
    "src ip targeting several different users across a sliding 8 minute window",
    "failed authentications per hour over the last 12 hours",
    "account lockout then a successful login inside 90 seconds",
    "find hosts spraying unique usernames inside a 15 minute rolling window",
    "plot a daily vpn connection-failure time series for the past 7 days",
    "privilege group change then successful login within 2 minutes",
)


def test_three_repros_and_adjacent_variants_compile_faithfully() -> None:
    for query in (*_THREE_REPROS, *_ADJACENT):
        spec = build_spl_intent_spec(query)
        assert spec["support_status"] == "supported"
        spl = compile_intent_spec_to_spl(spec)
        result = validate_semantic_fidelity(spec, spl)
        assert result["passed"] is True, (query, result["losses"], spl)


def test_failed_authentications_per_hour_is_failed_login_trend() -> None:
    spec = build_spl_intent_spec("failed authentications per hour over the last 12 hours")
    assert spec["analysis_shape"] == "trend"
    assert spec["temporal_grain"] == "1h"
    assert spec["search_horizon"] == "earliest=-12h latest=now"
    assert "failed_login" in spec["required_event_sets"]
    assert spec["search_horizon"] != "earliest=-24h latest=now"


def test_sliding_window_variant_does_not_invent_24h_horizon() -> None:
    spec = build_spl_intent_spec(
        "src ip targeting several different users across a sliding 8 minute window"
    )
    assert spec["analysis_shape"] == "rolling"
    assert spec["analytical_window"]["size"] == "8m"
    assert spec["search_horizon"] is None
    assert "user" in spec["distinct_by"]
    assert spec["entity_roles"]["subject"] == ["src_ip"]


def test_lockout_then_login_variant_preserves_gap() -> None:
    spec = build_spl_intent_spec("account lockout then a successful login inside 90 seconds")
    assert spec["analysis_shape"] == "sequence"
    assert spec["ordered_sequence"] == ["account_lockout", "successful_login"]
    assert spec["sequence_max_gap"] == "90s"


@pytest.mark.parametrize(
    ("query", "spl", "loss"),
    [
        (
            "src ip targeting several different users across a sliding 8 minute window",
            "search index=auth | stats count by src_ip | head 100",
            "rolling_window_missing",
        ),
        (
            "src ip targeting several different users across a sliding 8 minute window",
            "search index=auth | streamstats time_window=8m dc(user) as distinct_count by dest_ip",
            "wrong_grouping_entity",
        ),
        (
            "src ip targeting several different users across a sliding 8 minute window",
            "search index=auth | streamstats time_window=8m count as event_count by src_ip",
            "distinct_count_missing",
        ),
        (
            "failed authentications per hour over the last 12 hours",
            "search index=auth earliest=-12h latest=now | timechart span=1h count",
            "required_event_type_missing",
        ),
        (
            "account lockout then a successful login inside 90 seconds",
            "search index=auth (EventCode=4624) (EventCode=4740) | table _time",
            "sequence_ordering_missing",
        ),
        (
            "account lockout then a successful login inside 90 seconds",
            'search index=auth | eval event_type=if(EventCode=4740,"account_lockout",'
            '"successful_login") | sort 0 _time | streamstats current=f last(_time) as prev_time',
            "sequence_gap_missing",
        ),
        (
            "failed authentications per hour over the last 12 hours",
            "search index=auth earliest=-12h latest=now EventCode=4625 | timechart count",
            "time_bucket_missing",
        ),
        (
            "failed authentications per hour over the last 12 hours",
            "search index=auth earliest=-12h latest=now EventCode=4625 | stats count by user | head 100",
            "time_series_shape_missing",
        ),
        (
            "failed authentications per hour over the last 12 hours",
            "search index=auth earliest=-12h latest=now EventCode=4625 | timechart span=1h count | where count>50",
            "unexpected_threshold",
        ),
        (
            "src ip targeting several different users across a sliding 8 minute window",
            "search index=auth | eval user_norm=lower(coalesce(user,\"unknown\")) "
            "| streamstats time_window=8m count as event_count by src_ip",
            "normalized_field_unused",
        ),
        (
            "plot a daily vpn connection-failure time series for the past 7 days",
            "search index=vpn earliest=-7d latest=now | timechart span=1d count | head 100",
            "arbitrary_truncation",
        ),
    ],
)
def test_negative_loss_matrix(query: str, spl: str, loss: str) -> None:
    spec = build_spl_intent_spec(query)
    result = validate_semantic_fidelity(spec, spl)
    assert result["passed"] is False
    assert loss in result["losses"]


def test_malformed_structure_negative() -> None:
    errors = validate_spl_structure("search index=foo | eval x=\"hello\nworld\"")
    assert "broken_multiline_expression" in errors or "unbalanced_quotes" in errors


def test_more_than_one_repair_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    result, trace = attempt_bounded_utility_spl_llm_draft(
        "hourly failed-login trend over the last 24 hours",
        llm_raw_output_provider=lambda: "{}",
        context={"repair_attempt_count": 2},
        repair_attempt=True,
    )
    assert result is None
    assert trace["llm_spl_draft_dropped_reason"] == "more_than_one_repair"
    assert MAX_SPL_LLM_REPAIRS == 1
