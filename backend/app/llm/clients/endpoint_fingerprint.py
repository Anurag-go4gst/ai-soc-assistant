"""Sanitized candidate-contract fingerprints for failover deduplication (workstream E).

Never stores URLs, tokens, credentials, or raw configuration in telemetry.
If any contract component is unknown, equivalence cannot be proven and both
candidates must be retained.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

API_PROTOCOL_OPENAI_CHAT = "openai_chat_completions"
ADAPTER_LOCAL_CHAT = "local_chat_client"
TRANSPORT_SIDECAR = "sidecar"
TRANSPORT_SYNTHESIS = "synthesis"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class RequestContractFingerprint:
    """Bounded request contract — excludes prompt text and credentials."""

    call_purpose: str
    max_tokens: int
    temperature: float
    response_format_present: bool
    seed_present: bool

    @classmethod
    def from_generate_kwargs(
        cls,
        *,
        call_purpose: str | None,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        seed: int | None = None,
    ) -> RequestContractFingerprint:
        return cls(
            call_purpose=str(call_purpose or "other"),
            max_tokens=int(max_tokens),
            temperature=round(float(temperature), 4),
            response_format_present=response_format is not None,
            seed_present=seed is not None,
        )


@dataclass(frozen=True)
class CandidateContractFingerprint:
    """All fields that can make two failover candidates operationally distinct."""

    endpoint_identity: str
    model: str
    api_protocol: str
    adapter_type: str
    config_identity: str
    auth_source_label: str
    transport_mode: str
    request_contract: RequestContractFingerprint

    @property
    def is_fully_known(self) -> bool:
        return UNKNOWN not in {
            self.endpoint_identity,
            self.model,
            self.api_protocol,
            self.adapter_type,
            self.config_identity,
            self.auth_source_label,
            self.transport_mode,
        }

    def equivalence_key(self) -> tuple[Any, ...]:
        """Hashable key for within-chain duplicate detection."""
        return (
            self.endpoint_identity,
            self.model,
            self.api_protocol,
            self.adapter_type,
            self.config_identity,
            self.auth_source_label,
            self.transport_mode,
            self.request_contract.call_purpose,
            self.request_contract.max_tokens,
            self.request_contract.temperature,
            self.request_contract.response_format_present,
            self.request_contract.seed_present,
        )


def normalized_endpoint_identity(base_url: str) -> str:
    """Stable non-secret endpoint label (host + optional path prefix hash)."""
    raw = str(base_url or "").strip()
    if not raw:
        return UNKNOWN
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if not host:
        return UNKNOWN
    path = (parsed.path or "").rstrip("/").lower()
    if path in {"", "/v1", "/v1/chat"}:
        material = host
    else:
        material = f"{host}:{path}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"ep_{digest}"


def auth_source_label(*, api_key: str, provider_label: str) -> str:
    """Non-secret stable auth-source identity."""
    if api_key and str(api_key).strip():
        return f"bearer_cfg:{provider_label or 'anonymous'}"
    return "auth_none"


def candidate_fingerprint_from_client(
    client: object,
    *,
    provider_label: str,
    transport_mode: str,
    request_contract: RequestContractFingerprint,
) -> CandidateContractFingerprint:
    base_url = str(getattr(client, "base_url", "") or "")
    model = str(getattr(client, "model", "") or "").strip().lower()
    api_key = str(getattr(client, "api_key", "") or "")
    adapter_type = str(getattr(client, "adapter_type", ADAPTER_LOCAL_CHAT) or ADAPTER_LOCAL_CHAT)
    api_protocol = str(getattr(client, "api_protocol", API_PROTOCOL_OPENAI_CHAT) or API_PROTOCOL_OPENAI_CHAT)
    return CandidateContractFingerprint(
        endpoint_identity=normalized_endpoint_identity(base_url),
        model=model or UNKNOWN,
        api_protocol=api_protocol or UNKNOWN,
        adapter_type=adapter_type or UNKNOWN,
        config_identity=str(provider_label or UNKNOWN),
        auth_source_label=auth_source_label(api_key=api_key, provider_label=provider_label),
        transport_mode=transport_mode or UNKNOWN,
        request_contract=request_contract,
    )


def candidates_equivalent(
    left: CandidateContractFingerprint,
    right: CandidateContractFingerprint,
) -> bool:
    """True only when every contract component is known and identical."""
    if not left.is_fully_known or not right.is_fully_known:
        return False
    return left.equivalence_key() == right.equivalence_key()
