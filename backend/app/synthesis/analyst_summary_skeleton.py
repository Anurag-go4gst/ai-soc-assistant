"""Deterministic analyst-summary skeleton for Stage 3K-Q1G shadow narration fallback."""

from __future__ import annotations

from typing import Any

MAX_SUMMARY_CHARS = 240
MAX_TRACE_BULLETS = 3


def build_analyst_summary_skeleton(structured_input: dict[str, Any]) -> dict[str, Any]:
    """Build a one- to two-sentence skeleton and three trace bullets from structured input only."""
    preflight = str(structured_input.get("preflight_status") or "observed")
    skill = str(structured_input.get("primary_skill") or "not_selected")
    route_status = str(structured_input.get("route_status") or "not_evaluated")
    template_status = str(structured_input.get("template_match_shadow_status") or "not_attempted")
    matched_template = structured_input.get("matched_template_id")

    sentence_1 = (
        f"Shadow route-plan observation only: preflight {preflight}, "
        f"deterministic skill {skill}, route status {route_status}."
    )[:MAX_SUMMARY_CHARS]

    sentence_2 = None
    if matched_template:
        sentence_2 = (
            f"Template match shadow status {template_status} for template {matched_template}; "
            "no execution was authorized."
        )[:MAX_SUMMARY_CHARS]
    elif not structured_input.get("execution_authorized"):
        sentence_2 = "Execution remains unauthorized; this path records metadata only."[:MAX_SUMMARY_CHARS]

    bullets = [
        f"Preflight: {preflight}; missing slots: {_format_list(structured_input.get('missing_slots'))}.",
        f"Route-plan shadow: {route_status}; candidate reason: {structured_input.get('candidate_reason') or 'none'}.",
        (
            f"Template shadow: {template_status}; rendered SPL available: "
            f"{bool(structured_input.get('rendered_spl_available'))} (hash only, not shown)."
        ),
    ][:MAX_TRACE_BULLETS]

    return {
        "summary_sentence_1": sentence_1,
        "summary_sentence_2": sentence_2,
        "technical_trace_bullets": bullets,
        "source": "deterministic_skeleton",
    }


def narration_to_shadow_fields(narration: dict[str, Any]) -> dict[str, Any]:
    """Join narration dict into envelope fields."""
    parts = [str(narration.get("summary_sentence_1") or "").strip()]
    second = narration.get("summary_sentence_2")
    if isinstance(second, str) and second.strip():
        parts.append(second.strip())
    bullets = narration.get("technical_trace_bullets")
    if not isinstance(bullets, list):
        bullets = []
    return {
        "analyst_summary_shadow_text": " ".join(part for part in parts if part),
        "analyst_summary_trace_bullets": [str(item) for item in bullets[:MAX_TRACE_BULLETS]],
    }


def _format_list(value: Any) -> str:
    if isinstance(value, list) and value:
        return ", ".join(str(item) for item in value)
    return "none"
