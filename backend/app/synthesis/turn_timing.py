"""Turn-level timing instrumentation for live synthesis baseline (workstream E).

Best-effort wall-clock segments on the live `/chat` path. Never breaks chat;
payloads are sanitized (no prompts, queries, or credentials).

Schema v1 ``segments_ms`` preserves legacy semantics (broad ``retrieval_spl`` until
``generating_answer``). Accurate exclusive phases and per-hop endpoint attempts
live under ``attribution_v2``.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterator

SCHEMA_VERSION = "1"
ATTRIBUTION_V2_SCHEMA_VERSION = "3"
_ARITHMETIC_TOLERANCE_MS = 5

_SENSITIVE_KEY_FRAGMENTS = (
    "prompt",
    "query",
    "message",
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "url",
    "error_message",
    "error_body",
    "raw_error",
    "stack_trace",
)


class SynthesisPath(StrEnum):
    LAB = "lab"
    COMPOSER = "composer"
    SKIPPED = "skipped"


class TurnOutcome(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"
    SKIPPED = "skipped"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class EndpointAttemptOutcome(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"


class WrapperEventOutcome(StrEnum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    SATURATED = "saturated"


class RunKind(StrEnum):
    COLD = "cold"
    WARM = "warm"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EndpointAttemptRecord:
    duration_ms: int
    outcome: EndpointAttemptOutcome
    provider_label: str | None = None
    model: str | None = None
    call_purpose: str | None = None
    candidate_position: int | None = None


@dataclass(frozen=True)
class WrapperEventRecord:
    call_purpose: str | None
    wrapper_kind: str
    duration_ms: int
    outcome: WrapperEventOutcome


@dataclass
class TurnTimingSession:
    """Mutable per-turn collector; finalize once at response assembly."""

    started_at: float = field(default_factory=time.monotonic)
    run_kind: RunKind = RunKind.UNKNOWN
    canonical_planning_ms: int | None = None
    # v1 legacy broad post-planning interval (dispatch + post_planning_pipeline)
    retrieval_spl_ms: int | None = None
    synthesis_endpoint_ms: int | None = None
    synthesis_path: SynthesisPath = SynthesisPath.SKIPPED
    outcome: TurnOutcome = TurnOutcome.SKIPPED
    timeout_applied: bool = False
    fallback_used: bool = False
    governed_request_timeout: bool = False
    dispatch_and_retrieval_ms: int | None = None
    post_planning_pipeline_ms: int | None = None
    final_synthesis_ms: int | None = None
    finalization_ms: int | None = None
    endpoint_attempt_count: int = 0
    endpoint_attempt_timeout_count: int = 0
    endpoint_provider_label: str | None = None
    endpoint_model: str | None = None
    _dispatch_phase_started_at: float | None = None
    _post_planning_started_at: float | None = None
    _final_synthesis_started_at: float | None = None
    _finalization_started_at: float | None = None
    _endpoint_attempts: list[EndpointAttemptRecord] = field(default_factory=list)
    _wrapper_events: list[WrapperEventRecord] = field(default_factory=list)
    _suppressed_candidate_count: int = 0
    _finalized: bool = False

    def record_canonical_planning(self, duration_ms: int) -> None:
        self.canonical_planning_ms = max(0, int(duration_ms))
        self._dispatch_phase_started_at = time.monotonic()

    def close_dispatch_and_retrieval_phase(self) -> None:
        """After imperative/RP dispatch completes (MCP/RAG/SPL execution)."""
        if self._dispatch_phase_started_at is None:
            return
        elapsed = int((time.monotonic() - self._dispatch_phase_started_at) * 1000)
        self.dispatch_and_retrieval_ms = (self.dispatch_and_retrieval_ms or 0) + max(0, elapsed)
        self._dispatch_phase_started_at = None
        self._post_planning_started_at = time.monotonic()

    def close_post_planning_pipeline_phase(self) -> None:
        """At ``generating_answer`` — MITRE/sufficiency/severity assembly (v1 close)."""
        if self._post_planning_started_at is not None:
            elapsed = int((time.monotonic() - self._post_planning_started_at) * 1000)
            self.post_planning_pipeline_ms = (self.post_planning_pipeline_ms or 0) + max(0, elapsed)
            self._post_planning_started_at = None
        dispatch = self.dispatch_and_retrieval_ms or 0
        post = self.post_planning_pipeline_ms or 0
        if dispatch or post:
            self.retrieval_spl_ms = dispatch + post
        self._final_synthesis_started_at = time.monotonic()

    def begin_retrieval_spl_phase(self) -> None:
        """Legacy v1: noop when dispatch timer already started after canonical planning."""

    def close_retrieval_spl_phase(self) -> None:
        """Legacy v1 close at ``generating_answer`` (dispatch + post-planning)."""
        if self._dispatch_phase_started_at is not None:
            self.close_dispatch_and_retrieval_phase()
        self.close_post_planning_pipeline_phase()

    def record_synthesis_endpoint(
        self,
        duration_ms: int,
        *,
        path: SynthesisPath,
        outcome: TurnOutcome,
        timeout_applied: bool = False,
        fallback_used: bool = False,
        provider_label: str | None = None,
        model: str | None = None,
        endpoint_attempt_timeout: bool = False,
        governed_request_timeout: bool = False,
    ) -> None:
        attempt_outcome = EndpointAttemptOutcome.TIMEOUT if endpoint_attempt_timeout else (
            EndpointAttemptOutcome.FALLBACK
            if outcome in {TurnOutcome.FALLBACK, TurnOutcome.TIMEOUT}
            else EndpointAttemptOutcome.COMPLETED
        )
        if duration_ms > 0 or path is not SynthesisPath.SKIPPED:
            self.record_endpoint_attempt(
                duration_ms,
                outcome=attempt_outcome,
                provider_label=provider_label,
            )
        self.set_synthesis_path_outcome(
            path=path,
            outcome=outcome,
            timeout_applied=timeout_applied,
            fallback_used=fallback_used,
            governed_request_timeout=governed_request_timeout,
            provider_label=provider_label,
            model=model,
        )

    def close_final_synthesis_phase(self) -> None:
        """After governed lab narration + composer LLM block."""
        if self._final_synthesis_started_at is None:
            return
        elapsed = int((time.monotonic() - self._final_synthesis_started_at) * 1000)
        self.final_synthesis_ms = (self.final_synthesis_ms or 0) + max(0, elapsed)
        self._final_synthesis_started_at = None
        if self._finalization_started_at is None:
            self._finalization_started_at = time.monotonic()

    def record_endpoint_attempt(
        self,
        duration_ms: int,
        *,
        outcome: EndpointAttemptOutcome,
        provider_label: str | None = None,
        model: str | None = None,
        call_purpose: str | None = None,
        candidate_position: int | None = None,
    ) -> None:
        """One primary or failover model HTTP hop (nested inside final_synthesis)."""
        if self._finalized:
            return
        increment = max(0, int(duration_ms))
        self._endpoint_attempts.append(
            EndpointAttemptRecord(
                duration_ms=increment,
                outcome=outcome,
                provider_label=_bound_metadata(provider_label),
                model=_bound_metadata(model),
                call_purpose=_bound_metadata(call_purpose),
                candidate_position=candidate_position,
            )
        )
        self.endpoint_attempt_count += 1
        if outcome is EndpointAttemptOutcome.TIMEOUT:
            self.endpoint_attempt_timeout_count += 1
        self.synthesis_endpoint_ms = (self.synthesis_endpoint_ms or 0) + increment
        if provider_label:
            self.endpoint_provider_label = _bound_metadata(provider_label)

    def record_wrapper_event(
        self,
        duration_ms: int,
        *,
        call_purpose: str | None,
        wrapper_kind: str,
        outcome: WrapperEventOutcome,
    ) -> None:
        if self._finalized:
            return
        self._wrapper_events.append(
            WrapperEventRecord(
                call_purpose=_bound_metadata(call_purpose),
                wrapper_kind=_bound_metadata(wrapper_kind) or "unknown",
                duration_ms=max(0, int(duration_ms)),
                outcome=outcome,
            )
        )

    def record_suppressed_candidate(self) -> None:
        if self._finalized:
            return
        self._suppressed_candidate_count += 1

    def set_synthesis_path_outcome(
        self,
        *,
        path: SynthesisPath,
        outcome: TurnOutcome,
        timeout_applied: bool = False,
        fallback_used: bool = False,
        governed_request_timeout: bool = False,
        provider_label: str | None = None,
        model: str | None = None,
    ) -> None:
        if path is SynthesisPath.COMPOSER:
            self.synthesis_path = path
        elif self.synthesis_path is not SynthesisPath.COMPOSER:
            self.synthesis_path = path
        self.outcome = outcome
        self.timeout_applied = self.timeout_applied or bool(timeout_applied)
        self.fallback_used = self.fallback_used or bool(fallback_used)
        self.governed_request_timeout = self.governed_request_timeout or bool(governed_request_timeout)
        if provider_label:
            self.endpoint_provider_label = _bound_metadata(provider_label)
        if model:
            self.endpoint_model = _bound_metadata(model)

    def mark_synthesis_skipped(
        self,
        *,
        outcome: TurnOutcome = TurnOutcome.SKIPPED,
        reason: str | None = None,
    ) -> None:
        self.synthesis_path = SynthesisPath.SKIPPED
        self.outcome = outcome
        if reason:
            self.endpoint_provider_label = None
            self.endpoint_model = None

    def _close_open_phases_for_finalize(self) -> None:
        if self._dispatch_phase_started_at is not None:
            self.close_dispatch_and_retrieval_phase()
        if self._post_planning_started_at is not None:
            self.close_post_planning_pipeline_phase()
        if self._final_synthesis_started_at is not None:
            self.close_final_synthesis_phase()
        if self._finalization_started_at is not None:
            elapsed = int((time.monotonic() - self._finalization_started_at) * 1000)
            self.finalization_ms = (self.finalization_ms or 0) + max(0, elapsed)
            self._finalization_started_at = None

    def _exclusive_phase_total_ms(self) -> int:
        total = 0
        for value in (
            self.canonical_planning_ms,
            self.dispatch_and_retrieval_ms,
            self.post_planning_pipeline_ms,
            self.final_synthesis_ms,
            self.finalization_ms,
        ):
            if value is not None:
                total += value
        return total

    def finalize(self) -> dict[str, Any]:
        if not self._finalized:
            self._close_open_phases_for_finalize()
            self._finalized = True
        end_to_end_ms = int((time.monotonic() - self.started_at) * 1000)
        exclusive_total = self._exclusive_phase_total_ms()
        timing_arithmetic_valid = exclusive_total <= end_to_end_ms + _ARITHMETIC_TOLERANCE_MS
        application_overhead_v2 = max(0, end_to_end_ms - exclusive_total)
        # v1 legacy overhead (retrieval_spl is broad; synthesis_endpoint is nested diagnostic)
        v1_known = sum(
            value
            for value in (
                self.canonical_planning_ms,
                self.retrieval_spl_ms,
                self.synthesis_endpoint_ms,
            )
            if value is not None
        )
        application_overhead_ms = max(0, end_to_end_ms - v1_known)
        endpoint_attempt_ms_total = sum(row.duration_ms for row in self._endpoint_attempts)
        attempts_payload = [
            {
                "duration_ms": row.duration_ms,
                "outcome": row.outcome.value,
                "provider_label": row.provider_label,
                "model": row.model,
                "call_purpose": row.call_purpose,
                "candidate_position": row.candidate_position,
                "completed": row.outcome is EndpointAttemptOutcome.COMPLETED,
                "timeout": row.outcome is EndpointAttemptOutcome.TIMEOUT,
                "failure": row.outcome is EndpointAttemptOutcome.FALLBACK,
            }
            for row in self._endpoint_attempts
        ]
        wrapper_payload = [
            {
                "call_purpose": row.call_purpose,
                "wrapper_kind": row.wrapper_kind,
                "duration_ms": row.duration_ms,
                "outcome": row.outcome.value,
            }
            for row in self._wrapper_events
        ]
        return sanitize_turn_timing_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "run_kind": self.run_kind.value,
                "synthesis_path": self.synthesis_path.value,
                "outcome": self.outcome.value,
                "timeout_applied": self.timeout_applied,
                "fallback_used": self.fallback_used,
                "segments_ms": {
                    "canonical_planning": self.canonical_planning_ms,
                    "retrieval_spl": self.retrieval_spl_ms,
                    "synthesis_endpoint": self.synthesis_endpoint_ms,
                    "application_overhead": application_overhead_ms,
                    "end_to_end": end_to_end_ms,
                },
                "endpoint_detail": {
                    "provider_label": self.endpoint_provider_label,
                    "model": self.endpoint_model,
                    "http_round_trip_ms": self.synthesis_endpoint_ms,
                },
                "attribution_v2": {
                    "schema_version": ATTRIBUTION_V2_SCHEMA_VERSION,
                    "phase_segments_ms": {
                        "dispatch_and_retrieval": self.dispatch_and_retrieval_ms,
                        "post_planning_pipeline": self.post_planning_pipeline_ms,
                        "final_synthesis": self.final_synthesis_ms,
                        "finalization": self.finalization_ms,
                    },
                    "phase_boundaries": {
                        "dispatch_and_retrieval": (
                            "after canonical_planning until graph_node_context_finalize entry "
                            "(imperative dispatch + RP graph_node_context_finalize dispatch)"
                        ),
                        "post_planning_pipeline": (
                            "context_finalize entry until emit_stage(generating_answer) "
                            "(MITRE, sufficiency, severity assembly)"
                        ),
                        "final_synthesis": (
                            "generating_answer until close after lab narration + composer LLM block"
                        ),
                        "finalization": (
                            "after final_synthesis until finalize_turn_timing "
                            "(answer guard, surfacing, trace assembly)"
                        ),
                    },
                    "endpoint_attempts": attempts_payload,
                    "endpoint_attempt_count": self.endpoint_attempt_count,
                    "endpoint_attempt_timeout_count": self.endpoint_attempt_timeout_count,
                    "endpoint_attempt_ms_total": endpoint_attempt_ms_total,
                    "wrapper_events": wrapper_payload,
                    "suppressed_candidate_count": self._suppressed_candidate_count,
                    "governed_request_timeout": self.governed_request_timeout,
                    "endpoint_attempt_timeout": self.endpoint_attempt_timeout_count > 0,
                    "exclusive_phase_total_ms": exclusive_total,
                    "application_overhead_exclusive_ms": application_overhead_v2,
                    "timing_arithmetic_valid": timing_arithmetic_valid,
                },
            }
        )


_session: ContextVar[TurnTimingSession | None] = ContextVar("synthesis_turn_timing", default=None)

_METADATA_MAX_LEN = 64


def _bound_metadata(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).strip()[:_METADATA_MAX_LEN] or None


def benchmark_run_kind_override() -> RunKind | None:
    raw = os.getenv("AI_SOC_BENCHMARK_RUN_KIND", "").strip().lower()
    if raw in {"cold", "warm"}:
        return RunKind(raw)
    return None


def resolve_run_kind(*, explicit: RunKind | None = None) -> RunKind:
    if explicit is not None and explicit is not RunKind.UNKNOWN:
        return explicit
    return RunKind.UNKNOWN


@contextmanager
def synthesis_turn_timing_scope(*, run_kind: RunKind | None = None) -> Iterator[TurnTimingSession]:
    session = TurnTimingSession(run_kind=resolve_run_kind(explicit=run_kind))
    token = _session.set(session)
    try:
        yield session
    finally:
        _session.reset(token)


def get_turn_timing_session() -> TurnTimingSession | None:
    return _session.get()


def record_canonical_planning_ms(duration_ms: int) -> None:
    session = _session.get()
    if session is not None:
        session.record_canonical_planning(duration_ms)


def close_dispatch_and_retrieval_phase() -> None:
    session = _session.get()
    if session is not None:
        session.close_dispatch_and_retrieval_phase()


def close_post_planning_pipeline_phase() -> None:
    session = _session.get()
    if session is not None:
        session.close_post_planning_pipeline_phase()


def close_final_synthesis_phase() -> None:
    session = _session.get()
    if session is not None:
        session.close_final_synthesis_phase()


def record_endpoint_attempt(
    duration_ms: int,
    *,
    outcome: EndpointAttemptOutcome,
    provider_label: str | None = None,
    model: str | None = None,
    call_purpose: str | None = None,
    candidate_position: int | None = None,
) -> None:
    session = _session.get()
    if session is not None:
        session.record_endpoint_attempt(
            duration_ms,
            outcome=outcome,
            provider_label=provider_label,
            model=model,
            call_purpose=call_purpose,
            candidate_position=candidate_position,
        )


def record_suppressed_candidate() -> None:
    session = _session.get()
    if session is not None:
        session.record_suppressed_candidate()


def record_wrapper_event(
    duration_ms: int,
    *,
    call_purpose: str | None,
    wrapper_kind: str,
    outcome: WrapperEventOutcome,
) -> None:
    session = _session.get()
    if session is not None:
        session.record_wrapper_event(
            duration_ms,
            call_purpose=call_purpose,
            wrapper_kind=wrapper_kind,
            outcome=outcome,
        )


def set_synthesis_path_outcome(
    *,
    path: SynthesisPath,
    outcome: TurnOutcome,
    timeout_applied: bool = False,
    fallback_used: bool = False,
    governed_request_timeout: bool = False,
    provider_label: str | None = None,
    model: str | None = None,
) -> None:
    session = _session.get()
    if session is not None:
        session.set_synthesis_path_outcome(
            path=path,
            outcome=outcome,
            timeout_applied=timeout_applied,
            fallback_used=fallback_used,
            governed_request_timeout=governed_request_timeout,
            provider_label=provider_label,
            model=model,
        )


def record_synthesis_endpoint(
    duration_ms: int,
    *,
    path: SynthesisPath,
    outcome: TurnOutcome,
    timeout_applied: bool = False,
    fallback_used: bool = False,
    provider_label: str | None = None,
    model: str | None = None,
    endpoint_attempt_timeout: bool = False,
    governed_request_timeout: bool = False,
) -> None:
    """Backward-compatible wrapper: records one hop + path outcome."""
    attempt_outcome = EndpointAttemptOutcome.TIMEOUT if endpoint_attempt_timeout else (
        EndpointAttemptOutcome.FALLBACK
        if outcome in {TurnOutcome.FALLBACK, TurnOutcome.TIMEOUT}
        else EndpointAttemptOutcome.COMPLETED
    )
    if duration_ms > 0 or path is not SynthesisPath.SKIPPED:
        record_endpoint_attempt(
            duration_ms,
            outcome=attempt_outcome,
            provider_label=provider_label,
        )
    set_synthesis_path_outcome(
        path=path,
        outcome=outcome,
        timeout_applied=timeout_applied,
        fallback_used=fallback_used,
        governed_request_timeout=governed_request_timeout,
        provider_label=provider_label,
        model=model,
    )


def mark_synthesis_skipped(*, outcome: TurnOutcome = TurnOutcome.SKIPPED) -> None:
    session = _session.get()
    if session is not None:
        session.mark_synthesis_skipped(outcome=outcome)


def finalize_turn_timing() -> dict[str, Any] | None:
    session = _session.get()
    if session is None:
        return None
    return session.finalize()


# Legacy aliases (v1 close at generating_answer)
def begin_retrieval_spl_phase() -> None:
    get_turn_timing_session()


def close_retrieval_spl_phase() -> None:
    close_post_planning_pipeline_phase()


def sanitize_turn_timing_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def _walk(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
                    continue
                cleaned[key] = _walk(item)
            return cleaned
        if isinstance(value, list):
            return [_walk(item) for item in value]
        if isinstance(value, str) and len(value) > 256:
            return value[:256]
        return value

    return _walk(payload)


def validate_timing_payload_arithmetic(payload: dict[str, Any]) -> bool:
    """Return False when exclusive v2 phases exceed end_to_end."""
    v2 = payload.get("attribution_v2") or {}
    if isinstance(v2.get("timing_arithmetic_valid"), bool):
        return bool(v2["timing_arithmetic_valid"])
    segments = payload.get("segments_ms") or {}
    end_to_end = int(segments.get("end_to_end") or 0)
    exclusive = int(v2.get("exclusive_phase_total_ms") or 0)
    return exclusive <= end_to_end + _ARITHMETIC_TOLERANCE_MS
