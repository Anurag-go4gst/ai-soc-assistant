"""Turn-level timing instrumentation for live synthesis baseline (workstream E).

Best-effort wall-clock segments on the live `/chat` path. Never breaks chat;
payloads are sanitized (no prompts, queries, or credentials).
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
COLD_WARM_GAP_SECONDS = 120.0

_SENSITIVE_KEY_FRAGMENTS = (
    "prompt",
    "query",
    "message",
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
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


class RunKind(StrEnum):
    COLD = "cold"
    WARM = "warm"
    UNKNOWN = "unknown"


@dataclass
class TurnTimingSession:
    """Mutable per-turn collector; finalize once at response assembly."""

    started_at: float = field(default_factory=time.monotonic)
    run_kind: RunKind = RunKind.UNKNOWN
    canonical_planning_ms: int | None = None
    retrieval_spl_ms: int | None = None
    synthesis_endpoint_ms: int | None = None
    synthesis_path: SynthesisPath = SynthesisPath.SKIPPED
    outcome: TurnOutcome = TurnOutcome.SKIPPED
    timeout_applied: bool = False
    fallback_used: bool = False
    endpoint_provider_label: str | None = None
    endpoint_model: str | None = None
    _retrieval_phase_started_at: float | None = None
    _finalized: bool = False

    def record_canonical_planning(self, duration_ms: int) -> None:
        self.canonical_planning_ms = max(0, int(duration_ms))
        self._retrieval_phase_started_at = time.monotonic()

    def begin_retrieval_spl_phase(self) -> None:
        if self._retrieval_phase_started_at is None:
            self._retrieval_phase_started_at = time.monotonic()

    def close_retrieval_spl_phase(self) -> None:
        if self._retrieval_phase_started_at is None:
            return
        elapsed = int((time.monotonic() - self._retrieval_phase_started_at) * 1000)
        prior = self.retrieval_spl_ms or 0
        self.retrieval_spl_ms = prior + max(0, elapsed)
        self._retrieval_phase_started_at = None

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
    ) -> None:
        increment = max(0, int(duration_ms))
        prior = self.synthesis_endpoint_ms or 0
        self.synthesis_endpoint_ms = prior + increment if increment else prior
        if path is SynthesisPath.COMPOSER:
            self.synthesis_path = path
        elif self.synthesis_path is not SynthesisPath.COMPOSER:
            self.synthesis_path = path
        self.outcome = outcome
        self.timeout_applied = self.timeout_applied or bool(timeout_applied)
        self.fallback_used = self.fallback_used or bool(fallback_used)
        if provider_label:
            self.endpoint_provider_label = provider_label
        if model:
            self.endpoint_model = model
        if increment:
            _mark_synthesis_completed()

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

    def finalize(self) -> dict[str, Any]:
        if not self._finalized:
            self.close_retrieval_spl_phase()
            self._finalized = True
        end_to_end_ms = int((time.monotonic() - self.started_at) * 1000)
        known_parts = [
            value
            for value in (
                self.canonical_planning_ms,
                self.retrieval_spl_ms,
                self.synthesis_endpoint_ms,
            )
            if value is not None
        ]
        known_total = sum(known_parts)
        application_overhead_ms = max(0, end_to_end_ms - known_total)
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
            }
        )


_session: ContextVar[TurnTimingSession | None] = ContextVar("synthesis_turn_timing", default=None)
_last_synthesis_completed_at: float | None = None


def _mark_synthesis_completed() -> None:
    global _last_synthesis_completed_at
    _last_synthesis_completed_at = time.monotonic()


def benchmark_run_kind_override() -> RunKind | None:
    """Harness-only cold/warm hint (benchmark script env; not production config)."""
    raw = os.getenv("AI_SOC_BENCHMARK_RUN_KIND", "").strip().lower()
    if raw in {"cold", "warm"}:
        return RunKind(raw)
    return None


def infer_run_kind(*, explicit: RunKind | None = None) -> RunKind:
    if explicit is not None and explicit is not RunKind.UNKNOWN:
        return explicit
    if _last_synthesis_completed_at is None:
        return RunKind.COLD
    gap = time.monotonic() - _last_synthesis_completed_at
    if gap >= COLD_WARM_GAP_SECONDS:
        return RunKind.COLD
    return RunKind.WARM


@contextmanager
def synthesis_turn_timing_scope(*, run_kind: RunKind | None = None) -> Iterator[TurnTimingSession]:
    session = TurnTimingSession(run_kind=infer_run_kind(explicit=run_kind))
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


def begin_retrieval_spl_phase() -> None:
    session = _session.get()
    if session is not None:
        session.begin_retrieval_spl_phase()


def close_retrieval_spl_phase() -> None:
    session = _session.get()
    if session is not None:
        session.close_retrieval_spl_phase()


def record_synthesis_endpoint(
    duration_ms: int,
    *,
    path: SynthesisPath,
    outcome: TurnOutcome,
    timeout_applied: bool = False,
    fallback_used: bool = False,
    provider_label: str | None = None,
    model: str | None = None,
) -> None:
    session = _session.get()
    if session is not None:
        session.record_synthesis_endpoint(
            duration_ms,
            path=path,
            outcome=outcome,
            timeout_applied=timeout_applied,
            fallback_used=fallback_used,
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


def sanitize_turn_timing_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unexpected keys and redact sensitive fragments from string values."""

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
