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


def test_adapter_path_does_not_raise_attributeerror(monkeypatch) -> None:
    # Regression: the reasoner used adapted.ok / adapted.payload, which do not exist
    # on LLMAdapterResult (.accepted / .normalized_payload) — it crashed on every
    # live call. With a real LLM payload it must return cleanly, never raise.
    import app.llm.missing_evidence_reasoner as mer

    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    payload = '{"missing_evidence_analysis": ["Confirm MFA status to strengthen the conclusion."]}'
    monkeypatch.setattr(mer, "invoke_sidecar_role", lambda **_: (payload, False, "local_primary"))
    contract = AnswerContract(
        missing_evidence=["mfa_status"], hil_status="not_required", answer_mode="live_investigation",
    )
    result = run_missing_evidence_reasoner(contract=contract)  # must not raise
    assert result.llm_called is True
    assert isinstance(result.bullets, list)
