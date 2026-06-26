"""Per-turn LLM call accounting for trace and scorecard readiness."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


from app.llm.sidecar_clients import INTENT_ROLE


def intent_advisor_reserve_seconds() -> float:
    """Protected wall-time reserve for the intent advisor hop."""
    from app.config import settings

    configured = float(getattr(settings, "ai_soc_llm_intent_advisor_reserve_seconds", 12.0) or 12.0)
    return max(1.0, configured)


def downstream_optional_reserve_seconds() -> float:
    """Soft downstream reservation for optional late hops (e.g. composer narration)."""
    from app.config import settings

    configured = max(1.0, float(getattr(settings, "ai_soc_llm_timeout_seconds", 30) or 30))
    return max(1.0, min(configured, 15.0))


def hop_reserve_seconds(role: str) -> float:
    """Wall time that must remain before starting a sidecar hop."""
    from app.config import settings
    from app.llm.sidecar_clients import sidecar_timeout_seconds

    if role == INTENT_ROLE:
        return intent_advisor_reserve_seconds()
    return max(
        1.0,
        min(
            sidecar_timeout_seconds(role),
            float(getattr(settings, "ai_soc_llm_timeout_seconds", 30) or 30),
        ),
    )


@dataclass
class TurnLlmBudget:
    max_sidecar_calls: int = 2
    max_narration_calls: int = 1
    deadline_seconds: float = 75.0
    sidecar_calls: int = 0
    narration_calls: int = 0
    started_at: float = field(default_factory=time.monotonic)
    records: list[dict[str, Any]] = field(default_factory=list)

    def time_budget_exhausted(self) -> bool:
        return self.deadline_seconds > 0 and (time.monotonic() - self.started_at) >= self.deadline_seconds

    def remaining_seconds(self) -> float | None:
        if self.deadline_seconds <= 0:
            return None
        return max(0.0, self.deadline_seconds - (time.monotonic() - self.started_at))

    def capped_hop_timeout_seconds(
        self,
        *,
        role: str,
        min_seconds: float = 1.0,
    ) -> float | None:
        """Wall-clock timeout for one hop, capped to the remaining turn budget."""
        from app.llm.sidecar_clients import sidecar_timeout_seconds

        role_timeout = sidecar_timeout_seconds(role)
        remaining = self.remaining_seconds()
        if remaining is None:
            return role_timeout
        if remaining <= min_seconds:
            return None
        return max(min_seconds, min(role_timeout, remaining))

    def composer_reserve_seconds(self) -> float:
        """Reserve required before starting governed composer narration."""
        from app.config import settings

        configured = max(1.0, float(getattr(settings, "ai_soc_llm_timeout_seconds", 30) or 30))
        remaining = self.remaining_seconds()
        if remaining is None:
            return configured
        return max(1.0, min(configured, remaining))

    def can_start_call(self, *, reserve_seconds: float = 0.0) -> bool:
        remaining = self.remaining_seconds()
        # >= so a hop may start when the capped socket window exactly fits the
        # remaining turn budget (composer_reserve clamps to remaining).
        return remaining is None or remaining >= max(0.0, reserve_seconds)

    def sidecar_hop_blocked(self, *, role: str) -> str | None:
        if self.sidecar_calls >= self.max_sidecar_calls:
            return "turn_budget_exhausted"
        if self.time_budget_exhausted():
            return "turn_budget_exhausted"
        reserve = hop_reserve_seconds(role)
        if not self.can_start_call(reserve_seconds=reserve):
            return "insufficient_deadline_reserve"
        return None

    def narration_hop_blocked(self, *, reserve_seconds: float | None = None) -> str | None:
        del reserve_seconds  # trace callers may pass composer_reserve; gate uses capped hop.
        if self.narration_calls >= self.max_narration_calls:
            return "turn_budget_exhausted"
        if self.time_budget_exhausted():
            return "turn_budget_exhausted"
        if self.capped_hop_timeout_seconds(role="governed_composer", min_seconds=1.0) is None:
            return "insufficient_deadline_reserve"
        return None

    def _record_entry(
        self,
        *,
        kind: str,
        outcome: str,
        role: str | None = None,
        provider_label: str | None = None,
        latency_ms: int | None = None,
        model: str | None = None,
        reserve_seconds: float | None = None,
        token_usage: dict[str, Any] | None = None,
        cancelled: bool | None = None,
    ) -> dict[str, Any]:
        remaining = self.remaining_seconds()
        entry: dict[str, Any] = {
            "kind": kind,
            "outcome": outcome,
            "latency_ms": latency_ms,
            "model": model,
            "deadline_remaining_seconds": round(remaining, 2) if remaining is not None else None,
        }
        if role is not None:
            entry["role"] = role
        if provider_label is not None:
            entry["provider_label"] = provider_label
        if reserve_seconds is not None:
            entry["reserve_seconds"] = round(reserve_seconds, 2)
        if token_usage:
            entry["token_usage"] = dict(token_usage)
        if cancelled is not None:
            entry["cancelled"] = cancelled
        return entry

    def record_sidecar(
        self,
        *,
        role: str,
        provider_label: str | None,
        outcome: str,
        latency_ms: int | None = None,
        model: str | None = None,
        reserve_seconds: float | None = None,
        token_usage: dict[str, Any] | None = None,
        cancelled: bool | None = None,
    ) -> None:
        self.sidecar_calls += 1
        self.records.append(
            self._record_entry(
                kind="sidecar",
                role=role,
                provider_label=provider_label,
                outcome=outcome,
                latency_ms=latency_ms,
                model=model,
                reserve_seconds=reserve_seconds if reserve_seconds is not None else hop_reserve_seconds(role),
                token_usage=token_usage,
                cancelled=cancelled,
            )
        )

    def record_narration(
        self,
        *,
        provider_label: str | None,
        outcome: str,
        latency_ms: int | None = None,
        model: str | None = None,
        reserve_seconds: float | None = None,
        token_usage: dict[str, Any] | None = None,
        cancelled: bool | None = None,
    ) -> None:
        self.narration_calls += 1
        self.records.append(
            self._record_entry(
                kind="narration",
                provider_label=provider_label,
                outcome=outcome,
                latency_ms=latency_ms,
                model=model,
                reserve_seconds=reserve_seconds,
                token_usage=token_usage,
                cancelled=cancelled,
            )
        )

    def sidecar_budget_exhausted(self) -> bool:
        return self.sidecar_calls >= self.max_sidecar_calls or self.time_budget_exhausted()

    def narration_budget_exhausted(self) -> bool:
        return self.narration_calls >= self.max_narration_calls or self.time_budget_exhausted()

    def to_trace_dict(self) -> dict[str, Any]:
        remaining = self.remaining_seconds()
        return {
            "max_sidecar_calls": self.max_sidecar_calls,
            "max_narration_calls": self.max_narration_calls,
            "deadline_seconds": self.deadline_seconds,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 2),
            "remaining_seconds": round(remaining, 2) if remaining is not None else None,
            "time_budget_exhausted": self.time_budget_exhausted(),
            "sidecar_calls": self.sidecar_calls,
            "narration_calls": self.narration_calls,
            "records": list(self.records),
        }
