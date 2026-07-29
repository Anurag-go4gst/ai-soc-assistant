"""Timing attribution tests for turn_timing segments (workstream E measurement integrity)."""

from __future__ import annotations

import time

from app.synthesis.turn_timing import (
    RunKind,
    SynthesisPath,
    TurnOutcome,
    TurnTimingSession,
    finalize_turn_timing,
    mark_synthesis_skipped,
    record_canonical_planning_ms,
    record_synthesis_endpoint,
    synthesis_turn_timing_scope,
)


def test_synthesis_skipped_without_retrieval_records_no_endpoint_attempts() -> None:
    with synthesis_turn_timing_scope(run_kind=RunKind.COLD):
        record_canonical_planning_ms(50)
        mark_synthesis_skipped()
        payload = finalize_turn_timing()
    assert payload["synthesis_path"] == "skipped"
    assert payload["segments_ms"]["synthesis_endpoint"] is None
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 0


def test_synthesis_skipped_after_genuine_retrieval_closes_retrieval_only() -> None:
    session = TurnTimingSession()
    session.record_canonical_planning(40)
    session.begin_retrieval_spl_phase()
    time.sleep(0.02)
    session.close_retrieval_spl_phase()
    session.mark_synthesis_skipped()
    payload = session.finalize()
    retrieval = payload["segments_ms"]["retrieval_spl"]
    assert retrieval is not None
    assert retrieval >= 15
    assert payload["segments_ms"]["synthesis_endpoint"] is None


def test_primary_endpoint_success_sums_into_synthesis_endpoint() -> None:
    with synthesis_turn_timing_scope():
        record_canonical_planning_ms(10)
        record_synthesis_endpoint(
            1200,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.COMPLETED,
            provider_label="local_primary",
        )
        payload = finalize_turn_timing()
    assert payload["segments_ms"]["synthesis_endpoint"] == 1200
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 1
    assert payload["attribution_v2"]["endpoint_attempt_ms_total"] == 1200


def test_primary_timeout_then_failover_success_accumulates_attempts() -> None:
    with synthesis_turn_timing_scope():
        record_synthesis_endpoint(
            800,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.FALLBACK,
            fallback_used=True,
            endpoint_attempt_timeout=True,
        )
        record_synthesis_endpoint(
            400,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.COMPLETED,
            provider_label="foundation_sec_instruct_fallback",
        )
        payload = finalize_turn_timing()
    assert payload["segments_ms"]["synthesis_endpoint"] == 1200
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 2
    assert payload["attribution_v2"]["endpoint_attempt_timeout_count"] == 1


def test_governed_request_timeout_after_endpoint_timeouts() -> None:
    with synthesis_turn_timing_scope():
        record_synthesis_endpoint(
            90000,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.TIMEOUT,
            timeout_applied=True,
            fallback_used=True,
            governed_request_timeout=True,
            endpoint_attempt_timeout=True,
        )
        payload = finalize_turn_timing()
    assert payload["outcome"] == "timeout"
    assert payload["attribution_v2"]["governed_request_timeout"] is True
    assert payload["attribution_v2"]["endpoint_attempt_timeout_count"] == 1


def test_application_overhead_never_negative() -> None:
    session = TurnTimingSession()
    session.record_canonical_planning(100)
    session.record_synthesis_endpoint(
        50,
        path=SynthesisPath.COMPOSER,
        outcome=TurnOutcome.COMPLETED,
    )
    payload = session.finalize()
    assert payload["segments_ms"]["application_overhead"] >= 0


def test_finalize_includes_additive_attribution_v2_without_breaking_v1() -> None:
    with synthesis_turn_timing_scope():
        record_synthesis_endpoint(
            25,
            path=SynthesisPath.COMPOSER,
            outcome=TurnOutcome.COMPLETED,
        )
        payload = finalize_turn_timing()
    assert payload["schema_version"] == "1"
    assert payload["attribution_v2"]["schema_version"] == "1"
    assert "segments_ms" in payload


def test_sanitize_drops_sensitive_keys_from_attribution_payload() -> None:
    with synthesis_turn_timing_scope():
        record_synthesis_endpoint(
            10,
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.COMPLETED,
            provider_label="local_primary",
            model="test-model",
        )
        payload = finalize_turn_timing()
    text = str(payload).lower()
    assert "password" not in text
    assert "prompt" not in text
