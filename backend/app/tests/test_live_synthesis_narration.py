"""Live-model narration of the analyst summary, exercised with a stub client so
the suite never makes a real HTTP call. Verifies: success replaces the summary
while facts stay deterministic; any client failure falls back to the
deterministic summary; the flag gates the model call entirely."""

from __future__ import annotations

import pytest

from app.actions.capability_policy import action_capability_for
from app.llm.clients import ChatResult, LocalChatError
from app.synthesis.lab_runner import run_governed_synthesis_lab
from app.tests.test_p6_guarded_synthesis_lab import (
    _source_evidence,
    _structured_context,
    _sufficiency_ready,
)


class _StubClient:
    def __init__(self, *, text: str = "", raises: bool = False, finish_reason: str | None = None) -> None:
        self._text = text
        self._raises = raises
        self._finish_reason = finish_reason
        self.calls = 0

    def generate(self, *, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float, **kwargs: object) -> ChatResult:
        self.calls += 1
        if self._raises:
            raise LocalChatError("transport_error:Boom")
        return ChatResult(
            text=self._text,
            model="stub-model",
            latency_ms=1234,
            usage={"total_tokens": 7},
            finish_reason=self._finish_reason,
        )


def _run(monkeypatch: pytest.MonkeyPatch, *, live: bool, client) -> object:
    for attr, value in (
        ("ai_soc_llm_final_synthesis_enabled", True),
        ("ai_soc_llm_live_synthesis_enabled", live),
        ("ai_soc_llm_require_context_sufficiency", True),
    ):
        monkeypatch.setattr(f"app.synthesis.lab_runner.settings.{attr}", value)
    return run_governed_synthesis_lab(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        context_sufficiency=_sufficiency_ready(),
        mitre_mappings=[],
        action_capability=action_capability_for("attack_discovery", "P2 - High"),
        severity_label="P2 - High",
        spl_validation=None,
        human_review=None,
        synthesis_client=client,
    )


def test_live_narration_replaces_summary_and_keeps_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _StubClient(text="Repeated failed logins indicate a brute-force attempt; review the source IPs.")
    result = _run(monkeypatch, live=True, client=client)

    assert client.calls == 1
    assert result.status.provider == "local_model"
    assert result.status.model == "stub-model"
    assert result.status.latency_ms == 1234
    assert result.analyst_summary == "Repeated failed logins indicate a brute-force attempt; review the source IPs."
    assert result.draft["analyst_summary"] == result.analyst_summary
    assert result.draft["draft_source"] == "live_model"
    # Facts stay deterministic authority.
    assert result.draft["execution_eligible"] is False
    assert result.draft["severity_label"] == "P2 - High"


def test_live_narration_sanitizes_reasoning_preamble(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _StubClient(
        text=(
            "<think>private chain</think>\n"
            "The user is asking about failed logins.\n\n"
            "Repeated failed logins require analyst review."
        )
    )
    result = _run(monkeypatch, live=True, client=client)

    assert result.analyst_summary == "Repeated failed logins require analyst review."
    assert "<think>" not in result.analyst_summary
    assert "The user is asking" not in result.analyst_summary


def test_live_narration_length_finish_reason_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _StubClient(text="Partial analyst prose", finish_reason="length")
    result = _run(monkeypatch, live=True, client=client)

    assert client.calls == 1
    assert result.status.status == "degraded"
    assert result.status.provider == "deterministic_lab"
    assert "live_narration_truncated" in result.status.reason
    assert result.draft["draft_source"] == "deterministic_lab"


def test_live_narration_failure_falls_back_to_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _StubClient(raises=True)
    result = _run(monkeypatch, live=True, client=client)

    assert client.calls == 1
    assert result.status.status == "degraded"
    assert result.status.provider == "deterministic_lab"
    assert "transport_error" in result.status.reason
    assert result.draft["draft_source"] == "deterministic_lab"
    assert result.analyst_summary  # deterministic summary retained


def test_live_flag_off_never_calls_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _StubClient(text="should not be used")
    result = _run(monkeypatch, live=False, client=client)

    assert client.calls == 0
    assert result.status.provider == "deterministic_lab"
    assert result.draft["draft_source"] == "deterministic_lab"
