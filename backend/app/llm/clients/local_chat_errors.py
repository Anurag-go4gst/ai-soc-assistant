"""User-facing messages for local/OpenAI-compatible LLM transport errors."""

from __future__ import annotations


def local_chat_error_code(exc: BaseException) -> str:
    if hasattr(exc, "code") and isinstance(getattr(exc, "code"), str):
        return str(exc.code)
    message = str(exc)
    if message.startswith("http_") or message.startswith("url_error"):
        return message.split(":", 1)[0]
    return "transport_error:Unknown"


def user_message_for_local_chat_error(code: str) -> str:
    if code == "base_url_not_configured":
        return "Live LLM synthesis is enabled but no model endpoint URL is configured."
    if code == "empty_completion":
        return "The LLM returned an empty completion."
    if code.startswith("http_"):
        status = code.removeprefix("http_")
        if status in {"502", "503", "504"}:
            return (
                f"The LLM server returned HTTP {status} (gateway/upstream unavailable). "
                "Check that llama.cpp or your OpenAI-compatible server is running."
            )
        if status in {"401", "403"}:
            return f"The LLM server rejected the request (HTTP {status}). Check API key and access settings."
        if status == "404":
            return "The LLM chat/completions URL was not found (HTTP 404). Check the base URL path."
        if status == "105":
            return (
                "The LLM endpoint returned HTTP 105. This usually means a proxy or upstream rejected "
                "the connection—verify the base URL, port, and that the model server is reachable from the backend."
            )
        return (
            f"The LLM server returned HTTP {status}. "
            "A governed deterministic answer will be used instead."
        )
    if code.startswith("url_error:"):
        reason = code.split(":", 1)[-1]
        if reason in {"ConnectionRefusedError", "ConnectionRefused"}:
            return (
                "Could not connect to the LLM server (connection refused). "
                "Confirm the host, port, and that llama.cpp is listening."
            )
        if reason in {"TimeoutError", "timed out"}:
            return "The LLM server did not respond in time. A governed deterministic answer will be used instead."
        if reason in {"NameResolutionError", "gaierror"}:
            return "Could not resolve the LLM hostname. Check DNS and the configured base URL."
        return f"Network error reaching the LLM server ({reason}). A deterministic answer will be used instead."
    if code.startswith("transport_error:"):
        detail = code.split(":", 1)[-1]
        return f"LLM request failed ({detail}). A governed deterministic answer will be used instead."
    return "Live LLM synthesis failed. A governed deterministic answer will be used instead."
