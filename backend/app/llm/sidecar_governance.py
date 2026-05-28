"""Shared governance helpers for Stage 3K LLM-assist sidecars (Q1C/Q1D, future Q1F/Q1G).

Sidecars are Instruct-only, shadow-gated, and never authoritative. This module centralizes
role resolution (governance-resolved provider/model), reasoning rejection, skip reasons,
timeouts, forbidden-field notes, disagreement shape, and advisory confidence handling.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from app.config import settings
from app.llm.registry_settings import REASONING_PROVIDER_ID, build_llm_governance_status

SIDECAR_ASSIST_TIMEOUT_SECONDS = 1.5

SKIP_LLM_DISABLED = "llm_disabled"
SKIP_NO_PROVIDER_CONFIGURED = "no_provider_configured"
SKIP_ROLE_NOT_CONFIGURED = "role_not_configured"
SKIP_ROLE_NOT_ENABLED = "role_not_enabled"

REASONING_REJECTION_MATCHING = "reasoning_model_not_allowed_for_matching"
REASONING_REJECTION_RENDERING = "reasoning_model_not_allowed_for_rendering"
REASONING_REJECTION_ROUTING = "reasoning_model_not_allowed_for_routing"

NOTE_LLM_ASSIST_TIMED_OUT = "llm_assist_timed_out"
NOTE_CONFIDENCE_ADVISORY_ONLY = "confidence_advisory_only"


@dataclass(frozen=True)
class SidecarRoleStatus:
    """Governance-resolved status for a sidecar role."""

    enabled: bool
    rejected_reason: str | None = None
    llm_assist_skipped_reason: str | None = None
    resolved_provider: str | None = None
    resolved_model: str | None = None
    role_configured: bool = False


@dataclass(frozen=True)
class SidecarLlmCallResult:
    """Result of a bounded sidecar LLM invocation."""

    raw_output: str | None
    timed_out: bool
    notes: list[str]


def is_reasoning_provider_assignment(provider: str | None, model: str | None) -> bool:
    """True when governance-resolved provider/model is Foundation-sec-Reasoning."""
    if provider and provider.strip() == REASONING_PROVIDER_ID:
        return True
    if model and "reasoning" in model.strip().lower():
        return True
    return False


def resolve_sidecar_role_status(
    role: str,
    *,
    reasoning_rejection_reason: str,
    assist_invoked: bool = False,
) -> SidecarRoleStatus:
    """Resolve sidecar role using governance ``roles`` entry (not env-only)."""
    if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
        return SidecarRoleStatus(
            enabled=False,
            llm_assist_skipped_reason=SKIP_LLM_DISABLED,
        )

    governance = build_llm_governance_status()
    role_entry = next(
        (item for item in governance.get("role_mappings", []) if item.get("role") == role),
        None,
    )

    if not role_entry:
        if assist_invoked:
            return SidecarRoleStatus(enabled=True, role_configured=False)
        return SidecarRoleStatus(
            enabled=False,
            llm_assist_skipped_reason=SKIP_ROLE_NOT_CONFIGURED,
            role_configured=False,
        )

    resolved_provider = role_entry.get("provider")
    resolved_model = role_entry.get("model")
    provider_text = str(resolved_provider).strip() if resolved_provider else None
    model_text = str(resolved_model).strip() if resolved_model else None

    if is_reasoning_provider_assignment(provider_text, model_text):
        return SidecarRoleStatus(
            enabled=False,
            rejected_reason=reasoning_rejection_reason,
            resolved_provider=provider_text,
            resolved_model=model_text,
            role_configured=True,
        )

    if not role_entry.get("enabled"):
        if assist_invoked:
            return SidecarRoleStatus(
                enabled=True,
                resolved_provider=provider_text,
                resolved_model=model_text,
                role_configured=True,
            )
        skipped = SKIP_NO_PROVIDER_CONFIGURED if not provider_text else SKIP_ROLE_NOT_ENABLED
        return SidecarRoleStatus(
            enabled=False,
            llm_assist_skipped_reason=skipped,
            resolved_provider=provider_text,
            resolved_model=model_text,
            role_configured=True,
        )

    return SidecarRoleStatus(
        enabled=True,
        resolved_provider=provider_text,
        resolved_model=model_text,
        role_configured=True,
    )


def run_sidecar_llm_with_timeout(
    llm_raw_output_provider: Callable[[], str],
    *,
    timeout_seconds: float = SIDECAR_ASSIST_TIMEOUT_SECONDS,
) -> SidecarLlmCallResult:
    """Invoke sidecar LLM provider with a hard timeout (default 1.5s)."""
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(llm_raw_output_provider)
            raw_output = future.result(timeout=timeout_seconds)
        return SidecarLlmCallResult(raw_output=raw_output, timed_out=False, notes=[])
    except (FuturesTimeoutError, TimeoutError):
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=[NOTE_LLM_ASSIST_TIMED_OUT])


def build_sidecar_metadata_payload(
    *,
    skipped_reason: str | None = None,
    rejected_reason: str | None = None,
    timed_out: bool = False,
    advisory_confidence: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a backward-compatible sidecar metadata envelope."""
    payload: dict[str, Any] = {
        "coe_synthetic_fixture": True,
        "captured_live_run": False,
        "production_execution": False,
    }
    if skipped_reason:
        payload["llm_assist_skipped_reason"] = skipped_reason
    if rejected_reason:
        payload["rejected_reason"] = rejected_reason
    if timed_out:
        payload["timed_out"] = True
        payload["llm_assist_timed_out"] = True
    if advisory_confidence is not None:
        payload["advisory_confidence"] = advisory_confidence
        payload["confidence_advisory_only"] = True
    if extra:
        payload.update(extra)
    return payload


def adapter_dropped_field_notes(
    dropped_fields: list[str],
    *,
    forbidden_keys: frozenset[str],
    forbidden_substrings: tuple[str, ...] = ("template",),
) -> list[str]:
    """Map adapter dropped fields to stable sidecar notes."""
    notes: list[str] = []
    forbidden_hit = False
    for field in dropped_fields:
        if field in forbidden_keys or any(part in field for part in forbidden_substrings):
            forbidden_hit = True
        notes.append(f"dropped_field:{field}")
    if forbidden_hit:
        notes.insert(0, "forbidden_field_stripped")
    return notes


def build_advisory_disagreement(
    *,
    field: str,
    llm_value: Any,
    deterministic_value: Any,
    reason_for_deterministic_win: str,
) -> dict[str, Any]:
    """Standard disagreement record shape (deterministic authority wins)."""
    return {
        "field": field,
        "llm_value": llm_value,
        "deterministic_value": deterministic_value,
        "reason_for_deterministic_win": reason_for_deterministic_win,
    }


def extract_advisory_confidence(
    raw_output: str,
    *,
    nested_paths: tuple[tuple[str, ...], ...] = (),
) -> tuple[float | None, list[str]]:
    """Extract confidence for advisory metadata only; never used for authority."""
    notes: list[str] = []
    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return None, notes
    if not isinstance(parsed, dict):
        return None, notes

    candidates: list[Any] = []
    if "confidence" in parsed:
        candidates.append(parsed.get("confidence"))
    for path in nested_paths:
        node: Any = parsed
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, dict) and "confidence" in node:
            candidates.append(node.get("confidence"))

    for value in candidates:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            notes.append(NOTE_CONFIDENCE_ADVISORY_ONLY)
            return float(value), notes
    return None, notes
