"""Resolve governed LLM endpoints: Qwen/local primary, Foundation-Sec instruct failover."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.llm.clients.endpoint_fingerprint import (
    ADAPTER_LOCAL_CHAT,
    API_PROTOCOL_OPENAI_CHAT,
    TRANSPORT_SIDECAR,
    TRANSPORT_SYNTHESIS,
    CandidateContractFingerprint,
    RequestContractFingerprint,
    candidate_fingerprint_from_client,
    candidates_equivalent,
)
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import LocalChatClient

REASONING_ROLES = frozenset(
    {
        "pattern_reasoner",
        "mitre_reasoner",
        "missing_evidence_reasoner",
        "risk_rationale_reasoner",
    }
)


@dataclass(frozen=True)
class ResolvedEndpoint:
    label: str
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int


def _configured(value: str) -> bool:
    return bool(value and str(value).strip())


# Socket-timeout ceiling for sidecar calls against a local single-slot model.
# Must be >= the sidecar wrapper timeouts in sidecar_clients._ROLE_TIMEOUT_SECONDS
# so the wrapper does not silently abandon a call the socket would have completed.
# A single-slot 8B instruct needs ~30-90s; the old 45s cap killed every sidecar.
# Three layers align: env AI_SOC_LLM_TIMEOUT_SECONDS -> socket ceiling -> wrapper.
SIDECAR_SOCKET_CEILING_SECONDS = 120


def _timeout_for_mode(mode: str, *, sidecar: bool = False) -> int:
    configured = max(int(settings.ai_soc_llm_timeout_seconds or 60), 60)
    if mode == "local":
        if sidecar:
            return min(configured, SIDECAR_SOCKET_CEILING_SECONDS)
        # Live synthesis / narration: honor configured env exactly (no silent 120s floor).
        return configured
    return min(configured, 120)


def resolve_qwen_primary_endpoint(*, sidecar: bool = False) -> ResolvedEndpoint | None:
    """COE Qwen — only when ``AI_SOC_LLM_QWEN_PRIMARY_ENABLED`` and QWEN_* are set."""
    if not settings.ai_soc_llm_qwen_primary_enabled:
        return None
    base_url = settings.ai_soc_llm_qwen_base_url.strip()
    model = settings.ai_soc_llm_qwen_model.strip()
    if not _configured(base_url) or not _configured(model):
        return None
    return ResolvedEndpoint(
        label="qwen_primary",
        base_url=base_url,
        model=model,
        api_key=settings.ai_soc_llm_qwen_api_key,
        timeout_seconds=_timeout_for_mode("local", sidecar=sidecar),
    )


def resolve_local_primary_endpoint(*, sidecar: bool = False) -> ResolvedEndpoint | None:
    """Local OpenAI-compatible endpoint via ``AI_SOC_LLM_LOCAL_*`` (dev Foundation-Sec)."""
    mode = settings.ai_soc_llm_mode.strip().lower()
    if mode in {"mock", "disabled", ""}:
        return None
    if mode == "local":
        base_url = settings.ai_soc_llm_local_base_url.strip()
        model = settings.ai_soc_llm_local_model.strip() or settings.ai_soc_llm_default_model.strip()
        api_key = settings.ai_soc_llm_local_api_key
    else:
        base_url = settings.ai_soc_llm_openai_base_url.strip()
        model = settings.ai_soc_llm_openai_model.strip() or settings.ai_soc_llm_default_model.strip()
        api_key = settings.ai_soc_llm_openai_api_key
    if not _configured(base_url) or not _configured(model):
        return None
    return ResolvedEndpoint(
        label="local_primary",
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=_timeout_for_mode(mode, sidecar=sidecar),
    )


def resolve_foundation_sec_instruct_endpoint(*, sidecar: bool = False) -> ResolvedEndpoint | None:
    """Security/SPL specialist failover — current production default when Qwen is down."""
    base_url = settings.ai_soc_llm_foundation_sec_instruct_base_url.strip()
    model = (
        settings.ai_soc_llm_foundation_sec_instruct_model.strip()
        or settings.ai_soc_llm_default_model.strip()
    )
    if not _configured(base_url) or not _configured(model):
        return None
    return ResolvedEndpoint(
        label="foundation_sec_instruct_fallback",
        base_url=base_url,
        model=model,
        api_key=settings.ai_soc_llm_foundation_sec_instruct_api_key,
        timeout_seconds=_timeout_for_mode("local", sidecar=sidecar),
    )


def resolve_foundation_sec_reasoning_endpoint(*, sidecar: bool = False) -> ResolvedEndpoint | None:
    base_url = settings.ai_soc_llm_foundation_sec_reasoning_base_url.strip()
    model = (
        settings.ai_soc_llm_foundation_sec_reasoning_model.strip()
        or settings.ai_soc_llm_default_model.strip()
    )
    if not _configured(base_url) or not _configured(model):
        return None
    return ResolvedEndpoint(
        label="foundation_sec_reasoning",
        base_url=base_url,
        model=model,
        api_key=settings.ai_soc_llm_foundation_sec_reasoning_api_key,
        timeout_seconds=_timeout_for_mode("local", sidecar=sidecar),
    )


def _client_from_endpoint(
    endpoint: ResolvedEndpoint,
    *,
    transport_mode: str,
) -> LocalChatClient:
    return LocalChatClient(
        base_url=endpoint.base_url,
        model=endpoint.model,
        api_key=endpoint.api_key,
        timeout_seconds=endpoint.timeout_seconds,
        adapter_type=ADAPTER_LOCAL_CHAT,
        api_protocol=API_PROTOCOL_OPENAI_CHAT,
    )


def _reference_fingerprint(
    endpoint: ResolvedEndpoint,
    *,
    transport_mode: str,
) -> CandidateContractFingerprint:
    client = _client_from_endpoint(endpoint, transport_mode=transport_mode)
    return candidate_fingerprint_from_client(
        client,
        provider_label=endpoint.label,
        transport_mode=transport_mode,
        request_contract=RequestContractFingerprint(
            call_purpose="chain_build",
            max_tokens=0,
            temperature=0.0,
            response_format_present=False,
            seed_present=False,
        ),
    )


def _append_endpoint(
    chain: list[tuple[str, LocalChatClient]],
    endpoint: ResolvedEndpoint,
    *,
    transport_mode: str,
    existing_fingerprints: list[CandidateContractFingerprint],
) -> None:
    candidate_fp = _reference_fingerprint(endpoint, transport_mode=transport_mode)
    for existing in existing_fingerprints:
        if candidates_equivalent(existing, candidate_fp):
            return
    chain.append((endpoint.label, _client_from_endpoint(endpoint, transport_mode=transport_mode)))
    existing_fingerprints.append(candidate_fp)


def build_failover_chat_client(
    *,
    role: str | None = None,
    sidecar: bool = False,
) -> FailoverChatClient | None:
    """Failover chain: optional Qwen (flag) → LOCAL → Foundation-Sec Instruct.

    Reasoning roles optionally prepend Foundation-Sec Reasoning when configured.
    When Qwen flag is off, behavior is unchanged (LOCAL / Instruct only).
    """
    chain: list[tuple[str, LocalChatClient]] = []
    transport_mode = TRANSPORT_SIDECAR if sidecar else TRANSPORT_SYNTHESIS
    build_fps: list[CandidateContractFingerprint] = []
    if role in REASONING_ROLES:
        reasoning = resolve_foundation_sec_reasoning_endpoint(sidecar=sidecar)
        if reasoning is not None:
            _append_endpoint(chain, reasoning, transport_mode=transport_mode, existing_fingerprints=build_fps)

    qwen = resolve_qwen_primary_endpoint(sidecar=sidecar)
    if qwen is not None:
        _append_endpoint(chain, qwen, transport_mode=transport_mode, existing_fingerprints=build_fps)

    primary = resolve_local_primary_endpoint(sidecar=sidecar)
    if primary is not None:
        _append_endpoint(chain, primary, transport_mode=transport_mode, existing_fingerprints=build_fps)

    fallback = resolve_foundation_sec_instruct_endpoint(sidecar=sidecar)
    if fallback is not None:
        _append_endpoint(chain, fallback, transport_mode=transport_mode, existing_fingerprints=build_fps)

    if not chain:
        return None
    return FailoverChatClient(chain=tuple(chain), transport_mode=transport_mode)


def build_synthesis_client_from_settings() -> FailoverChatClient | None:
    """Live-chat synthesis / narration client (optional Qwen → LOCAL → Instruct)."""
    return build_failover_chat_client(sidecar=False)
