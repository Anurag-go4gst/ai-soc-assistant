"""TurnLlmBudget wall-clock deadline (C: bound stacked-sidecar latency)."""
from __future__ import annotations

import time

from app.llm.turn_llm_budget import TurnLlmBudget


def test_count_budget_still_enforced():
    b = TurnLlmBudget(max_sidecar_calls=2, deadline_seconds=0)  # time gate off
    assert b.sidecar_budget_exhausted() is False
    b.record_sidecar(role="x", provider_label=None, outcome="ok")
    b.record_sidecar(role="y", provider_label=None, outcome="ok")
    assert b.sidecar_budget_exhausted() is True


def test_time_deadline_exhausts_budget_even_with_calls_remaining():
    b = TurnLlmBudget(max_sidecar_calls=5, deadline_seconds=0.05)
    assert b.sidecar_budget_exhausted() is False  # fresh
    time.sleep(0.06)
    # No calls made, but the wall-clock deadline alone now blocks further LLM work.
    assert b.time_budget_exhausted() is True
    assert b.sidecar_budget_exhausted() is True
    assert b.narration_budget_exhausted() is True


def test_zero_deadline_disables_time_gate():
    b = TurnLlmBudget(max_sidecar_calls=5, deadline_seconds=0)
    time.sleep(0.02)
    assert b.time_budget_exhausted() is False
    assert b.sidecar_budget_exhausted() is False


def test_trace_dict_exposes_deadline_fields():
    b = TurnLlmBudget(deadline_seconds=75.0)
    trace = b.to_trace_dict()
    assert trace["deadline_seconds"] == 75.0
    assert "elapsed_seconds" in trace
    assert trace["time_budget_exhausted"] is False
    assert 0 < trace["remaining_seconds"] <= 75.0


def test_call_reserve_blocks_hop_before_deadline_is_fully_exhausted():
    # Wider deadline on a loaded VPS; 50ms total is too tight for sleep+jitter.
    b = TurnLlmBudget(deadline_seconds=0.20)
    assert b.can_start_call(reserve_seconds=0.01) is True
    time.sleep(0.08)
    assert b.time_budget_exhausted() is False
    assert b.can_start_call(reserve_seconds=0.15) is False


def test_call_reserve_is_disabled_with_zero_deadline():
    b = TurnLlmBudget(deadline_seconds=0)
    assert b.remaining_seconds() is None
    assert b.can_start_call(reserve_seconds=999) is True


def test_sidecar_hop_blocked_on_insufficient_reserve(monkeypatch):
    from app.llm.turn_llm_budget import TurnLlmBudget, hop_reserve_seconds

    monkeypatch.setattr("app.config.settings.ai_soc_llm_timeout_seconds", 30)
    b = TurnLlmBudget(max_sidecar_calls=5, deadline_seconds=0.20)
    time.sleep(0.10)
    role = "intent_shadow_classifier"
    assert b.sidecar_hop_blocked(role=role) == "insufficient_deadline_reserve"
    assert hop_reserve_seconds(role) == 30.0


def test_narration_hop_blocked_when_count_exhausted():
    b = TurnLlmBudget(max_narration_calls=1, deadline_seconds=0)
    b.record_narration(provider_label=None, outcome="ok")
    assert b.narration_hop_blocked() == "turn_budget_exhausted"


def test_record_sidecar_includes_deadline_remaining():
    b = TurnLlmBudget(deadline_seconds=75.0)
    b.record_sidecar(role="x", provider_label="p", outcome="completed", latency_ms=10)
    rec = b.records[-1]
    assert "deadline_remaining_seconds" in rec
    assert "reserve_seconds" in rec


def test_capped_hop_timeout_clamps_to_remaining(monkeypatch):
    from app.llm.turn_llm_budget import TurnLlmBudget

    monkeypatch.setattr("app.config.settings.ai_soc_llm_timeout_seconds", 120)
    b = TurnLlmBudget(deadline_seconds=0.25)
    import time
    time.sleep(0.12)
    capped = b.capped_hop_timeout_seconds(role="intent_shadow_classifier", min_seconds=0.05)
    assert capped is not None
    assert capped <= 0.14


def test_capped_hop_timeout_none_when_budget_exhausted():
    from app.llm.turn_llm_budget import TurnLlmBudget
    import time

    b = TurnLlmBudget(deadline_seconds=0.05)
    time.sleep(0.06)
    assert b.capped_hop_timeout_seconds(role="intent_shadow_classifier") is None


def test_composer_reserve_clamps_to_remaining():
    from app.llm.turn_llm_budget import TurnLlmBudget

    b = TurnLlmBudget(deadline_seconds=40.0)
    reserve = b.composer_reserve_seconds()
    assert 1.0 <= reserve <= 40.0
