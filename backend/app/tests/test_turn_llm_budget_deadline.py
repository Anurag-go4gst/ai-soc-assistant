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
