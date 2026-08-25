"""S4 — semantic fidelity negatives and lightweight structural checks."""

from __future__ import annotations

from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity, validate_spl_structure


def _spec(query: str) -> dict:
    return build_spl_intent_spec(query)


def test_rolling_window_missing() -> None:
    spec = _spec("one source IP attacking multiple distinct accounts over a rolling 10-minute window")
    result = validate_semantic_fidelity(spec, "search index=auth | stats count by src_ip | head 100")
    assert result["passed"] is False
    assert "rolling_window_missing" in result["losses"]
    assert "distinct_count_missing" in result["losses"]
    assert "arbitrary_truncation" in result["losses"] or "arbitrary_head_100" in result["losses"]


def test_wrong_grouping_entity() -> None:
    spec = _spec("one source IP attacking multiple distinct accounts over a rolling 10-minute window")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth | streamstats time_window=10m dc(user) as distinct_count by dest_ip",
    )
    assert "wrong_grouping_entity" in result["losses"] or "group_by_src_ip" in result["losses"]


def test_required_event_type_missing() -> None:
    spec = _spec("hourly failed-login trend over the last 24 hours")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth earliest=-24h latest=now | timechart span=1h count",
    )
    assert "required_event_type_missing" in result["losses"]


def test_sequence_ordering_and_gap_missing() -> None:
    spec = _spec("password change followed by successful login within 5 minutes")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth (EventCode=4624) | stats count by user",
    )
    assert "sequence_ordering_missing" in result["losses"]
    assert "sequence_gap_missing" in result["losses"]


def test_time_bucket_and_series_missing() -> None:
    spec = _spec("hourly failed-login trend over the last 24 hours")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth action=failure earliest=-24h | stats count by user | head 100",
    )
    assert "time_series_shape_missing" in result["losses"]
    assert "time_bucket_missing" in result["losses"]


def test_unexpected_threshold() -> None:
    spec = _spec("hourly failed-login trend over the last 24 hours")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth action=failure earliest=-24h | timechart span=1h count | where count>50",
    )
    assert "unexpected_threshold" in result["losses"]


def test_normalized_field_unused() -> None:
    spec = _spec("one source IP attacking multiple distinct accounts over a rolling 10-minute window")
    result = validate_semantic_fidelity(
        spec,
        "search index=auth | eval user_norm=lower(coalesce(user,\"unknown\")) "
        "| streamstats time_window=10m count as event_count by src_ip",
    )
    assert "normalized_field_unused" in result["losses"]


def test_malformed_structure() -> None:
    errors = validate_spl_structure('search index=foo eval user=lower(coalesce(user, "x")')
    assert "unbalanced_parentheses" in errors or "unbalanced_quotes" in errors
    spec = _spec("show all firewall events last 7 days")
    result = validate_semantic_fidelity(spec, 'search index=foo | stats count by src_ip || head 10')
    assert "malformed_structure" in result["losses"]


def test_compiled_shapes_pass_fidelity() -> None:
    for query in (
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window",
        "hourly failed-login trend over the last 24 hours",
        "password change followed by successful login within 5 minutes",
    ):
        spec = _spec(query)
        spl = compile_intent_spec_to_spl(spec)
        result = validate_semantic_fidelity(spec, spl)
        assert result["passed"] is True, (query, result["losses"], spl)
