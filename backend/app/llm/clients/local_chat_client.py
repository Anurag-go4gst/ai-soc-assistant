"""Minimal OpenAI-compatible chat client for an on-prem llama.cpp / local model.

Used only by the live-chat synthesis narration. Stdlib-only (urllib) to avoid a
new dependency, mirroring the verification helpers in `routes_settings`. Unlike
those helpers it does NOT clamp the timeout to 30s, because a local single-slot
model generates at single-digit tokens/sec and a real synthesis answer needs
longer than the connectivity smoke.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.llm.clients.local_chat_errors import user_message_for_local_chat_error

logger = logging.getLogger(__name__)


class LocalChatError(RuntimeError):
    """Raised on any failure to obtain a completion. Callers fall back to the
    deterministic draft; this never propagates to the chat response."""

    def __init__(self, code: str, *, detail: str | None = None) -> None:
        self.code = code
        super().__init__(detail or code)

    @property
    def user_message(self) -> str:
        return user_message_for_local_chat_error(self.code)


@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)
    answered_label: str = ""
    finish_reason: str | None = None


def _url_error_code(exc: URLError) -> str:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, BaseException):
        return f"url_error:{type(reason).__name__}"
    if reason is not None:
        text = str(reason).strip().replace("\n", " ")[:80]
        return f"url_error:{text}" if text else "url_error:URLError"
    return "url_error:URLError"


def _read_http_error_body(exc: HTTPError, limit: int = 512) -> str:
    try:
        raw = exc.read(limit)
        if not raw:
            return ""
        return raw.decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        return ""


def _parse_completion(raw: bytes) -> tuple[str, dict[str, int], str | None]:
    if not raw:
        return "", {}, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        snippet = raw[:200].decode("utf-8", errors="replace")
        raise LocalChatError(
            "api_error:invalid_json",
            detail=f"non-JSON response ({type(exc).__name__}): {snippet[:120]}",
        ) from exc
    if not isinstance(data, dict):
        return "", {}, None
    error_block = data.get("error")
    if error_block is not None:
        if isinstance(error_block, dict):
            message = str(error_block.get("message") or error_block.get("type") or error_block)
        else:
            message = str(error_block)
        message = message.strip().replace("\n", " ")[:200]
        raise LocalChatError(f"api_error:{message or 'unknown_api_error'}")
    text = ""
    choices = data.get("choices")
    finish_reason = None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        raw_finish = choices[0].get("finish_reason")
        if raw_finish is not None:
            finish_reason = str(raw_finish)
        message = choices[0].get("message")
        if isinstance(message, dict):
            text = str(message.get("content") or "").strip()
        if not text:
            text = str(choices[0].get("text") or "").strip()
    usage: dict[str, int] = {}
    usage_raw = data.get("usage")
    if isinstance(usage_raw, dict):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage_raw.get(key)
            if isinstance(value, int):
                usage[key] = value
    return text, usage, finish_reason


@dataclass(frozen=True)
class LocalChatClient:
    """One blocking, non-streaming chat/completions call per `generate`."""

    base_url: str
    model: str
    api_key: str = ""
    timeout_seconds: int = 60

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        seed: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatResult:
        if not self.base_url.strip():
            raise LocalChatError("base_url_not_configured")
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = "Bearer " + self.api_key.strip()
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        # Fixed seed makes generation repeatable (temperature=0 alone does not on
        # llama.cpp without a seed) — required for byte-stable SPL diagnostics.
        if seed is not None:
            payload["seed"] = seed
        # OpenAI-compatible structured-output hint (e.g. {"type": "json_object"});
        # forces valid JSON on llama.cpp servers that support it.
        if response_format is not None:
            payload["response_format"] = response_format
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method="POST", headers=headers)
        started = time.monotonic()
        effective_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        try:
            with urlopen(request, timeout=max(float(effective_timeout), 0.05)) as response:  # noqa: S310
                raw = response.read(1024 * 256)
        except HTTPError as exc:
            body = _read_http_error_body(exc)
            code = f"http_{exc.code}"
            detail = f"HTTP {exc.code}"
            if body:
                detail = f"{detail}: {body[:200]}"
            logger.warning("local_chat http error %s url=%s body=%s", exc.code, url, body[:200])
            raise LocalChatError(code, detail=detail) from exc
        except URLError as exc:
            code = _url_error_code(exc)
            logger.warning("local_chat url error code=%s url=%s", code, url)
            raise LocalChatError(code) from exc
        except socket.timeout as exc:
            raise LocalChatError("url_error:timeout") from exc
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__ or "Exception"
            logger.warning("local_chat transport error %s url=%s", name, url)
            raise LocalChatError(f"transport_error:{name}") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        text, usage, finish_reason = _parse_completion(raw)
        if not text:
            raise LocalChatError("empty_completion")
        return ChatResult(
            text=text,
            model=self.model,
            latency_ms=elapsed_ms,
            usage=usage,
            finish_reason=finish_reason,
        )


def build_synthesis_client_from_settings():
    """Construct a failover client (Qwen/local primary, Foundation-Sec instruct fallback).

    Implemented in ``endpoint_resolver``; re-exported here for backward compatibility.
    """
    from app.llm.clients.endpoint_resolver import build_synthesis_client_from_settings as _build

    return _build()
