"""Unit tests for live synthesis benchmark harness (workstream E phase 1)."""

from __future__ import annotations

from app.evals.live_synthesis_benchmark import (
    estimate_live_probe_cost,
    parse_probe_matrix,
    run_stub_benchmark,
    summarize_benchmark,
)


def test_stub_benchmark_produces_sanitized_summary() -> None:
    report = run_stub_benchmark()
    payload = report.to_sanitized_dict()
    assert payload["mode"] == "stub"
    assert payload["evidence_class"] == "stub_deterministic_not_measured"
    assert payload["run_count"] == len(parse_probe_matrix())
    assert payload["summary"]["sample_count"] == payload["run_count"]
    assert "end_to_end_ms" in payload["summary"]
    assert "synthesis_path_counts" in payload["summary"]
    for row in payload["runs"]:
        assert "turn_timing" in row
        assert "schema_version" in row["turn_timing"]
        assert "segments_ms" in row["turn_timing"]


def test_estimate_live_probe_cost_is_heuristic() -> None:
    cost = estimate_live_probe_cost()
    assert cost["probe_count"] == 6
    assert cost["estimated_runtime_minutes"] > 0
    assert "note" in cost


def test_summarize_benchmark_handles_empty_runs() -> None:
    from app.evals.live_synthesis_benchmark import BenchmarkReport

    summary = summarize_benchmark(BenchmarkReport())
    assert summary["end_to_end_ms"]["p50"] is None
    assert summary["timeout_rate"] is None
