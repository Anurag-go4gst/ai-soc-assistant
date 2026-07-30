"""Timing attribution tests for turn_timing segments (workstream E measurement integrity)."""

from __future__ import annotations

import time

import pytest
from unittest.mock import MagicMock

from app.evals.percentile_stats import percentile_summary
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError
from app.synthesis.turn_timing import (
    EndpointAttemptOutcome,
    RunKind,
    SynthesisPath,
    TurnOutcome,
    TurnTimingSession,
    close_dispatch_and_retrieval_phase,
    close_final_synthesis_phase,
    close_post_planning_pipeline_phase,
    finalize_turn_timing,
    mark_synthesis_skipped,
    record_canonical_planning_ms,
    record_endpoint_attempt,
    record_synthesis_endpoint,
    set_synthesis_path_outcome,
    synthesis_turn_timing_scope,
    validate_timing_payload_arithmetic,
)

# Legacy v1 consumer fixture: broad retrieval_spl closes at generating_answer.
V1_LEGACY_SEGMENTS_FIXTURE = {
    "canonical_planning": 5000,
    "retrieval_spl": 45000,
    "synthesis_endpoint": 90000,
    "application_overhead": 51000,
    "end_to_end": 200000,
}


def _session_with_v1_fixture_values() -> TurnTimingSession:
    session = TurnTimingSession()
    session.started_at = time.monotonic() - 200.0
    session.canonical_planning_ms = V1_LEGACY_SEGMENTS_FIXTURE["canonical_planning"]
    session.dispatch_and_retrieval_ms = 40000
    session.post_planning_pipeline_ms = 5000
    session.retrieval_spl_ms = V1_LEGACY_SEGMENTS_FIXTURE["retrieval_spl"]
    session.final_synthesis_ms = 85000
    session.finalization_ms = 10000
    session.record_endpoint_attempt(
        V1_LEGACY_SEGMENTS_FIXTURE["synthesis_endpoint"],
        outcome=EndpointAttemptOutcome.COMPLETED,
        provider_label="local_primary",
    )
    session.set_synthesis_path_outcome(
        path=SynthesisPath.LAB,
        outcome=TurnOutcome.COMPLETED,
        provider_label="local_primary",
    )
    return session


def test_v1_projection_matches_legacy_fixture_segments() -> None:
    payload = _session_with_v1_fixture_values().finalize()
    segments = payload["segments_ms"]
    assert segments["canonical_planning"] == V1_LEGACY_SEGMENTS_FIXTURE["canonical_planning"]
    assert segments["retrieval_spl"] == V1_LEGACY_SEGMENTS_FIXTURE["retrieval_spl"]
    assert segments["synthesis_endpoint"] == V1_LEGACY_SEGMENTS_FIXTURE["synthesis_endpoint"]
    assert segments["application_overhead"] >= 0
    assert segments["end_to_end"] >= 190000
    assert payload["schema_version"] == "1"
    assert "retrieval_spl" in segments
    assert "post_planning_pipeline" not in segments


def test_attribution_v2_has_accurately_named_phase_segments() -> None:
    payload = _session_with_v1_fixture_values().finalize()
    phases = payload["attribution_v2"]["phase_segments_ms"]
    assert set(phases) == {
        "dispatch_and_retrieval",
        "post_planning_pipeline",
        "final_synthesis",
        "finalization",
    }
    assert "retrieval_spl" not in phases
    boundaries = payload["attribution_v2"]["phase_boundaries"]
    assert "generating_answer" in boundaries["post_planning_pipeline"]
    assert "graph_node_context_finalize" in boundaries["dispatch_and_retrieval"]


def test_rp_and_imperative_phase_boundaries_document_both_runtimes() -> None:
    payload = _session_with_v1_fixture_values().finalize()
    dispatch_boundary = payload["attribution_v2"]["phase_boundaries"]["dispatch_and_retrieval"]
    assert "imperative" in dispatch_boundary
    assert "RP" in dispatch_boundary or "graph_node_context_finalize" in dispatch_boundary


def test_exclusive_phase_total_does_not_exceed_end_to_end() -> None:
    with synthesis_turn_timing_scope():
        record_canonical_planning_ms(5)
        close_dispatch_and_retrieval_phase()
        close_post_planning_pipeline_phase()
        record_endpoint_attempt(12, outcome=EndpointAttemptOutcome.COMPLETED)
        set_synthesis_path_outcome(path=SynthesisPath.LAB, outcome=TurnOutcome.COMPLETED)
        close_final_synthesis_phase()
        payload = finalize_turn_timing()
    v2 = payload["attribution_v2"]
    assert v2["exclusive_phase_total_ms"] <= payload["segments_ms"]["end_to_end"] + 5
    assert v2["timing_arithmetic_valid"] is True
    assert validate_timing_payload_arithmetic(payload)


