"""Per-turn LLM call accounting for trace and scorecard readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnLlmBudget:
    max_sidecar_calls: int = 2
    max_narration_calls: int = 1
    sidecar_calls: int = 0
    narration_calls: int = 0
    records: list[dict[str, Any]] = field(default_factory=list)

    def record_sidecar(self, *, role: str, provider_label: str | None, outcome: str) -> None:
        self.sidecar_calls += 1
        self.records.append(
            {
                "kind": "sidecar",
                "role": role,
                "provider_label": provider_label,
                "outcome": outcome,
            }
        )

    def record_narration(self, *, provider_label: str | None, outcome: str) -> None:
        self.narration_calls += 1
        self.records.append(
            {
                "kind": "narration",
                "provider_label": provider_label,
                "outcome": outcome,
            }
        )

    def sidecar_budget_exhausted(self) -> bool:
        return self.sidecar_calls >= self.max_sidecar_calls

    def narration_budget_exhausted(self) -> bool:
        return self.narration_calls >= self.max_narration_calls

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "max_sidecar_calls": self.max_sidecar_calls,
            "max_narration_calls": self.max_narration_calls,
            "sidecar_calls": self.sidecar_calls,
            "narration_calls": self.narration_calls,
            "records": list(self.records),
        }
