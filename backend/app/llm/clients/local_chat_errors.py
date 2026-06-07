"""User-facing messages for local/OpenAI-compatible LLM transport errors."""

from __future__ import annotations


def local_chat_error_code(exc: BaseException) -> str:
    code_attr = getattr(exc, "code", None)
    if isinstance(code_attr, str) and code_attr:
        return code_attr
    name = type(exc).__name__ or "Exception"
    text = str(exc).strip().replace("\n", " ")[:120]
    if text.startswith(("http_", "url_error:", "transport_error:", "api_error:", "empty_completion")):
        return text.split()[0] if text.split() else f"unexpected:{name}"
    if text:
        return f"unexpected:{name}:{text}"
    return f"unexpected:{name}"


def user_message_for_local_chat_error(code: str) -> str:
    if code == "base_url_not_configured":
        return "Live LLM synthesis is enabled but no model endpoint URL is configured."
    if code == "empty_completion":
        return "The LLM returned an empty completion (check model name and server logs)."
    if code.startswith("api_error:"):
        detail = code.split(":", 1)[-1].strip()
        return f"The LLM API returned an error: {detail}. A governed deterministic answer will be used instead."
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
        lowered = reason.lower()
        if "refused" in lowered or reason in {"ConnectionRefusedError", "ConnectionRefused"}:
            return (
                "Could not connect to the LLM server (connection refused). "
                "Confirm the host, port, and that llama.cpp is listening."
            )
        if "timeout" in lowered or reason in {"TimeoutError", "timed out", "timeout"}:
            return (
                "The LLM server did not respond in time. "
                "The local model may still be loading or the request is too large—a governed deterministic answer will be used instead."
            )
        if "gaierror" in lowered or "name or service not known" in lowered:
            return "Could not resolve the LLM hostname. Check DNS and the configured base URL."
        return f"Network error reaching the LLM server ({reason}). A deterministic answer will be used instead."
    if code.startswith("transport_error:"):
        detail = code.split(":", 1)[-1]
        return f"LLM request failed ({detail}). A governed deterministic answer will be used instead."
    if code.startswith("unexpected:"):
        detail = code.removeprefix("unexpected:")
        return f"LLM request failed ({detail}). A governed deterministic answer will be used instead."
    return "Live LLM synthesis failed. A governed deterministic answer will be used instead."
