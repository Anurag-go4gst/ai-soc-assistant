"""Tests for bounded linear percentile summaries (workstream E)."""

from __future__ import annotations

import pytest

from app.evals.percentile_stats import linear_percentile, percentile_summary

E5_RUN3_E2E = [181753, 737, 180940, 20478, 181144, 181046]
E5_RUN3_SYNTHESIS = [0, 90093]
E5_RUN3_WARM_E2E = [737, 20478]


def test_empty_samples_returns_null_percentiles() -> None:
    assert percentile_summary([]) == {"p50": None, "p90": None, "p95": None}


def test_one_sample_percentiles_equal_sample() -> None:
    assert percentile_summary([42]) == {"p50": 42, "p90": 42, "p95": 42}


def test_two_sample_percentiles_bounded() -> None:
    summary = percentile_summary([10, 30])
    assert summary["p50"] == 20
    assert summary["p90"] >= 10
    assert summary["p95"] <= 30


def test_six_sample_e5_run3_end_to_end_percentiles() -> None:
    summary = percentile_summary(E5_RUN3_E2E)
    assert summary["p50"] == 180993
    assert summary["p90"] == 181448
    assert summary["p95"] == 181600


def test_synthesis_endpoint_e5_run3_subset() -> None:
    summary = percentile_summary(E5_RUN3_SYNTHESIS)
    assert summary["p50"] == 45046
    assert summary["p90"] == 81083
    assert summary["p95"] == 85588


def test_warm_end_to_end_e5_run3_subset() -> None:
    summary = percentile_summary(E5_RUN3_WARM_E2E)
    assert summary["p50"] == 10607
    assert summary["p90"] == 18503
    assert summary["p95"] == 19490


def test_unsorted_input_matches_sorted() -> None:
    shuffled = list(reversed(E5_RUN3_E2E))
    assert percentile_summary(shuffled) == percentile_summary(E5_RUN3_E2E)


def test_percentiles_never_below_min_or_above_max() -> None:
    samples = [100, 200, 300, 400, 500, 600]
    ordered = sorted(samples)
    summary = percentile_summary(samples)
    for key in ("p50", "p90", "p95"):
        value = summary[key]
        assert value is not None
        assert ordered[0] <= value <= ordered[-1]


def test_p50_p90_p95_monotonic_ordering() -> None:
    summary = percentile_summary(E5_RUN3_E2E)
    assert summary["p50"] <= summary["p90"] <= summary["p95"]


def test_linear_percentile_rejects_empty() -> None:
    with pytest.raises(ValueError):
        linear_percentile([], 0.5)
