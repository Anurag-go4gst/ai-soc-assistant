"""Direct-LLM lab endpoint.

A deliberately *ungoverned* text-in/text-out probe of the on-prem model, kept
isolated from the governed SOC `/chat` answer pipeline. It never touches MCP,
RAG, SourceEvidence, or any deterministic authority layer — it exists so an
operator can sanity-check raw model behaviour. Every response is stamped with an
honesty disclaimer; the model output here is NOT a SOC answer.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.session import require_auth
from app.config import settings
from app.llm.clients.endpoint_resolver import build_failover_chat_client
from app.llm.sidecar_clients import invoke_sidecar_role

router = APIRouter()

# Dedicated role label: keeps the lab traffic separable from the governed
# sidecar roles in telemetry. Unknown to PROMPT_CONTRACTS on purpose so it does
# not inherit a JSON-only contract — the lab is free-form prose.
LAB_ROLE = "llm_lab_direct"

# VPS 8B instruct is single-slot and slow (~30-120s/call) and the shared host
# adds CPU-steal bursts on top; give the lab generous headroom over the 15s
# sidecar default so a legitimate answer is not cut off mid-generation.
LAB_TIMEOUT_SECONDS = 180.0

LAB_SYSTEM_PROMPT = (
    "You are a security-domain assistant answering directly, without any tool "
    "access, live data, or retrieval. Be concise and explicit about uncertainty. "
    "If a question needs live SOC data you do not have, say so plainly."
)

DISCLAIMER = (
    "Ungoverned direct-model output. Not a SOC answer: no live data, MCP, RAG, "
    "or deterministic authority. Verify before acting."
)

_LLM_OFF_MODES = {"mock", "disabled", ""}


class LlmLabAskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    system_prompt: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=512, ge=1, le=2048)


def _provider_configured() -> bool:
    """True when at least one local/instruct endpoint resolves (no secrets leaked)."""
    return build_failover_chat_client(role=LAB_ROLE, sidecar=False) is not None


def _llm_available() -> bool:
    if settings.ai_soc_llm_mode.strip().lower() in _LLM_OFF_MODES:
        return False
    if not settings.ai_soc_llm_enabled:
        return False
    return _provider_configured()


def _available_models() -> list[str]:
    """Operator-curated model allowlist (advisory/display only, no secrets)."""
    raw = settings.ai_soc_llm_available_models or ""
    models = [item.strip() for item in raw.split(",") if item.strip()]
    active = (settings.ai_soc_llm_active_model or "").strip()
    if active and active not in models:
        models.insert(0, active)
    return models or ([active] if active else [])


@router.get("/llm-lab/status")
def llm_lab_status(_user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    """Readiness for the direct-LLM lab. Booleans only — never echoes secrets."""
    return {
        "available": _llm_available(),
        "llm_enabled": bool(settings.ai_soc_llm_enabled),
        "mode": settings.ai_soc_llm_mode,
        "provider_configured": _provider_configured(),
        "active_model": (settings.ai_soc_llm_active_model or "").strip() or None,
        "available_models": _available_models(),
        "disclaimer": DISCLAIMER,
    }


@router.post("/llm-lab/ask")
def llm_lab_ask(
    payload: LlmLabAskRequest,
    _user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Send a raw prompt straight to the on-prem model. No governance, no tools."""
    if not _llm_available():
        return {
            "answer": None,
            "available": False,
            "llm_called": False,
            "provider": None,
            "timed_out": False,
            "latency_ms": 0,
            "disclaimer": DISCLAIMER,
            "reason": "llm_unavailable",
        }

    system_prompt = (payload.system_prompt or "").strip() or LAB_SYSTEM_PROMPT
    started = time.monotonic()
    raw_output, timed_out, answered_label = invoke_sidecar_role(
        role=LAB_ROLE,
        user_prompt=payload.prompt,
        system_prompt=system_prompt,
        max_tokens=payload.max_tokens,
        timeout_seconds=LAB_TIMEOUT_SECONDS,
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    answer = (raw_output or "").strip() or None
    return {
        "answer": answer,
        "available": True,
        "llm_called": answer is not None,
        "provider": answered_label,
        "timed_out": timed_out,
        "latency_ms": latency_ms,
        "disclaimer": DISCLAIMER,
        "reason": None if answer is not None else ("llm_timed_out" if timed_out else "llm_no_output"),
    }
