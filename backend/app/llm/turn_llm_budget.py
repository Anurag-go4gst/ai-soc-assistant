"""Per-turn LLM call accounting for trace and scorecard readiness."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnLlmBudget:
    max_sidecar_calls: int = 2
    max_narration_calls: int = 1
    # Wall-clock ceiling for all blocking LLM calls on a turn. Without it, stacked
    # sidecars on a slow on-prem model push /chat to 70-160s (the deterministic
    # answer is unaffected). 0 disables the time gate. Default leaves room for the
    # most valuable single call while capping the worst-case stack.
    deadline_seconds: float = 75.0
    sidecar_calls: int = 0
    narration_calls: int = 0
    started_at: float = field(default_factory=time.monotonic)
    records: list[dict[str, Any]] = field(default_factory=list)

    def time_budget_exhausted(self) -> bool:
        return self.deadline_seconds > 0 and (time.monotonic() - self.started_at) >= self.deadline_seconds

    def record_sidecar(
        self,
        *,
        role: str,
        provider_label: str | None,
        outcome: str,
        latency_ms: int | None = None,
        model: str | None = None,
    ) -> None:
        self.sidecar_calls += 1
        self.records.append(
            {
                "kind": "sidecar",
                "role": role,
                "provider_label": provider_label,
                "outcome": outcome,
                "latency_ms": latency_ms,
                "model": model,
            }
        )

    def record_narration(
        self,
        *,
        provider_label: str | None,
        outcome: str,
        latency_ms: int | None = None,
        model: str | None = None,
    ) -> None:
        self.narration_calls += 1
        self.records.append(
            {
                "kind": "narration",
                "provider_label": provider_label,
                "outcome": outcome,
                "latency_ms": latency_ms,
                "model": model,
            }
        )

    def sidecar_budget_exhausted(self) -> bool:
        return self.sidecar_calls >= self.max_sidecar_calls or self.time_budget_exhausted()

    def narration_budget_exhausted(self) -> bool:
        return self.narration_calls >= self.max_narration_calls or self.time_budget_exhausted()

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "max_sidecar_calls": self.max_sidecar_calls,
            "max_narration_calls": self.max_narration_calls,
            "deadline_seconds": self.deadline_seconds,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 2),
            "time_budget_exhausted": self.time_budget_exhausted(),
            "sidecar_calls": self.sidecar_calls,
            "narration_calls": self.narration_calls,
            "records": list(self.records),
        }
