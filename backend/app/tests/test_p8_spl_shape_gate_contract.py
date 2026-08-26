"""The compiled SPL for every semantic shape must survive its own downstream gates.

P8 L3 measured SPL at 1/5 and read it as a model limit. It was not: for the
rolling, trend and sequence shapes the deterministic compiler emitted SPL that
the deterministic gates behind it rejected, so no candidate ever reached
scoring and the model's detection plan was discarded unseen.

    rolling   draft_quality  SOC-STD-SPL-001-Q11  (`sort 0 _time`, not `sort 0 + _time`)
    sequence  draft_quality  SOC-STD-SPL-001-Q11  + validate_spl missing_aggregation
    trend     validate_spl   missing_result_limit

These pins keep the compiler honest against the gates rather than relaxing the
gates. Nothing here makes a candidate executable: execution eligibility is
asserted false below.
"""

from __future__ import annotations

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.draft_quality import evaluate_draft_quality
from app.spl.llm_plan_compiler import compile_plan_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import _DENIED_SPL_RE, validate_semantic_fidelity

# The frozen P8 L3 bank queries for the four shapes the compiler owns end to end.
SHAPE_QUERIES = {
    "rolling": "one source IP attacking multiple distinct accounts over a rolling 10-minute window",
    "trend": "hourly failed-login trend over the last 24 hours",
    "sequence": "password change followed by successful login within 5 minutes",
}

_NEUTRAL_PLAN = {
    "data_domain": "auth",
    "filters": [],
    "group_by": [],
    "metric": "count",
    "required_fields": [],
    "detection_family": "p8_shape_contract",
}


def _compile(query: str) -> tuple[dict, str]:
    spec = build_spl_intent_spec(query)
    return spec, compile_plan_to_spl(dict(_NEUTRAL_PLAN), intent_spec=spec)


# Rejections that mean "the compiler emitted a shape its own gates refuse".
# Index/sourcetype allowlisting is a deployment-binding concern, not a shape
# defect, and placeholders are expected when no source profile is configured.
SHAPE_DEFECT_REJECTS = frozenset({"missing_aggregation", "missing_result_limit"})


@pytest.mark.parametrize("shape", sorted(SHAPE_QUERIES))
def test_compiled_shape_is_not_rejected_by_its_own_gates(shape: str) -> None:
    spec, spl = _compile(SHAPE_QUERIES[shape])
    assert spec["analysis_shape"] == shape
    assert spl, f"{shape}: compiler produced no candidate"

    validation = validate_spl(spl)
    offending = SHAPE_DEFECT_REJECTS.intersection(validation["reject_reasons"])
    assert not offending, f"{shape}: {sorted(offending)}"

    quality = evaluate_draft_quality(spl)
    assert quality.hard_fail_count == 0, [
        finding
        for finding in quality.to_dict()["findings"]
        if finding.get("severity") == "hard_fail"
    ]

    fidelity = validate_semantic_fidelity(spec, spl)
    assert fidelity["losses"] == [], f"{shape}: {fidelity['losses']}"


@pytest.mark.parametrize("shape", sorted(SHAPE_QUERIES))
def test_compiled_shape_is_never_execution_eligible(shape: str) -> None:
    _, spl = _compile(SHAPE_QUERIES[shape])
    assert validate_spl(spl)["execution_eligible"] is False


def test_streamstats_shapes_use_the_explicit_ascending_sort() -> None:
    """Q11 accepts only `sort 0 + _time`, which is what the shapes must emit."""
    for shape in ("rolling", "sequence"):
        _, spl = _compile(SHAPE_QUERIES[shape])
        assert "streamstats" in spl
        assert "sort 0 + _time" in spl, shape


def test_trend_satisfies_result_limit_without_truncating_the_series() -> None:
    """The trend contract prohibits any head cap, so ordering carries the limit."""
    spec, spl = _compile(SHAPE_QUERIES["trend"])
    assert "arbitrary_truncation" in spec["prohibitions"]
    assert "| head" not in spl
    assert "sort 0 _time" in spl
    assert "missing_result_limit" not in validate_spl(spl)["reject_reasons"]


def test_non_predicate_filter_matches_are_dropped_not_compiled() -> None:
    """A planner writing "select everything" must not narrow the search to nothing.

    ``src_ip="*"`` is not a wildcard in a base search term — it matches the literal
    string. The prompt forbids these values; the compiler does not rely on that.
    """
    plan = {
        "data_domain": "auth",
        "group_by": ["src_ip"],
        "metric": "count",
        "detection_family": "junk_filters",
        "filters": [
            {"field": "src_ip", "match": "*"},
            {"field": "user", "match": "not null"},
            {"field": "host", "match": "any"},
            {"field": "action", "match": "failure"},
        ],
    }
    spl = compile_plan_to_spl(plan)
    assert 'action="failure"' in spl
    for dropped in ('src_ip="*"', 'user="not null"', 'host="any"'):
        assert dropped not in spl


def test_denied_filter_match_is_not_weakened_by_quote_tolerance() -> None:
    """Crediting action="denied" must not credit a query with no denied filter."""
    assert _DENIED_SPL_RE.search('action="denied"')
    assert _DENIED_SPL_RE.search("action=denied")
    assert not _DENIED_SPL_RE.search('action="allowed"')
    assert not _DENIED_SPL_RE.search("| stats count by src_ip")
