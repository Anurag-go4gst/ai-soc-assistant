from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient
from app.llm.sidecar_clients import invoke_sidecar_role


def test_primary_timeout_falls_to_instruct(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.sidecar_clients.settings.ai_soc_llm_enabled", True)
    monkeypatch.setattr("app.llm.sidecar_clients.settings.ai_soc_llm_mode", "local")

    def slow_primary(**kwargs):  # noqa: ANN003
        time.sleep(2.0)
        return ChatResult(text='{"ok": true}', model="qwen", latency_ms=10, answered_label="local_primary")

    primary = MagicMock(spec=LocalChatClient)
    primary.generate.side_effect = slow_primary

    secondary = MagicMock(spec=LocalChatClient)
    secondary.generate.return_value = ChatResult(
        text='{"missing_evidence_analysis": ["need more logs"]}',
        model="instruct",
        latency_ms=5,
        answered_label="foundation_sec_instruct_fallback",
    )

    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )

    with patch("app.llm.sidecar_clients.build_failover_client_for_role", return_value=client):
        raw, timed_out, label = invoke_sidecar_role(
            role="missing_evidence_reasoner",
            user_prompt="test",
            timeout_seconds=0.5,
        )

    assert timed_out is False
    assert raw is not None
    assert label == "foundation_sec_instruct_fallback"
    primary.generate.assert_called_once()
    secondary.generate.assert_called_once()


def test_both_timeout_returns_timed_out(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.sidecar_clients.settings.ai_soc_llm_enabled", True)
    monkeypatch.setattr("app.llm.sidecar_clients.settings.ai_soc_llm_mode", "local")

    def slow(**kwargs):  # noqa: ANN003
        time.sleep(2.0)
        return ChatResult(text="late", model="m", latency_ms=1, answered_label="local_primary")

    primary = MagicMock(spec=LocalChatClient)
    primary.generate.side_effect = slow
    secondary = MagicMock(spec=LocalChatClient)
    secondary.generate.side_effect = slow
    client = FailoverChatClient(
        chain=(
            ("local_primary", primary),
            ("foundation_sec_instruct_fallback", secondary),
        )
    )

    with patch("app.llm.sidecar_clients.build_failover_client_for_role", return_value=client):
        raw, timed_out, label = invoke_sidecar_role(
            role="missing_evidence_reasoner",
            user_prompt="test",
            timeout_seconds=0.3,
        )

    assert timed_out is True
    assert raw is None