def test_nested_endpoint_timing_not_double_subtracted_from_overhead() -> None:
    session = TurnTimingSession()
    session.started_at = time.monotonic() - 0.5
    session.canonical_planning_ms = 100
    session.dispatch_and_retrieval_ms = 50
    session.post_planning_pipeline_ms = 50
    session.retrieval_spl_ms = 100
    session.final_synthesis_ms = 200
    session.finalization_ms = 50
    session.record_endpoint_attempt(80, outcome=EndpointAttemptOutcome.COMPLETED)
    session.record_endpoint_attempt(20, outcome=EndpointAttemptOutcome.TIMEOUT, provider_label="failover")
    payload = session.finalize()
    e2e = payload["segments_ms"]["end_to_end"]
    exclusive = payload["attribution_v2"]["exclusive_phase_total_ms"]
    endpoint_total = payload["attribution_v2"]["endpoint_attempt_ms_total"]
    overhead_exclusive = payload["attribution_v2"]["application_overhead_exclusive_ms"]
    assert endpoint_total == 100
    assert overhead_exclusive == max(0, e2e - exclusive)
    assert overhead_exclusive != max(0, e2e - exclusive - endpoint_total)


def test_primary_timeout_then_failover_success_counts_two_attempts() -> None:
    with synthesis_turn_timing_scope():
        record_endpoint_attempt(
            800,
            outcome=EndpointAttemptOutcome.TIMEOUT,
            provider_label="local_primary",
        )
        record_endpoint_attempt(
            400,
            outcome=EndpointAttemptOutcome.COMPLETED,
            provider_label="foundation_sec_instruct_fallback",
        )
        set_synthesis_path_outcome(
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.COMPLETED,
            provider_label="foundation_sec_instruct_fallback",
        )
        payload = finalize_turn_timing()
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_count"] == 2
    assert v2["endpoint_attempt_timeout_count"] == 1
    assert v2["endpoint_attempt_ms_total"] == 1200
    assert payload["segments_ms"]["synthesis_endpoint"] == 1200


def test_primary_and_secondary_timeout_counts_both_attempts() -> None:
    with synthesis_turn_timing_scope():
        record_endpoint_attempt(
            90000,
            outcome=EndpointAttemptOutcome.TIMEOUT,
            provider_label="local_primary",
        )
        record_endpoint_attempt(
            90000,
            outcome=EndpointAttemptOutcome.TIMEOUT,
            provider_label="foundation_sec_instruct_fallback",
        )
        set_synthesis_path_outcome(
            path=SynthesisPath.LAB,
            outcome=TurnOutcome.TIMEOUT,
            timeout_applied=True,
            fallback_used=True,
            governed_request_timeout=True,
        )
        payload = finalize_turn_timing()
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_count"] == 2
    assert v2["endpoint_attempt_timeout_count"] == 2
    assert v2["endpoint_attempt_ms_total"] == 180000


def test_skipped_synthesis_records_zero_endpoint_attempts() -> None:
    with synthesis_turn_timing_scope(run_kind=RunKind.COLD):
        record_canonical_planning_ms(50)
        mark_synthesis_skipped()
        payload = finalize_turn_timing()
    assert payload["synthesis_path"] == "skipped"
    assert payload["segments_ms"]["synthesis_endpoint"] is None
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 0
    assert payload["attribution_v2"]["endpoint_attempt_ms_total"] == 0


def test_impossible_overlap_sets_timing_arithmetic_invalid() -> None:
    session = TurnTimingSession()
    session.started_at = time.monotonic() - 0.05
    session.canonical_planning_ms = 100_000
    payload = session.finalize()
    assert payload["attribution_v2"]["timing_arithmetic_valid"] is False
    assert validate_timing_payload_arithmetic(payload) is False


def test_percentiles_remain_bounded_by_min_max() -> None:
    values = [10, 20, 30, 40, 50]
    summary = percentile_summary(values)
    lo, hi = min(values), max(values)
    assert lo <= summary["p50"] <= hi
    assert lo <= summary["p90"] <= hi
    assert lo <= summary["p95"] <= hi


def test_synthesis_skipped_after_genuine_retrieval_closes_v1_retrieval_at_generating_answer() -> None:
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


