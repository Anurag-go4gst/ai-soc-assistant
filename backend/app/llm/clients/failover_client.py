"""Try primary local (Qwen) then Foundation-Sec Instruct on transport/HTTP failures."""

from __future__ import annotations

import inspect
import logging
import time
from dataclasses import dataclass

from app.llm.clients.endpoint_fingerprint import (
    TRANSPORT_SIDECAR,
    TRANSPORT_SYNTHESIS,
    CandidateContractFingerprint,
    RequestContractFingerprint,
    candidate_fingerprint_from_client,
    candidates_equivalent,
)
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError
from app.llm.llm_call_context import get_call_purpose
from app.synthesis.narration_deadline import hop_timeout_seconds, should_attempt_hop
from app.synthesis.turn_timing import (
    EndpointAttemptOutcome,
    get_turn_timing_session,
    record_endpoint_attempt,
    record_suppressed_candidate,
)

logger = logging.getLogger(__name__)

_CAPABILITY_CACHE: dict[object, frozenset[str]] = {}
_NEGOTIABLE_KWARGS: tuple[str, ...] = ("seed", "response_format")


def _supported_kwargs(generate_callable: object) -> frozenset[str]:
    key = getattr(generate_callable, "__func__", generate_callable)
    cached = _CAPABILITY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        signature = inspect.signature(generate_callable)
    except (TypeError, ValueError):
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
    transport_mode: str = TRANSPORT_SYNTHESIS

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
        call_purpose: str | None = None,
    ) -> ChatResult:
        if not self.chain:
            raise LocalChatError("no_llm_endpoint_configured")
        last_error: LocalChatError | None = None
        purpose = call_purpose or get_call_purpose()
        request_contract = RequestContractFingerprint.from_generate_kwargs(
            call_purpose=purpose,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            seed=seed,
        )
        timed_out_fingerprints: set[tuple] = set()
        for position, (label, client) in enumerate(self.chain, start=1):
            candidate_fp = candidate_fingerprint_from_client(
                client,
                provider_label=label,
                transport_mode=self.transport_mode,
                request_contract=request_contract,
            )
            equiv_key = candidate_fp.equivalence_key()
            if equiv_key in timed_out_fingerprints:
                record_suppressed_candidate()
                logger.info(
                    "llm_failover suppressed duplicate timeout retry label=%s position=%s",
                    label,
                    position,
                )
                continue
            if not should_attempt_hop(deadline):
                break
            per_hop_timeout = hop_timeout_seconds(client.timeout_seconds, deadline)
            if deadline is not None and per_hop_timeout is None:
                break
            hop_started = time.monotonic()
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
                hop_ms = int((time.monotonic() - hop_started) * 1000)
                if get_turn_timing_session() is not None:
                    record_endpoint_attempt(
                        hop_ms,
                        outcome=EndpointAttemptOutcome.COMPLETED,
                        provider_label=label,
                        model=result.model or candidate_fp.model or None,
                        call_purpose=purpose,
                        candidate_position=position,
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
                hop_ms = int((time.monotonic() - hop_started) * 1000)
                if get_turn_timing_session() is not None:
                    code = str(exc.code).lower()
                    attempt_outcome = (
                        EndpointAttemptOutcome.TIMEOUT
                        if "timeout" in code
                        else EndpointAttemptOutcome.FALLBACK
                    )
                    record_endpoint_attempt(
                        hop_ms,
                        outcome=attempt_outcome,
                        provider_label=label,
                        model=candidate_fp.model or None,
                        call_purpose=purpose,
                        candidate_position=position,
                    )
                last_error = exc
                logger.warning("llm_failover attempt failed label=%s code=%s", label, exc.code)
                if "timeout" in str(exc.code).lower():
                    timed_out_fingerprints.add(equiv_key)
                if not should_attempt_hop(deadline):
                    break
                continue
        raise last_error or LocalChatError("all_failover_endpoints_failed")


def chain_has_equivalent_candidates(
    chain: tuple[tuple[str, LocalChatClient], ...],
    *,
    transport_mode: str,
) -> bool:
    """Return True when two chain entries are provably equivalent at build time."""
    fingerprints: list[CandidateContractFingerprint] = []
    reference_contract = RequestContractFingerprint(
        call_purpose="chain_build",
        max_tokens=0,
        temperature=0.0,
        response_format_present=False,
        seed_present=False,
    )
    for label, client in chain:
        fp = candidate_fingerprint_from_client(
            client,
            provider_label=label,
            transport_mode=transport_mode,
            request_contract=reference_contract,
        )
        for existing in fingerprints:
            if candidates_equivalent(existing, fp):
                return True
        fingerprints.append(fp)
    return False
