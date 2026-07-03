from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.llm.missing_evidence_reasoner import run_missing_evidence_reasoner
from app.llm.sidecar_clients import SidecarInvocationResult


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
    monkeypatch.setattr(
        mer,
        "invoke_sidecar_role_with_metadata",
        lambda **_: SidecarInvocationResult(payload, False, "local_primary"),
    )
    contract = AnswerContract(
        missing_evidence=["mfa_status"], hil_status="not_required", answer_mode="live_investigation",
    )
    result = run_missing_evidence_reasoner(contract=contract)  # must not raise
    assert result.llm_called is True
    assert isinstance(result.bullets, list)


def test_missing_evidence_bullets_are_sanitized(monkeypatch) -> None:
    import app.llm.missing_evidence_reasoner as mer

    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    payload = (
        '{"reasoning_summary": "review only", '
        '"missing_evidence_analysis": ["<think>hidden</think>The user is asking about MFA.\\n\\n'
        'Confirm MFA status before escalating."]}'
    )
    monkeypatch.setattr(
        mer,
        "invoke_sidecar_role_with_metadata",
        lambda **_: SidecarInvocationResult(payload, False, "local_primary", "stop"),
    )
    contract = AnswerContract(
        missing_evidence=["mfa_status"], hil_status="not_required", answer_mode="live_investigation",
    )

    result = run_missing_evidence_reasoner(contract=contract)

    assert result.bullets == ["Confirm MFA status before escalating."]
    assert result.finish_reason == "stop"
    assert "removed_think_block" in result.sanitizer_notes


def test_missing_evidence_length_finish_reason_rejects_partial_json(monkeypatch) -> None:
    import app.llm.missing_evidence_reasoner as mer

    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(
        mer,
        "invoke_sidecar_role_with_metadata",
        lambda **_: SidecarInvocationResult(
            '{"missing_evidence_analysis": ["partial"]',
            False,
            "local_primary",
            "length",
        ),
    )
    contract = AnswerContract(
        missing_evidence=["mfa_status"], hil_status="not_required", answer_mode="live_investigation",
    )

    result = run_missing_evidence_reasoner(contract=contract)

    assert result.bullets == []
    assert result.skipped_reason == "llm_finish_reason=length"
    assert result.finish_reason == "length"
