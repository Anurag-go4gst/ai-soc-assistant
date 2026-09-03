"""Shared governance helpers for Stage 3K LLM-assist sidecars (Q1C/Q1D, future Q1F/Q1G).

Sidecars are Instruct-only, shadow-gated, and never authoritative. This module centralizes
role resolution (governance-resolved provider/model), reasoning rejection, skip reasons,
timeouts, forbidden-field notes, disagreement shape, and advisory confidence handling.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from contextvars import copy_context
from dataclasses import dataclass
from typing import Any, Callable

from app.config import settings
from app.llm.llm_call_context import run_with_call_context
from app.llm.registry_settings import REASONING_PROVIDER_ID, build_llm_governance_status
from app.synthesis.turn_timing import WrapperEventOutcome, record_wrapper_event

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
NOTE_LLM_PROVIDER_UNAVAILABLE = "llm_provider_unavailable"

# Failure classes a caller may need to tell apart. `timed_out` keeps its existing
# meaning ("the hop produced nothing, degrade") for the callers that branch on it;
# `failure_kind` carries the accurate class. Plan 7 D1: a provider exception used to
# be reported as a timeout, which made "LLM unavailable" and "LLM timeout"
# indistinguishable in every trace.
FAILURE_TIMEOUT = "timeout"
FAILURE_PROVIDER_UNAVAILABLE = "provider_unavailable"
FAILURE_POOL_REJECTED = "pool_rejected"
FAILURE_SLOT_BUSY = "slot_busy"
FAILURE_CIRCUIT_OPEN = "circuit_open"
NOTE_LLM_SLOT_BUSY = "llm_model_slot_busy"
NOTE_CONFIDENCE_ADVISORY_ONLY = "confidence_advisory_only"
NOTE_CIRCUIT_OPEN = "t4_circuit_open"
NOTE_HUMAN_ACTION_REQUIRED = "human_action_required_model_restart"
NOTE_CIRCUIT_HALF_OPEN = "t4_circuit_half_open_probe"

CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_OPEN = "OPEN"
CIRCUIT_HALF_OPEN = "HALF_OPEN"

# Trip the shared-model circuit. Slot-busy is backpressure, not model failure.
_CIRCUIT_FAILURE_KINDS = frozenset(
    {FAILURE_TIMEOUT, FAILURE_PROVIDER_UNAVAILABLE, FAILURE_POOL_REJECTED}
)

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
    failure_kind: str | None = None
    circuit_state: str | None = None
    human_action_required: bool = False


@dataclass
class T4Circuit:
    """Deterministic CLOSED/OPEN/HALF_OPEN breaker for the shared model slot.

    Opening the circuit sheds work. It never restarts Cisco. HALF_OPEN is allowed
    only after an operator records a manual restart plus inference-health evidence
    (not ``/v1/models`` liveness).
    """

    state: str = CIRCUIT_CLOSED
    consecutive_failures: int = 0
    opened_at: float | None = None
    half_open_in_flight: bool = False
    last_health: dict[str, Any] | None = None
    human_action_required: bool = False
    manual_restart_recorded: bool = False


_CIRCUIT = T4Circuit()
_CIRCUIT_LOCK = threading.Lock()


def _failure_threshold() -> int:
    return max(1, int(os.getenv("AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD", "3")))


def reset_t4_circuit() -> None:
    """Test/process isolation — does not restart the model."""
    global _CIRCUIT
    with _CIRCUIT_LOCK:
        _CIRCUIT = T4Circuit()


def t4_circuit_status() -> dict[str, Any]:
    with _CIRCUIT_LOCK:
        return {
            "state": _CIRCUIT.state,
            "consecutive_failures": _CIRCUIT.consecutive_failures,
            "human_action_required": _CIRCUIT.human_action_required,
            "manual_restart_recorded": _CIRCUIT.manual_restart_recorded,
            "half_open_in_flight": _CIRCUIT.half_open_in_flight,
            "last_health": dict(_CIRCUIT.last_health or {}),
            "opened_at": _CIRCUIT.opened_at,
        }


def request_human_model_restart() -> dict[str, Any]:
    """Operator diagnostic only. Never executes a restart command or API."""
    with _CIRCUIT_LOCK:
        _CIRCUIT.human_action_required = True
        _CIRCUIT.state = CIRCUIT_OPEN
        if _CIRCUIT.opened_at is None:
            _CIRCUIT.opened_at = time.monotonic()
    return {
        "human_action_required": True,
        "circuit_state": CIRCUIT_OPEN,
        "restart_authorized": False,
        "procedure": (
            "HUMAN ACTION REQUIRED: an operator must restart Cisco Foundation-Sec "
            "out of band, then call record_manual_model_restart() with inference-health "
            "evidence. This function does not restart the model."
        ),
    }


def record_manual_model_restart(*, inference_health_ok: bool, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record that a human already restarted the model. Does not restart it.

    ``inference_health_ok`` must come from a bounded generation probe, not from
    ``/v1/models`` liveness (Plan 7 F2 / Plan 8 REL0).
    """
    with _CIRCUIT_LOCK:
        _CIRCUIT.manual_restart_recorded = True
        _CIRCUIT.last_health = {
            "inference_health_ok": bool(inference_health_ok),
            "source": "operator_inference_probe",
            **dict(evidence or {}),
        }
        if not inference_health_ok:
            _CIRCUIT.state = CIRCUIT_OPEN
            _CIRCUIT.human_action_required = True
            _CIRCUIT.half_open_in_flight = False
        else:
            _CIRCUIT.state = CIRCUIT_HALF_OPEN
            _CIRCUIT.human_action_required = False
            _CIRCUIT.half_open_in_flight = False
            _CIRCUIT.consecutive_failures = 0
    return t4_circuit_status()


