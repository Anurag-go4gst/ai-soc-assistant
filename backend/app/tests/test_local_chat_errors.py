from __future__ import annotations

from app.llm.clients.local_chat_errors import local_chat_error_code, user_message_for_local_chat_error


def test_http_105_message_is_actionable() -> None:
    message = user_message_for_local_chat_error("http_105")
    assert "HTTP 105" in message
    assert "reachable" in message.lower() or "proxy" in message.lower()


def test_local_chat_error_code_never_returns_unknown() -> None:
    code = local_chat_error_code(RuntimeError("something broke"))
    assert "Unknown" not in code
    assert code.startswith("unexpected:")


def test_connection_refused_message() -> None:
    message = user_message_for_local_chat_error("url_error:ConnectionRefusedError")
    assert "connection refused" in message.lower()
