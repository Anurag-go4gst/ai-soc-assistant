"""Try primary local (Qwen) then Foundation-Sec Instruct on transport/HTTP failures."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError

logger = logging.getLogger(__name__)


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
    ) -> ChatResult:
        if not self.chain:
            raise LocalChatError("no_llm_endpoint_configured")
        last_error: LocalChatError | None = None
        for label, client in self.chain:
            try:
                result = client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=response_format,
                )
                if label != self.chain[0][0]:
                    logger.info("llm_failover succeeded on %s", label)
                return ChatResult(
                    text=result.text,
                    model=result.model,
                    latency_ms=result.latency_ms,
                    usage=result.usage,
                    answered_label=label,
                )
            except LocalChatError as exc:
                last_error = exc
                logger.warning("llm_failover attempt failed label=%s code=%s", label, exc.code)
                continue
        raise last_error or LocalChatError("all_failover_endpoints_failed")