def _circuit_allow_request() -> tuple[bool, str, bool]:
    with _CIRCUIT_LOCK:
        if _CIRCUIT.state == CIRCUIT_CLOSED:
            return True, CIRCUIT_CLOSED, False
        if _CIRCUIT.state == CIRCUIT_OPEN:
            _CIRCUIT.human_action_required = True
            return False, CIRCUIT_OPEN, True
        if _CIRCUIT.state == CIRCUIT_HALF_OPEN:
            if _CIRCUIT.half_open_in_flight:
                return False, CIRCUIT_HALF_OPEN, False
            _CIRCUIT.half_open_in_flight = True
            return True, CIRCUIT_HALF_OPEN, False
        return False, _CIRCUIT.state, True


def _circuit_record_success() -> None:
    with _CIRCUIT_LOCK:
        _CIRCUIT.consecutive_failures = 0
        _CIRCUIT.half_open_in_flight = False
        _CIRCUIT.human_action_required = False
        _CIRCUIT.state = CIRCUIT_CLOSED
        _CIRCUIT.opened_at = None
        _CIRCUIT.manual_restart_recorded = False


def _circuit_record_failure(kind: str | None) -> None:
    if kind not in _CIRCUIT_FAILURE_KINDS:
        with _CIRCUIT_LOCK:
            _CIRCUIT.half_open_in_flight = False
        return
    with _CIRCUIT_LOCK:
        _CIRCUIT.consecutive_failures += 1
        _CIRCUIT.half_open_in_flight = False
        if _CIRCUIT.state == CIRCUIT_HALF_OPEN or _CIRCUIT.consecutive_failures >= _failure_threshold():
            _CIRCUIT.state = CIRCUIT_OPEN
            _CIRCUIT.human_action_required = True
            if _CIRCUIT.opened_at is None:
                _CIRCUIT.opened_at = time.monotonic()


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
    allow_reasoning: bool = False,
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

    if is_reasoning_provider_assignment(provider_text, model_text) and not allow_reasoning:
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


def _finalize_sidecar_result(
    result: SidecarLlmCallResult,
    *,
    success: bool,
    kind: str | None,
    probe_state: str,
) -> SidecarLlmCallResult:
    if success:
        _circuit_record_success()
    else:
        _circuit_record_failure(kind)
    status = t4_circuit_status()
    notes = list(result.notes)
    if probe_state == CIRCUIT_HALF_OPEN and NOTE_CIRCUIT_HALF_OPEN not in notes:
        notes.append(NOTE_CIRCUIT_HALF_OPEN)
    if status["state"] == CIRCUIT_OPEN and NOTE_CIRCUIT_OPEN not in notes:
        notes.append(NOTE_CIRCUIT_OPEN)
    if status["human_action_required"] and NOTE_HUMAN_ACTION_REQUIRED not in notes:
        notes.append(NOTE_HUMAN_ACTION_REQUIRED)
    return SidecarLlmCallResult(
        raw_output=result.raw_output,
        timed_out=result.timed_out,
        notes=notes,
        failure_kind=result.failure_kind,
        circuit_state=status["state"],
        human_action_required=bool(status["human_action_required"]),
    )


