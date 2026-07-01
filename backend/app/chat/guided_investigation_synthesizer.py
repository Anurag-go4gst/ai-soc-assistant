"""Guided investigation LLM orchestration trace + honest degraded fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.chat.guided_step_sanitizer import filter_analyst_facing_steps
from app.config import settings
from app.llm.guided_llm_budget import (
    guided_composer_timeout_seconds,
    guided_llm_enabled,
    guided_turn_deadline_seconds,
)


@dataclass(frozen=True)
class GuidedLlmTrace:
    guided_llm_required: bool
    guided_llm_attempted: bool
    guided_llm_used: bool
    guided_llm_timeout: bool
    guided_llm_degraded_fallback: bool
    guided_llm_budget_seconds: float
    guided_llm_elapsed_ms: int | None
    guided_llm_failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "guided_llm_required": self.guided_llm_required,
            "guided_llm_attempted": self.guided_llm_attempted,
            "guided_llm_used": self.guided_llm_used,
            "guided_llm_timeout": self.guided_llm_timeout,
            "guided_llm_degraded_fallback": self.guided_llm_degraded_fallback,
            "guided_llm_budget_seconds": self.guided_llm_budget_seconds,
            "guided_llm_elapsed_ms": self.guided_llm_elapsed_ms,
            "guided_llm_failure_reason": self.guided_llm_failure_reason,
        }


def guided_llm_required_for_path(path_type: str | None) -> bool:
    return guided_llm_enabled() and str(path_type or "") == "guided_investigation"


def build_guided_llm_degraded_message(
    *,
    checklist: list[str] | None = None,
    failure_reason: str | None = None,
) -> str:
    reason = str(failure_reason or "timeout_or_unavailable").replace("_", " ")
    items = filter_analyst_facing_steps(list(checklist or []))[:6]
    checklist_block = ""
    if items:
        checklist_block = "\n".join(f"- {item}" for item in items)
        checklist_block = f"\n\nMinimal deterministic checklist:\n{checklist_block}"
    return (
        "Guided investigation requires the local LLM planner, but it "
        f"{reason}. No live telemetry was queried. "
        "Retry when the on-prem model is healthy or increase "
        "AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS."
        f"{checklist_block}"
    )


def build_guided_llm_trace(
    *,
    path_type: str | None,
    composer_trace: dict[str, Any] | None,
    elapsed_ms: int | None = None,
) -> GuidedLlmTrace:
    required = guided_llm_required_for_path(path_type)
    trace = composer_trace if isinstance(composer_trace, dict) else {}
    skipped = str(trace.get("llm_composer_skipped_reason") or trace.get("composer_skipped_reason") or "")
    blocked = str(trace.get("llm_blocked_reason") or "")
    used = bool(trace.get("llm_composer_used"))
    attempted = bool(
        trace.get("composer_attempted")
        or trace.get("llm_composer_enabled")
        or skipped
        or blocked
        or used
    )
    timed_out = "timeout" in skipped.lower() or "timeout" in blocked.lower()
    degraded = required and not used
    failure = None
    if degraded:
        failure = skipped or blocked or ("llm_timed_out" if timed_out else "guided_llm_unavailable")
    return GuidedLlmTrace(
        guided_llm_required=required,
        guided_llm_attempted=attempted if required else False,
        guided_llm_used=used if required else False,
        guided_llm_timeout=timed_out if required else False,
        guided_llm_degraded_fallback=degraded,
        guided_llm_budget_seconds=guided_turn_deadline_seconds() if required else 0.0,
        guided_llm_elapsed_ms=elapsed_ms,
        guided_llm_failure_reason=failure,
    )


def resolve_guided_composer_timeout(budget: Any) -> float | None:
    """Composer timeout for guided path; falls back to budget cap otherwise."""
    if not guided_llm_enabled():
        return budget.capped_hop_timeout_seconds(role="governed_composer")
    return guided_composer_timeout_seconds(budget)
