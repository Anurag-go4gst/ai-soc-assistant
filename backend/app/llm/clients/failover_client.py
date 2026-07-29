"""Try primary local (Qwen) then Foundation-Sec Instruct on transport/HTTP failures."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass

from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError
from app.synthesis.narration_deadline import hop_timeout_seconds, should_attempt_hop

logger = logging.getLogger(__name__)

# Per-`generate` capability cache keyed by the bound method's underlying function.
# Child clients duck-type `generate` with no formal Protocol, so we negotiate which
# optional kwargs each hop accepts once (cheap signature inspection) and reuse it.
_CAPABILITY_CACHE: dict[object, frozenset[str]] = {}

# Optional kwargs that a hop may or may not accept. Required kwargs
# (system_prompt/user_prompt/max_tokens/temperature) are always forwarded.
_NEGOTIABLE_KWARGS: tuple[str, ...] = ("seed", "response_format")


def _supported_kwargs(generate_callable: object) -> frozenset[str]:
    """Return the subset of negotiable kwargs the child's `generate` accepts.

    Inspected once per underlying function and cached. A hop whose signature
    declares ``**kwargs`` is treated as accepting every negotiable kwarg.
    """
    key = getattr(generate_callable, "__func__", generate_callable)
    cached = _CAPABILITY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        signature = inspect.signature(generate_callable)
    except (TypeError, ValueError):
        # Cannot introspect (builtin / C callable) — be conservative and forward
        # nothing optional rather than risk a TypeError on an unknown signature.
        supported: frozenset[str] = frozenset()
        _CAPABILITY_CACHE[key] = supported
        return supported
    has_var_keyword = any(
        param.kind is inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    if has_var_keyword:
        supported = frozenset(_NEGOTIABLE_KWARGS)
    else:
        supported = frozenset(
            name for name in _NEGOTIABLE_KWARGS if name in signature.parameters
        )
    _CAPABILITY_CACHE[key] = supported
    return supported


@dataclass(frozen=True)
class FailoverChatClient:
    chain: tuple[tuple[str, LocalChatClient], ...]

    @property
    def base_url(self) -> str:
        return self.chain[0][1].base_url if self.chain else ""

    @property
    def model(self) -> str:
        return self.chain[0][1].model if self.chain else ""

    @property
    def timeout_seconds(self) -> int:
        return self.chain[0][1].timeout_seconds if self.chain else 60

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        seed: int | None = None,
        deadline: float | None = None,
    ) -> ChatResult:
        if not self.chain:
            raise LocalChatError("no_llm_endpoint_configured")
        last_error: LocalChatError | None = None
        for label, client in self.chain:
            if not should_attempt_hop(deadline):
                break
            per_hop_timeout = hop_timeout_seconds(client.timeout_seconds, deadline)
            if deadline is not None and per_hop_timeout is None:
                break
            # Negotiate optional kwargs per hop: a child whose `generate` lacks
            # `seed` (or `response_format`) must not receive it, or it raises
            # TypeError instead of running. Required kwargs always pass through.
            supported = _supported_kwargs(client.generate)
            optional_kwargs: dict[str, object] = {}
            if "seed" in supported:
                optional_kwargs["seed"] = seed
            if "response_format" in supported:
                optional_kwargs["response_format"] = response_format
            try:
                result = client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_seconds=per_hop_timeout,
                    **optional_kwargs,
                )
                if label != self.chain[0][0]:
                    logger.info("llm_failover succeeded on %s", label)
                return ChatResult(
                    text=result.text,
                    model=result.model,
                    latency_ms=result.latency_ms,
                    usage=result.usage,
                    answered_label=label,
                    finish_reason=result.finish_reason,
                )
            except LocalChatError as exc:
                last_error = exc
                logger.warning("llm_failover attempt failed label=%s code=%s", label, exc.code)
                continue
        raise last_error or LocalChatError("all_failover_endpoints_failed")