def test_failover_client_records_per_hop_attempts_not_wrapper_only() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.base_url = "http://primary.example/v1"
    primary.model = "primary-model"
    primary.timeout_seconds = 60
    primary.generate.side_effect = LocalChatError("url_error:timeout")
    secondary = MagicMock(spec=LocalChatClient)
    secondary.base_url = "http://fallback.example/v1"
    secondary.model = "fallback-model"
    secondary.timeout_seconds = 60
    secondary.generate.return_value = ChatResult(
        text="ok",
        model="fallback-model",
        latency_ms=25,
        answered_label="foundation_sec_instruct_fallback",
    )
    with synthesis_turn_timing_scope():
        client = FailoverChatClient(
            chain=(
                ("local_primary", primary),
                ("foundation_sec_instruct_fallback", secondary),
            )
        )
        result = client.generate(
            system_prompt="sys",
            user_prompt="user",
            max_tokens=10,
            temperature=0.0,
        )
        payload = finalize_turn_timing()
    assert result.model == "fallback-model"
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_count"] == 2
    assert v2["endpoint_attempt_timeout_count"] == 1
    assert v2["endpoint_attempt_ms_total"] == sum(
        row["duration_ms"] for row in v2["endpoint_attempts"]
    )


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
    assert payload["attribution_v2"]["application_overhead_exclusive_ms"] >= 0


def test_finalize_includes_additive_attribution_v2_without_breaking_v1() -> None:
    with synthesis_turn_timing_scope():
        record_synthesis_endpoint(
            25,
            path=SynthesisPath.COMPOSER,
            outcome=TurnOutcome.COMPLETED,
        )
        payload = finalize_turn_timing()
    assert payload["schema_version"] == "1"
    assert payload["attribution_v2"]["schema_version"] == "3"
    assert "segments_ms" in payload


def test_finalize_freezes_endpoint_attempts_against_late_workers() -> None:
    session = TurnTimingSession()
    session.record_endpoint_attempt(10, outcome=EndpointAttemptOutcome.COMPLETED, call_purpose="routing")
    payload = session.finalize()
    session.record_endpoint_attempt(90_000, outcome=EndpointAttemptOutcome.TIMEOUT, call_purpose="shadow")
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 1
    assert len(payload["attribution_v2"]["endpoint_attempts"]) == 1


def test_endpoint_attempt_payload_includes_call_purpose_and_position() -> None:
    with synthesis_turn_timing_scope():
        record_endpoint_attempt(
            42,
            outcome=EndpointAttemptOutcome.TIMEOUT,
            provider_label="local_primary",
            model="foundation-sec-8b-instruct",
            call_purpose="synthesis_lab",
            candidate_position=1,
        )
        payload = finalize_turn_timing()
    attempt = payload["attribution_v2"]["endpoint_attempts"][0]
    assert attempt["call_purpose"] == "synthesis_lab"
    assert attempt["candidate_position"] == 1
    assert attempt["model"] == "foundation-sec-8b-instruct"
    assert attempt["timeout"] is True
    assert attempt["completed"] is False


def test_failover_client_suppresses_duplicate_timeout_retry() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.base_url = "http://llm.example/v1"
    primary.model = "same-model"
    primary.timeout_seconds = 60
    primary.adapter_type = "local_chat_client"
    primary.api_protocol = "openai_chat_completions"
    primary.api_key = ""
    primary.generate.side_effect = LocalChatError("url_error:timeout")
    duplicate = MagicMock(spec=LocalChatClient)
    duplicate.base_url = "http://llm.example/v1"
    duplicate.model = "same-model"
    duplicate.timeout_seconds = 60
    duplicate.adapter_type = "local_chat_client"
    duplicate.api_protocol = "openai_chat_completions"
    duplicate.api_key = ""
    duplicate.generate.return_value = ChatResult(
        text="ok",
        model="same-model",
        latency_ms=5,
        answered_label="foundation_sec_instruct_fallback",
    )
    with synthesis_turn_timing_scope():
        from app.llm.llm_call_context import CALL_PURPOSE_COMPOSER, llm_call_purpose_scope

        client = FailoverChatClient(
            chain=(
                ("local_primary", primary),
                ("local_primary", duplicate),
            )
        )
        with llm_call_purpose_scope(CALL_PURPOSE_COMPOSER):
            with pytest.raises(LocalChatError):
                client.generate(
                    system_prompt="sys",
                    user_prompt="user",
                    max_tokens=10,
                    temperature=0.0,
                    call_purpose=CALL_PURPOSE_COMPOSER,
                )
        payload = finalize_turn_timing()
    attempts = payload["attribution_v2"]["endpoint_attempts"]
    assert len(attempts) == 1
    assert payload["attribution_v2"]["suppressed_candidate_count"] == 1
    duplicate.generate.assert_not_called()


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