def run_sidecar_llm_with_timeout(
    llm_raw_output_provider: Callable[[], str],
    *,
    timeout_seconds: float = SIDECAR_ASSIST_TIMEOUT_SECONDS,
    slot_wait_seconds: float = 0.0,
    call_purpose: str | None = None,
    wrapper_kind: str = "sidecar",
    deadline: float | None = None,
) -> SidecarLlmCallResult:
    """Invoke sidecar LLM provider with a wall-clock timeout (default 1.5s).

    Acquires the single-flight model-slot guard first. ``slot_wait_seconds`` is the
    bounded time to wait for the slot before giving up; the default (0.0) is a
    non-blocking try-acquire so a busy slot skips the hop instead of stacking a second
    concurrent request onto a single-slot model. A skipped hop returns
    ``timed_out=False`` with no output and a ``NOTE_LLM_SLOT_BUSY`` note (distinct from
    a real timeout, so callers do not trigger failover pile-on).
    """
    started = time.monotonic()
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            duration_ms = int((time.monotonic() - started) * 1000)
            record_wrapper_event(
                duration_ms,
                call_purpose=call_purpose,
                wrapper_kind=wrapper_kind,
                outcome=WrapperEventOutcome.TIMEOUT,
            )
            return SidecarLlmCallResult(
                raw_output=None,
                timed_out=True,
                notes=[NOTE_LLM_ASSIST_TIMED_OUT],
                failure_kind=FAILURE_TIMEOUT,
            )
        timeout_seconds = min(timeout_seconds, remaining)

    allowed, circuit_state, human_action = _circuit_allow_request()
    if not allowed:
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.SATURATED,
        )
        notes = [NOTE_CIRCUIT_OPEN]
        if human_action:
            notes.append(NOTE_HUMAN_ACTION_REQUIRED)
        return SidecarLlmCallResult(
            raw_output=None,
            timed_out=False,
            notes=notes,
            failure_kind=FAILURE_CIRCUIT_OPEN,
            circuit_state=circuit_state,
            human_action_required=human_action,
        )

    slot = _MODEL_SLOT_SEMAPHORE
    if slot_wait_seconds and slot_wait_seconds > 0:
        acquired = slot.acquire(timeout=slot_wait_seconds)
    else:
        acquired = slot.acquire(blocking=False)
    if not acquired:
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.SATURATED,
        )
        return SidecarLlmCallResult(
            raw_output=None,
            timed_out=False,
            notes=[NOTE_LLM_SLOT_BUSY],
            failure_kind=FAILURE_SLOT_BUSY,
            circuit_state=circuit_state,
        )

    def _slot_guarded() -> str:
        try:
            return run_with_call_context(llm_raw_output_provider)
        finally:
            slot.release()

    try:
        future = _SIDECAR_EXECUTOR.submit(copy_context().run, _slot_guarded)
    except Exception:  # noqa: BLE001 — pool rejected the work; release and skip
        slot.release()
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.FAILURE,
        )
        return _finalize_sidecar_result(
            SidecarLlmCallResult(
                raw_output=None,
                timed_out=True,
                notes=[NOTE_LLM_ASSIST_TIMED_OUT],
                failure_kind=FAILURE_POOL_REJECTED,
            ),
            success=False,
            kind=FAILURE_POOL_REJECTED,
            probe_state=circuit_state,
        )

    try:
        raw_output = future.result(timeout=timeout_seconds)
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.COMPLETED,
        )
        return _finalize_sidecar_result(
            SidecarLlmCallResult(raw_output=raw_output, timed_out=False, notes=[]),
            success=True,
            kind=None,
            probe_state=circuit_state,
        )
    except (FuturesTimeoutError, TimeoutError):
        future.cancel()
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.TIMEOUT,
        )
        return _finalize_sidecar_result(
            SidecarLlmCallResult(
                raw_output=None,
                timed_out=True,
                notes=[NOTE_LLM_ASSIST_TIMED_OUT],
                failure_kind=FAILURE_TIMEOUT,
            ),
            success=False,
            kind=FAILURE_TIMEOUT,
            probe_state=circuit_state,
        )
    except Exception:  # noqa: BLE001 — never propagate provider errors to /chat
        duration_ms = int((time.monotonic() - started) * 1000)
        record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=WrapperEventOutcome.FAILURE,
        )
        # `timed_out=True` is retained so existing callers still degrade, but the note
        # and `failure_kind` say what actually happened: the provider failed, it did
        # not run out of time.
        return _finalize_sidecar_result(
            SidecarLlmCallResult(
                raw_output=None,
                timed_out=True,
                notes=[NOTE_LLM_PROVIDER_UNAVAILABLE],
                failure_kind=FAILURE_PROVIDER_UNAVAILABLE,
            ),
            success=False,
            kind=FAILURE_PROVIDER_UNAVAILABLE,
            probe_state=circuit_state,
        )


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
