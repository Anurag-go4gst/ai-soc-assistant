from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.missing_evidence_reasoner import run_missing_evidence_reasoner


def test_missing_evidence_reasoner_skips_without_context(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    contract = AnswerContract(missing_evidence=[], hil_status="not_required")
    result = run_missing_evidence_reasoner(contract=contract)
    assert result.skipped_reason == "no_missing_evidence_context"
    assert result.bullets == []


def test_missing_evidence_reasoner_skips_clarification_hil(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    contract = AnswerContract(
        missing_evidence=["auth_telemetry"],
        hil_status="clarification_required",
        answer_mode="clarification",
    )
    result = run_missing_evidence_reasoner(contract=contract)
    assert result.skipped_reason in {
        "hil_skip:clarification_required",
        "t0_answer_mode:clarification",
    }
    assert result.llm_called is False


def test_missing_evidence_reasoner_skips_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", False)
    contract = AnswerContract(missing_evidence=["auth_telemetry"], hil_status="missing_evidence_review")
    result = run_missing_evidence_reasoner(contract=contract)
    assert result.skipped_reason == "llm_disabled"
