from __future__ import annotations

from app.api import routes_llm_lab as lab
from app.llm.sidecar_clients import SidecarInvocationResult


def test_llm_lab_sanitizes_answer_and_reports_finish_reason(monkeypatch) -> None:
    monkeypatch.setattr(lab, "_llm_available", lambda: True)
    monkeypatch.setattr(
        lab,
        "invoke_sidecar_role_with_metadata",
        lambda **_: SidecarInvocationResult(
            raw_output="<think>hidden</think>\nThe user is asking for a summary.\n\nCollect MFA status.",
            timed_out=False,
            answered_label="local_primary",
            finish_reason="length",
        ),
    )

    result = lab.llm_lab_ask(lab.LlmLabAskRequest(prompt="summarize"), _user={"sub": "test"})

    assert result["answer"] == "Collect MFA status."
    assert result["provider"] == "local_primary"
    assert result["finish_reason"] == "length"
    assert "response_may_be_incomplete" in result["warnings"]
    assert "removed_think_block" in result["sanitizer_notes"]
