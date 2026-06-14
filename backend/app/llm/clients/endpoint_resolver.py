"""Resolve governed LLM endpoints: Qwen/local primary, Foundation-Sec instruct failover."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
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


def _timeout_for_mode(mode: str, *, sidecar: bool = False) -> int:
    configured = max(int(settings.ai_soc_llm_timeout_seconds or 60), 60)
    if mode == "local":
        return min(configured, 45) if sidecar else max(configured, 120)
    return min(configured, 90)


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


def _client_from_endpoint(endpoint: ResolvedEndpoint) -> LocalChatClient:
    return LocalChatClient(
        base_url=endpoint.base_url,
        model=endpoint.model,
        api_key=endpoint.api_key,
        timeout_seconds=endpoint.timeout_seconds,
    )


def _append_endpoint(
    chain: list[tuple[str, LocalChatClient]],
    endpoint: ResolvedEndpoint,
) -> None:
    normalized = endpoint.base_url.rstrip("/")
    if any(client.base_url.rstrip("/") == normalized for _, client in chain):
        return
    chain.append((endpoint.label, _client_from_endpoint(endpoint)))


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
    if role in REASONING_ROLES:
        reasoning = resolve_foundation_sec_reasoning_endpoint(sidecar=sidecar)
        if reasoning is not None:
            _append_endpoint(chain, reasoning)

    qwen = resolve_qwen_primary_endpoint(sidecar=sidecar)
    if qwen is not None:
        _append_endpoint(chain, qwen)

    primary = resolve_local_primary_endpoint(sidecar=sidecar)
    if primary is not None:
        _append_endpoint(chain, primary)

    fallback = resolve_foundation_sec_instruct_endpoint(sidecar=sidecar)
    if fallback is not None:
        _append_endpoint(chain, fallback)

    if not chain:
        return None
    return FailoverChatClient(chain=tuple(chain))


def build_synthesis_client_from_settings() -> FailoverChatClient | None:
    """Live-chat synthesis / narration client (optional Qwen → LOCAL → Instruct)."""
    return build_failover_chat_client(sidecar=False)
