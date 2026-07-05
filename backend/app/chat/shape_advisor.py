from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.chat.answer_shape_router import (
    classify_answer_shape,
    reference_taxonomy_negative_signal,
    reference_taxonomy_registry_signal,
)
from app.config import settings
from app.llm.adapter.role_results import adapt_llm_output
from app.llm.adapter.schemas import ShapeAdvisorPayload
from app.llm.sidecar_clients import invoke_sidecar_role_with_metadata, sidecar_timeout_seconds

SHAPE_ADVISOR_ROLE = "shape_advisor"


@dataclass(frozen=True)
class ShapeAdvisoryResult:
    suggested_shape: str | None = None
    confidence: float | None = None
    rationale: str = ""
    llm_called: bool = False
    provider_label: str | None = None
    timed_out: bool = False
    used: bool = False
    promoted_shape: str | None = None
    deterministic_shape: str | None = None
    ignored_reason: str | None = None
    skipped_reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    latency_ms: int | None = None

    def to_trace(self) -> dict[str, Any]:
        return {
            "role": SHAPE_ADVISOR_ROLE,
            "suggested_shape": self.suggested_shape,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "llm_called": self.llm_called,
            "provider_label": self.provider_label,
            "timed_out": self.timed_out,
            "used": self.used,
            "promoted_shape": self.promoted_shape,
            "deterministic_shape": self.deterministic_shape,
            "ignored_reason": self.ignored_reason,
            "skipped_reason": self.skipped_reason,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "latency_ms": self.latency_ms,
        }


def build_shape_advisor_prompt(query: str, *, deterministic_shape: str) -> str:
    return (
        "Classify the answer shape for this SOC question.\n"
        f"Deterministic shape: {deterministic_shape}\n"
        f"Question: {query}\n"
        "Return only JSON with suggested_shape, confidence, rationale."
    )


def generate_shape_advisory(
    query: str,
    *,
    deterministic_shape: str,
    raw_output_provider: Callable[[], str] | None = None,
    timeout_seconds: float | None = None,
) -> ShapeAdvisoryResult:
    if not settings.ai_soc_llm_final_synthesis_enabled or not settings.ai_soc_llm_live_synthesis_enabled:
        return ShapeAdvisoryResult(
            deterministic_shape=deterministic_shape,
            skipped_reason="live_synthesis_disabled",
        )

    started = time.monotonic()
    if raw_output_provider is None:
        invocation = invoke_sidecar_role_with_metadata(
            role=SHAPE_ADVISOR_ROLE,
            user_prompt=build_shape_advisor_prompt(query, deterministic_shape=deterministic_shape),
            max_tokens=10,
            timeout_seconds=timeout_seconds or min(10.0, sidecar_timeout_seconds(SHAPE_ADVISOR_ROLE)),
            temperature=0.0,
            allow_failover=False,
        )
        raw_output = invocation.raw_output
        timed_out = invocation.timed_out
        provider_label = invocation.answered_label
        if raw_output is None:
            # timed_out=True means the sidecar WAS invoked and the model didn't
            # answer in time (live-load condition) — distinct from the role
            # being unconfigured. Conflating the two masks a real timeout as a
            # config problem in the trace (found live 2026-07-05: 10002ms
            # latency reported as "unavailable_or_disabled").
            return ShapeAdvisoryResult(
                deterministic_shape=deterministic_shape,
                llm_called=False,
                timed_out=timed_out,
                provider_label=provider_label,
                skipped_reason="shape_advisor_timed_out" if timed_out else "shape_advisor_unavailable_or_disabled",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
    else:
        raw_output = raw_output_provider()
        timed_out = False
        provider_label = "test_provider"

    adapted = adapt_llm_output(role=SHAPE_ADVISOR_ROLE, raw_output=raw_output)
    if not adapted.accepted or not isinstance(adapted.normalized_payload, dict):
        return ShapeAdvisoryResult(
            deterministic_shape=deterministic_shape,
            llm_called=True,
            provider_label=provider_label,
            timed_out=timed_out,
            skipped_reason="shape_advisor_parse_failed",
            warnings=list(adapted.warnings),
            errors=list(adapted.errors),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    payload = ShapeAdvisorPayload.model_validate(adapted.normalized_payload)
    return ShapeAdvisoryResult(
        suggested_shape=payload.suggested_shape,
        confidence=payload.confidence,
        rationale=payload.rationale,
        deterministic_shape=deterministic_shape,
        llm_called=True,
        provider_label=provider_label,
        timed_out=timed_out,
        warnings=list(adapted.warnings),
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def apply_shape_advisory_promotion(query: str, advisory: ShapeAdvisoryResult) -> ShapeAdvisoryResult:
    deterministic_shape = advisory.deterministic_shape or classify_answer_shape(query).primary_shape
    if advisory.skipped_reason:
        return advisory
    if deterministic_shape == "reference_taxonomy":
        return ShapeAdvisoryResult(
            **{**advisory.__dict__, "ignored_reason": "advisory_ignored_deterministic_match", "deterministic_shape": deterministic_shape}
        )
    if advisory.suggested_shape != "reference_taxonomy":
        return ShapeAdvisoryResult(
            **{**advisory.__dict__, "ignored_reason": "advisory_not_reference_taxonomy", "deterministic_shape": deterministic_shape}
        )
    if reference_taxonomy_negative_signal(query):
        return ShapeAdvisoryResult(
            **{**advisory.__dict__, "ignored_reason": "reference_taxonomy_negative_signal", "deterministic_shape": deterministic_shape}
        )
    if not reference_taxonomy_registry_signal(query):
        return ShapeAdvisoryResult(
            **{**advisory.__dict__, "ignored_reason": "reference_taxonomy_partial_signal_missing", "deterministic_shape": deterministic_shape}
        )
    return ShapeAdvisoryResult(
        **{
            **advisory.__dict__,
            "used": True,
            "promoted_shape": "reference_taxonomy",
            "ignored_reason": None,
            "deterministic_shape": deterministic_shape,
        }
    )
