from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError


def test_failover_client_uses_secondary_when_primary_raises() -> None:
    calls: list[str] = []

    primary = MagicMock(spec=LocalChatClient)
    primary.generate.side_effect = LocalChatError("http_503")

    def secondary_ok(**kwargs):  # noqa: ANN003
        calls.append("secondary")
        return ChatResult(
            text='{"ok": true}',
            model="instruct",
            latency_ms=10,
            answered_label="foundation_sec_instruct_fallback",
        )

    secondary = MagicMock(spec=LocalChatClient)
    secondary.generate.side_effect = secondary_ok

    client = FailoverChatClient(chain=(("local_primary", primary), ("foundation_sec_instruct_fallback", secondary)))
    result = client.generate(
        system_prompt="sys",
        user_prompt="user",
        max_tokens=50,
        temperature=0.0,
    )
    assert result.text == '{"ok": true}'
    assert result.answered_label == "foundation_sec_instruct_fallback"
    assert calls == ["secondary"]
    primary.generate.assert_called_once()
    secondary.generate.assert_called_once()


def test_answered_label_primary() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.generate.return_value = ChatResult(
        text='{"ok": true}',
        model="qwen",
        latency_ms=5,
        answered_label="local_primary",
    )
    client = FailoverChatClient(chain=(("local_primary", primary),))
    result = client.generate(system_prompt="s", user_prompt="u", max_tokens=1, temperature=0.0)
    assert result.answered_label == "local_primary"


def test_failover_client_raises_when_all_endpoints_fail() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.generate.side_effect = LocalChatError("connection_refused")
    client = FailoverChatClient(chain=(("local_primary", primary),))
    with pytest.raises(LocalChatError):
        client.generate(system_prompt="s", user_prompt="u", max_tokens=1, temperature=0.0)
