"""Shared governance helpers for Stage 3K LLM-assist sidecars (Q1C/Q1D, future Q1F/Q1G).

Sidecars are Instruct-only, shadow-gated, and never authoritative. This module centralizes
role resolution (governance-resolved provider/model), reasoning rejection, skip reasons,
timeouts, forbidden-field notes, disagreement shape, and advisory confidence handling.
"""

from __future__ import annotations

import json
import os
import threading
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
REASONING_REJECTION_NARRATION = "reasoning_model_not_allowed_for_narration"

NOTE_LLM_ASSIST_TIMED_OUT = "llm_assist_timed_out"
NOTE_LLM_SLOT_BUSY = "llm_model_slot_busy"
NOTE_CONFIDENCE_ADVISORY_ONLY = "confidence_advisory_only"

# Persistent pool — never use ``with ThreadPoolExecutor()`` here: __exit__ joins workers
# and defeats ``future.result(timeout=...)``. Orphaned workers are bounded by the
# client socket timeout in LocalChatClient (see endpoint_resolver sidecar cap).
_SIDECAR_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("AI_SOC_SIDECAR_MAX_WORKERS", "8")),
    thread_name_prefix="sidecar-llm",
)

# Single-flight guard for the physical model slot (P2-A gate: "no abandoned request
# keeps occupying the single model slot"). On a single-slot 8B, future.cancel() cannot
# stop a running urlopen, so a timed-out hop stays orphaned on the socket and keeps the
# slot busy until it actually returns. The semaphore models real slot occupancy, not
# caller liveness: the worker releases it in ``finally`` when the call truly completes,
# so a caller timeout does NOT free the slot. A new hop try-acquires non-blocking; if the
# slot is still held by an orphan it skips (``NOTE_LLM_SLOT_BUSY``) → deterministic
# fallback, instead of piling a second concurrent request onto the slot and thrashing.
_MODEL_SLOTS = max(1, int(os.getenv("AI_SOC_LLM_MODEL_SLOTS", "1")))
_MODEL_SLOT_SEMAPHORE = threading.BoundedSemaphore(_MODEL_SLOTS)


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
    slot_wait_seconds: float = 0.0,
) -> SidecarLlmCallResult:
    """Invoke sidecar LLM provider with a wall-clock timeout (default 1.5s).

    Acquires the single-flight model-slot guard first. ``slot_wait_seconds`` is the
    bounded time to wait for the slot before giving up; the default (0.0) is a
    non-blocking try-acquire so a busy slot skips the hop instead of stacking a second
    concurrent request onto a single-slot model. A skipped hop returns
    ``timed_out=False`` with no output and a ``NOTE_LLM_SLOT_BUSY`` note (distinct from
    a real timeout, so callers do not trigger failover pile-on).
    """
    # Bind the live semaphore once so the worker releases the exact object it acquired,
    # even if the module global is later rebound (e.g. per-test isolation fixtures).
    slot = _MODEL_SLOT_SEMAPHORE
    if slot_wait_seconds and slot_wait_seconds > 0:
        acquired = slot.acquire(timeout=slot_wait_seconds)
    else:
        acquired = slot.acquire(blocking=False)
    if not acquired:
        return SidecarLlmCallResult(raw_output=None, timed_out=False, notes=[NOTE_LLM_SLOT_BUSY])

    # The worker owns slot release so the slot is freed only when the call truly
    # finishes — even after the caller below has timed out and walked away.
    def _slot_guarded() -> str:
        try:
            return llm_raw_output_provider()
        finally:
            slot.release()

    try:
        future = _SIDECAR_EXECUTOR.submit(_slot_guarded)
    except Exception:  # noqa: BLE001 — pool rejected the work; release and skip
        slot.release()
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=[NOTE_LLM_ASSIST_TIMED_OUT])

    try:
        raw_output = future.result(timeout=timeout_seconds)
        return SidecarLlmCallResult(raw_output=raw_output, timed_out=False, notes=[])
    except (FuturesTimeoutError, TimeoutError):
        # Do not join the worker — cancel is best-effort for a running urlopen. The
        # orphan keeps the slot held until _slot_guarded's finally runs, so the next
        # hop sees the slot busy and skips instead of thrashing the single model slot.
        future.cancel()
        return SidecarLlmCallResult(raw_output=None, timed_out=True, notes=[NOTE_LLM_ASSIST_TIMED_OUT])
    except Exception:  # noqa: BLE001 — never propagate provider errors to /chat
        # _slot_guarded's finally already released the slot on a provider error.
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
