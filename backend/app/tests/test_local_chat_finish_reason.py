from __future__ import annotations

import json

from app.llm.clients.local_chat_client import _parse_completion


def test_parse_completion_captures_finish_reason() -> None:
    raw = json.dumps(
        {
            "choices": [{"message": {"content": "done"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        }
    ).encode("utf-8")

    text, usage, finish_reason = _parse_completion(raw)

    assert text == "done"
    assert usage["total_tokens"] == 7
    assert finish_reason == "length"
