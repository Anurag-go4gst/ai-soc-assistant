"""Minimal OpenAI-compatible chat client for an on-prem llama.cpp / local model.

Used only by the live-chat synthesis narration. Stdlib-only (urllib) to avoid a
new dependency, mirroring the verification helpers in `routes_settings`. Unlike
those helpers it does NOT clamp the timeout to 30s, because a local single-slot
model generates at single-digit tokens/sec and a real synthesis answer needs
longer than the connectivity smoke.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


class LocalChatError(RuntimeError):
    """Raised on any failure to obtain a completion. Callers fall back to the
    deterministic draft; this never propagates to the chat response."""


@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)


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
    ) -> ChatResult:
        if not self.base_url.strip():
            raise LocalChatError("base_url_not_configured")
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = "Bearer " + self.api_key.strip()
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
        ).encode("utf-8")
        request = Request(url, data=body, method="POST", headers=headers)
        started = time.monotonic()
        try:
            with urlopen(request, timeout=max(self.timeout_seconds, 1)) as response:  # noqa: S310 - admin-configured on-prem endpoint.
                raw = response.read(1024 * 256)
        except HTTPError as exc:
            raise LocalChatError(f"http_{exc.code}") from exc
        except URLError as exc:
            raise LocalChatError(f"url_error:{type(getattr(exc, 'reason', exc)).__name__}") from exc
        except Exception as exc:  # noqa: BLE001 - any transport failure must fall back, never raise to chat.
            raise LocalChatError(f"transport_error:{type(exc).__name__}") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        text, usage = _parse_completion(raw)
        if not text:
            raise LocalChatError("empty_completion")
        return ChatResult(text=text, model=self.model, latency_ms=elapsed_ms, usage=usage)


def _parse_completion(raw: bytes) -> tuple[str, dict[str, int]]:
    if not raw:
        return "", {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "", {}
    if not isinstance(data, dict):
        return "", {}
    text = ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
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
    return text, usage


def build_synthesis_client_from_settings() -> LocalChatClient | None:
    """Construct a client from governed config, or None when live synthesis is
    not eligible (mock/disabled mode, or no endpoint configured)."""
    mode = settings.ai_soc_llm_mode.strip().lower()
    if mode in {"mock", "disabled", ""}:
        return None
    base_url = (
        settings.ai_soc_llm_local_base_url
        if mode == "local"
        else settings.ai_soc_llm_openai_base_url
    ).strip()
    model = (
        settings.ai_soc_llm_local_model
        if mode == "local"
        else settings.ai_soc_llm_openai_model
    ).strip() or settings.ai_soc_llm_default_model.strip()
    api_key = (
        settings.ai_soc_llm_local_api_key
        if mode == "local"
        else settings.ai_soc_llm_openai_api_key
    )
    if not base_url or not model:
        return None
    return LocalChatClient(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=settings.ai_soc_llm_timeout_seconds,
    )
