"""Phase 5 — LLM role scorecard aggregation + verdict logic."""

from __future__ import annotations

from app.quality.llm_role_scorecard import (
    VERDICT_DEGRADED,
    VERDICT_HEALTHY,
    VERDICT_INSUFFICIENT,
    aggregate_role_metrics,
    build_llm_role_scorecard,
)


def _budget_trace(*, role: str, provider_label: str, outcome: str = "completed") -> dict:
    return {
        "llm_turn_budget": {
            "records": [
                {"kind": "sidecar", "role": role, "provider_label": provider_label, "outcome": outcome}
            ]
        }
    }


def test_healthy_role_all_primary() -> None:
    traces = [_budget_trace(role="intent_shadow_classifier", provider_label="local_primary") for _ in range(25)]
    card = build_llm_role_scorecard(traces)
    role = card["roles"]["intent_shadow_classifier"]
    assert role["invocations"] == 25
    assert role["fallback_rate"] == 0.0
    assert role["verdict"] == VERDICT_HEALTHY
    assert card["overall_verdict"] == VERDICT_HEALTHY


def test_insufficient_data_below_min_sample() -> None:
    traces = [_budget_trace(role="missing_evidence_reasoner", provider_label="local_primary") for _ in range(5)]
    card = build_llm_role_scorecard(traces)
    assert card["roles"]["missing_evidence_reasoner"]["verdict"] == VERDICT_INSUFFICIENT
    assert card["overall_verdict"] == VERDICT_INSUFFICIENT


def test_degraded_on_high_fallback_rate() -> None:
    traces = [
        _budget_trace(role="intent_shadow_classifier", provider_label="foundation_sec_instruct_fallback")
        for _ in range(6)
    ] + [
        _budget_trace(role="intent_shadow_classifier", provider_label="local_primary") for _ in range(19)
    ]
    metrics = aggregate_role_metrics(traces)["intent_shadow_classifier"]
    assert metrics.invocations == 25
    assert metrics.fallbacks == 6
    assert metrics.fallback_rate >= 0.10
    assert metrics.verdict() == VERDICT_DEGRADED


def test_degraded_on_low_agreement() -> None:
    # 25 invocations, 10 timeouts → agreement 0.6 < 0.70.
    traces = [
        _budget_trace(role="intent_shadow_classifier", provider_label="local_primary", outcome="timed_out")
        for _ in range(10)
    ] + [
        _budget_trace(role="intent_shadow_classifier", provider_label="local_primary") for _ in range(15)
    ]
    metrics = aggregate_role_metrics(traces)["intent_shadow_classifier"]
    assert metrics.agreement_rate < 0.70
    assert metrics.verdict() == VERDICT_DEGRADED


def test_composer_narration_counted_and_fallback() -> None:
    # Real shape: composer trace is nested under control_plane_trace["llm_composer"].
    traces = [
        {
            "llm_composer": {
                "llm_composer_used": True,
                "llm_guard_status": "passed",
                "llm_provider_label": "foundation_sec_instruct_fallback",
            }
        }
        for _ in range(20)
    ]
    card = build_llm_role_scorecard(traces)
    role = card["roles"]["narration_composer"]
    assert role["invocations"] == 20
    assert role["fallbacks"] == 20
    assert role["verdict"] == VERDICT_DEGRADED


def test_composer_guard_blocked_is_disagreement() -> None:
    traces = [
        {
            "llm_composer": {
                "llm_composer_used": False,
                "llm_guard_status": "blocked",
                "llm_blocked_reason": "ungrounded_ip",
            }
        }
        for _ in range(20)
    ]
    metrics = aggregate_role_metrics(traces)["narration_composer"]
    assert metrics.invocations == 20
    assert metrics.disagreements == 20
    assert "ungrounded_ip" in metrics.disagreement_reasons


def test_intent_adjudication_disagreement_signal() -> None:
    traces = []
    for _ in range(25):
        t = _budget_trace(role="intent_shadow_classifier", provider_label="local_primary")
        t["llm_intent_advisory"] = {"llm_called": True, "adjudication_status": "rejected", "adjudication_reason": "not_in_registry"}
        traces.append(t)
    metrics = aggregate_role_metrics(traces)["intent_shadow_classifier"]
    assert metrics.disagreements == 25
    assert metrics.agreement_rate == 0.0
    assert metrics.verdict() == VERDICT_DEGRADED


def test_empty_corpus_is_insufficient() -> None:
    card = build_llm_role_scorecard([])
    assert card["overall_verdict"] == VERDICT_INSUFFICIENT
    assert card["roles"] == {}


def test_aggregates_real_pipeline_trace_shape(monkeypatch) -> None:
    # Regression guard: the scorecard must parse the ACTUAL control_plane_trace the
    # pipeline emits (composer nested under "llm_composer"), not a hand-rolled shape.
    from app.config import settings
    from app.schemas.requests import ChatRequest
    from app.chat.pipeline import build_live_chat_response

    response = build_live_chat_response(
        ChatRequest(message="show failed login spike last hour", session_id="scorecard-it")
    )
    trace = response.model_dump().get("control_plane_trace") or {}
    assert "llm_composer" in trace and "llm_turn_budget" in trace
    # Must not raise on the real shape; budget records drive invocation counts.
    metrics = aggregate_role_metrics([trace])
    assert isinstance(metrics, dict)
