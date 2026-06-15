from __future__ import annotations

from app.llm.turn_llm_budget import TurnLlmBudget


def test_third_sidecar_skipped() -> None:
    budget = TurnLlmBudget()
    budget.record_sidecar(role="intent_shadow_classifier", provider_label="local_primary", outcome="completed")
    budget.record_sidecar(role="missing_evidence_reasoner", provider_label="local_primary", outcome="completed")

    assert budget.sidecar_budget_exhausted() is True


def test_narration_budget() -> None:
    budget = TurnLlmBudget()
    budget.record_narration(provider_label="local_primary", outcome="completed")

    assert budget.narration_budget_exhausted() is True


def test_record_narration_updates_trace() -> None:
    budget = TurnLlmBudget()
    budget.record_narration(provider_label="foundation_sec_instruct_fallback", outcome="completed")
    trace = budget.to_trace_dict()

    assert trace["narration_calls"] == 1
    assert trace["records"][-1]["kind"] == "narration"
