"""S3 — compiler and postprocessor preserve temporal/normalization dependencies."""

from __future__ import annotations

from app.spl.llm_plan_compiler import compile_intent_spec_to_spl, compile_plan_to_spl
from app.spl.review_only_spl_postprocessor import normalize_review_only_spl
from app.spl.spl_intent_spec import build_spl_intent_spec


def test_rolling_compile_preserves_window_and_distinct() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "streamstats time_window=10m" in spl
    assert "dc(user_norm)" in spl or "dc(user)" in spl
    assert "by src_ip_norm" in spl or "by src_ip" in spl
    assert "head 100" not in spl
    assert "user_norm=" in spl
    assert "src_ip_norm=" in spl


def test_trend_compile_preserves_grain_and_horizon() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    spl = compile_intent_spec_to_spl(spec)
    assert "earliest=-24h" in spl
    assert "timechart span=1h" in spl
    assert "failed" in spl.lower() or "4625" in spl
    assert "head 100" not in spl


def test_sequence_compile_preserves_order_and_gap() -> None:
    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "password_change" in spl
    assert "successful_login" in spl
    # SOC-STD-SPL-001-Q11 requires the explicit `sort 0 + _time` form before
    # streamstats; the bare `sort 0 _time` is the same sort but hard-fails the lint.
    assert "sort 0 + _time" in spl
    assert "300" in spl or "maxspan=5m" in spl
    assert "head 100" not in spl


def test_comparison_compile_fails_closed() -> None:
    spec = build_spl_intent_spec("is this the same campaign as last month")
    assert compile_intent_spec_to_spl(spec) == ""


def test_legacy_plan_compile_unchanged_without_spec() -> None:
    plan = {
        "detection_family": "ot_modbus_unauthorized_write",
        "data_domain": "ot_network",
        "time_window_hours": 24,
        "filters": [{"field": "protocol", "match": "modbus"}],
        "group_by": ["src_ip", "dest_ip"],
        "metric": "count",
    }
    spl = compile_plan_to_spl(plan)
    assert spl.rstrip().endswith("head 100")
    assert "| stats count as event_count" in spl


def test_postprocessor_does_not_overwrite_explicit_horizon() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    spl = "search index=<your_index> earliest=-24h latest=now | timechart span=1h count"
    out = normalize_review_only_spl(
        spl,
        {
            "is_explicit_spl_authoring": True,
            "is_universal_spl": False,
            "semantic_analyst_intent": spec,
        },
    )
    assert "earliest=-24h" in out.normalized_spl
    assert "earliest=-24h" in (out.trace.get("final_earliest") or "earliest=-24h")


def test_postprocessor_keeps_streamstats_order() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype>\n"
        "| sort 0 _time\n"
        "| streamstats time_window=10m dc(user_norm) as distinct_count by src_ip_norm"
    )
    out = normalize_review_only_spl(
        spl,
        {
            "is_explicit_spl_authoring": True,
            "is_universal_spl": False,
            "semantic_analyst_intent": spec,
        },
    )
    assert "streamstats time_window=10m" in out.normalized_spl
    assert "sort 0 _time" in out.normalized_spl


def test_normalization_alias_is_consumed() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "user_norm=" in spl
    assert "dc(user_norm)" in spl
