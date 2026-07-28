"""Unit tests for synthesis turn timing instrumentation (workstream E phase 1)."""

from __future__ import annotations

from app.synthesis.turn_timing import (
    RunKind,
    SynthesisPath,
    TurnOutcome,
    TurnTimingSession,
    benchmark_run_kind_override,
    finalize_turn_timing,
    record_canonical_planning_ms,
    record_synthesis_endpoint,
    sanitize_turn_timing_payload,
    synthesis_turn_timing_scope,
)


def test_finalize_turn_timing_computes_overhead() -> None:
    with synthesis_turn_timing_scope(run_kind=RunKind.COLD):
        record_canonical_planning_ms(5000)
        record_synthesis_endpoint(
            12000,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.COMPLETED,
            provider_label="stub",
        )
        payload = finalize_turn_timing()
    assert payload is not None
    segments = payload["segments_ms"]
    assert segments["canonical_planning"] == 5000
    assert segments["synthesis_endpoint"] == 12000
    assert segments["end_to_end"] >= 0
    assert segments["application_overhead"] >= 0
    assert payload["synthesis_path"] == "lab"
    assert payload["run_kind"] == "cold"


def test_sanitize_turn_timing_payload_drops_sensitive_keys() -> None:
    cleaned = sanitize_turn_timing_payload(
        {
            "segments_ms": {"end_to_end": 10},
            "user_query": "secret question",
            "prompt_text": "do not keep",
        }
    )
    assert "user_query" not in cleaned
    assert "prompt_text" not in cleaned
    assert cleaned["segments_ms"]["end_to_end"] == 10


def test_composer_path_overrides_lab_path() -> None:
    session = TurnTimingSession(run_kind=RunKind.WARM)
    session.record_synthesis_endpoint(
        1000,
        path=SynthesisPath.LAB,
        outcome=TurnOutcome.COMPLETED,
    )
    session.record_synthesis_endpoint(
        2000,
        path=SynthesisPath.COMPOSER,
        outcome=TurnOutcome.COMPLETED,
    )
    payload = session.finalize()
    assert payload["synthesis_path"] == "composer"
    assert payload["segments_ms"]["synthesis_endpoint"] == 3000


def test_benchmark_run_kind_override_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("AI_SOC_BENCHMARK_RUN_KIND", raising=False)
    assert benchmark_run_kind_override() is None
    monkeypatch.setenv("AI_SOC_BENCHMARK_RUN_KIND", "warm")
    assert benchmark_run_kind_override() is RunKind.WARM
