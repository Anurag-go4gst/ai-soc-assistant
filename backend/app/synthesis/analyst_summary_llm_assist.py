"""Stage 3K-Q1G: Instruct-only shadow narration for analyst summary (lineage reveal only)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.sidecar_governance import (
    REASONING_REJECTION_NARRATION,
    SKIP_NO_PROVIDER_CONFIGURED,
    run_sidecar_llm_with_timeout,
)
from app.synthesis.analyst_summary_skeleton import (
    MAX_SUMMARY_CHARS,
    MAX_TRACE_BULLETS,
    build_analyst_summary_skeleton,
    narration_to_shadow_fields,
)

ANALYST_SUMMARY_NARRATION_ROLE = "analyst_summary_narration"
NARRATION_ASSIST_TIMEOUT_SECONDS = 3.0

DROP_SCHEMA_INVALID = "schema_invalid"
DROP_LENGTH_EXCEEDED = "length_exceeded"
DROP_UNSUPPORTED_CLAIM = "unsupported_claim"
DROP_LLM_TIMED_OUT = "llm_timed_out"
DROP_NARRATION_SHADOW_DISABLED = "narration_shadow_disabled"

FORBIDDEN_PHRASES: tuple[tuple[str, str], ...] = (
    ("this would run", "forbidden_phrase_this_would_run"),
    ("this executed", "forbidden_phrase_this_executed"),
    ("ready to run", "forbidden_phrase_ready_to_run"),
    ("we ran", "forbidden_phrase_we_ran"),
    ("results show", "forbidden_phrase_results_show"),
    ("this is what runs", "forbidden_phrase_this_is_what_runs"),
    ("production", "forbidden_phrase_production"),
)

ACTION_RECOMMENDATION_PATTERNS = (
    re.compile(r"\byou should\b", re.IGNORECASE),
    re.compile(r"\bnext,\s*do\b", re.IGNORECASE),
)

IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass
class AnalystSummaryNarrationResult:
    accepted: bool = False
    narration: dict[str, Any] | None = None
    dropped_reasons: list[str] = field(default_factory=list)
    llm_called: bool = False
    source: str | None = None
    adapter_warnings: list[str] = field(default_factory=list)


@dataclass
class AnalystSummaryShadowApplyResult:
    analyst_summary_shadow_available: bool = False
    analyst_summary_shadow_source: str | None = None


def build_structured_narration_input(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    """Redacted structured facts for narration; no rendered SPL body."""
    return {
        "preflight_status": route_plan_shadow.get("preflight_status"),
        "route_status": route_plan_shadow.get("route_status"),
        "primary_skill": route_plan_shadow.get("primary_skill"),
        "pattern_id": route_plan_shadow.get("pattern_id"),
        "candidate_reason": route_plan_shadow.get("candidate_reason"),
        "missing_slots": list(route_plan_shadow.get("missing_slots") or []),
        "template_match_shadow_status": route_plan_shadow.get("template_match_shadow_status"),
        "matched_template_id": route_plan_shadow.get("matched_template_id"),
        "template_match_attempted": route_plan_shadow.get("template_match_attempted"),
        "rendered_spl_available": route_plan_shadow.get("rendered_spl_available"),
        "rendered_spl_sha256": route_plan_shadow.get("rendered_spl_sha256"),
        "execution_authorized": route_plan_shadow.get("execution_authorized"),
        "spl_executed": route_plan_shadow.get("spl_executed"),
        "mcp_called": route_plan_shadow.get("mcp_called"),
        "llm_called": route_plan_shadow.get("llm_called"),
        "llm_candidate_route_plan_available": route_plan_shadow.get("llm_candidate_route_plan_available"),
        "deterministic_route_plan_wins": route_plan_shadow.get("deterministic_route_plan_wins"),
        "allowed_claim_tokens": sorted(_collect_allowed_claim_tokens(route_plan_shadow)),
    }


def apply_analyst_summary_shadow(
    route_plan_shadow: dict[str, Any],
    *,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> AnalystSummaryShadowApplyResult:
    """Populate Q1G shadow narration fields on route_plan_shadow (in-place)."""
    _set_shadow_defaults(route_plan_shadow)

    if not settings.routing_llm_shadow_enabled or not settings.ai_soc_llm_shadow_narration_enabled:
        route_plan_shadow["analyst_summary_dropped_reasons"] = [DROP_NARRATION_SHADOW_DISABLED]
        return AnalystSummaryShadowApplyResult(analyst_summary_shadow_available=False)

    structured = build_structured_narration_input(route_plan_shadow)
    narration_result = narrate_analyst_summary(structured, llm_raw_output_provider=llm_raw_output_provider)

    if narration_result.accepted and narration_result.narration:
        fields = narration_to_shadow_fields(narration_result.narration)
        route_plan_shadow.update(fields)
        route_plan_shadow["analyst_summary_shadow_available"] = True
        route_plan_shadow["analyst_summary_shadow_source"] = narration_result.source or "llm_shadow"
        route_plan_shadow["analyst_summary_narration_llm_called"] = narration_result.llm_called
        route_plan_shadow["analyst_summary_dropped_reasons"] = []
        return AnalystSummaryShadowApplyResult(
            analyst_summary_shadow_available=True,
            analyst_summary_shadow_source=route_plan_shadow["analyst_summary_shadow_source"],
        )

    skeleton = build_analyst_summary_skeleton(structured)
    route_plan_shadow.update(narration_to_shadow_fields(skeleton))
    route_plan_shadow["analyst_summary_shadow_available"] = True
    route_plan_shadow["analyst_summary_shadow_source"] = "deterministic_skeleton"
    route_plan_shadow["analyst_summary_narration_llm_called"] = narration_result.llm_called
    route_plan_shadow["analyst_summary_dropped_reasons"] = list(narration_result.dropped_reasons)
    for note in narration_result.adapter_warnings:
        if note not in route_plan_shadow["warnings"]:
            route_plan_shadow["warnings"].append(note)
    return AnalystSummaryShadowApplyResult(
        analyst_summary_shadow_available=True,
        analyst_summary_shadow_source="deterministic_skeleton",
    )


def narrate_analyst_summary(
    structured_input: dict[str, Any],
    *,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> AnalystSummaryNarrationResult:
    """Attempt Instruct shadow narration; never mutates analyst answer envelope."""
    from app.llm.sidecar_governance import resolve_sidecar_role_status

    result = AnalystSummaryNarrationResult()

    if not settings.routing_llm_shadow_enabled or not settings.ai_soc_llm_shadow_narration_enabled:
        result.dropped_reasons = [DROP_NARRATION_SHADOW_DISABLED]
        return result

    assist_invoked = llm_raw_output_provider is not None
    role_status = resolve_sidecar_role_status(
        ANALYST_SUMMARY_NARRATION_ROLE,
        reasoning_rejection_reason=REASONING_REJECTION_NARRATION,
        assist_invoked=assist_invoked,
    )

    if role_status.rejected_reason:
        result.dropped_reasons = [role_status.rejected_reason]
        return result

    if role_status.llm_assist_skipped_reason or not assist_invoked:
        skipped = role_status.llm_assist_skipped_reason or SKIP_NO_PROVIDER_CONFIGURED
        result.dropped_reasons = [skipped]
        return result

    result.llm_called = True
    call = run_sidecar_llm_with_timeout(
        llm_raw_output_provider,
        timeout_seconds=NARRATION_ASSIST_TIMEOUT_SECONDS,
    )
    if call.timed_out or not call.raw_output:
        result.dropped_reasons = [DROP_LLM_TIMED_OUT]
        result.adapter_warnings.extend(call.notes)
        return result

    return _process_narration_raw(
        call.raw_output,
        structured_input=structured_input,
        result=result,
    )


def _process_narration_raw(
    raw_output: str,
    *,
    structured_input: dict[str, Any],
    result: AnalystSummaryNarrationResult,
) -> AnalystSummaryNarrationResult:
    adapter = adapt_llm_output(role=ANALYST_SUMMARY_NARRATION_ROLE, raw_output=raw_output)
    result.adapter_warnings.extend(adapter.warnings)
    if not adapter.schema_valid or not adapter.accepted or adapter.normalized_payload is None:
        result.dropped_reasons = [DROP_SCHEMA_INVALID]
        return result

    payload = adapter.normalized_payload
    drop_reasons = _post_adapter_drop_reasons(payload, structured_input=structured_input)
    if drop_reasons:
        result.dropped_reasons = drop_reasons
        return result

    result.accepted = True
    result.narration = payload
    result.source = "llm_shadow"
    return result


def _post_adapter_drop_reasons(payload: dict[str, Any], *, structured_input: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    text_blob = _narration_text_blob(payload)

    for phrase, reason in FORBIDDEN_PHRASES:
        if phrase in text_blob.lower():
            reasons.append(reason)

    for pattern in ACTION_RECOMMENDATION_PATTERNS:
        if pattern.search(text_blob):
            reasons.append("forbidden_phrase_action_recommendation")
            break

    if len(str(payload.get("summary_sentence_1") or "")) > MAX_SUMMARY_CHARS:
        reasons.append(DROP_LENGTH_EXCEEDED)
    second = payload.get("summary_sentence_2")
    if isinstance(second, str) and len(second) > MAX_SUMMARY_CHARS:
        reasons.append(DROP_LENGTH_EXCEEDED)

    bullets = payload.get("technical_trace_bullets")
    if not isinstance(bullets, list) or len(bullets) != MAX_TRACE_BULLETS:
        reasons.append(DROP_SCHEMA_INVALID)
    elif any(len(str(item)) > MAX_SUMMARY_CHARS for item in bullets):
        reasons.append(DROP_LENGTH_EXCEEDED)

    sentence_count = 1 + (1 if isinstance(second, str) and second.strip() else 0)
    if sentence_count > 2:
        reasons.append(DROP_LENGTH_EXCEEDED)

    allowed_ips = set(structured_input.get("allowed_claim_tokens") or [])
    for ip in IPV4_PATTERN.findall(text_blob):
        if ip not in allowed_ips:
            reasons.append(DROP_UNSUPPORTED_CLAIM)
            break

    if structured_input.get("spl_executed") is not True and "results show" in text_blob.lower():
        if "forbidden_phrase_results_show" not in reasons:
            reasons.append("forbidden_phrase_results_show")

    return sorted(set(reasons))


def _narration_text_blob(payload: dict[str, Any]) -> str:
    parts = [str(payload.get("summary_sentence_1") or "")]
    second = payload.get("summary_sentence_2")
    if isinstance(second, str):
        parts.append(second)
    bullets = payload.get("technical_trace_bullets")
    if isinstance(bullets, list):
        parts.extend(str(item) for item in bullets)
    return " ".join(parts)


def _collect_allowed_claim_tokens(route_plan_shadow: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)
        elif isinstance(value, (str, int, float, bool)):
            text = str(value)
            tokens.add(text)
            for ip in IPV4_PATTERN.findall(text):
                tokens.add(ip)

    _walk(route_plan_shadow)
    return tokens


def _set_shadow_defaults(route_plan_shadow: dict[str, Any]) -> None:
    route_plan_shadow.setdefault("analyst_summary_shadow_available", False)
    route_plan_shadow.setdefault("analyst_summary_shadow_text", None)
    route_plan_shadow.setdefault("analyst_summary_trace_bullets", [])
    route_plan_shadow.setdefault("analyst_summary_dropped_reasons", [])
    route_plan_shadow.setdefault("analyst_summary_shadow_source", None)
    route_plan_shadow.setdefault("analyst_summary_narration_llm_called", False)
    route_plan_shadow.setdefault("coe_synthetic_fixture", True)
    route_plan_shadow.setdefault("captured_live_run", False)
    route_plan_shadow.setdefault("production_execution", False)
