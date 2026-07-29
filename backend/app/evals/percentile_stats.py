"""Bounded linear percentiles for exploratory benchmark summaries (workstream E).

Uses Hyndman & Fan type-7 (linear) interpolation so every reported percentile
lies within ``[min(samples), max(samples)]``.
"""

from __future__ import annotations


def linear_percentile(sorted_values: list[int], quantile: float) -> int:
    """Return an integer percentile from a **sorted** sample (type-7 / linear)."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("linear_percentile requires at least one sample")
    if n == 1:
        return sorted_values[0]
    q = float(quantile)
    if q <= 0.0:
        return sorted_values[0]
    if q >= 1.0:
        return sorted_values[-1]
    pos = (n - 1) * q
    lower = int(pos)
    upper = min(lower + 1, n - 1)
    frac = pos - lower
    interpolated = sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])
    return int(interpolated)


def percentile_summary(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"p50": None, "p90": None, "p95": None}
    ordered = sorted(values)
    return {
        "p50": linear_percentile(ordered, 0.5),
        "p90": linear_percentile(ordered, 0.9),
        "p95": linear_percentile(ordered, 0.95),
    }
