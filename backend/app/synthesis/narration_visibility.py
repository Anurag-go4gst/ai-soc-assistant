"""Narration / LLM-usage visibility (WS3 T3.2) — read-model, never authority.

One shared builder consolidating the scattered composer/guard/fallback traces
into a single auditable block. Consumed by the live chat response
(`narration_visibility` field), the answer scorecard, and the PowerGrid eval
(which previously kept a private copy of this mapping). Reporting only:
nothing here can change MITRE, severity, SPL, HIL, or execution outcomes.
"""

from __future__ import annotations

from typing import Any

LLM_EARLY_SKIP_REASONS = frozenset(
    {
        "draft_spl_preview_active",
        "Knowledge/SOP profile uses deterministic governed RAG summary.",
        "analyst_response_unavailable",
        "composer_not_eligible",
    }
)

_TIMEOUT_MARKERS = ("timeout", "timed out", "deadline")


def composer_trace_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    composer = payload.get("llm_composer") if isinstance(payload.get("llm_composer"), dict) else {}
    if not composer and isinstance(trace.get("llm_composer"), dict):
        composer = trace["llm_composer"]
    return composer


def llm_skip_reason(composer: dict[str, Any]) -> str | None:
    blocked = composer.get("llm_blocked_reason")
    if isinstance(blocked, str) and blocked.strip():
        return blocked.strip()
    skipped = composer.get("composer_skipped_reason")
    if isinstance(skipped, str) and skipped.strip():
        return skipped.strip()
    provider_skip = composer.get("provider_skip_reason")
    if isinstance(provider_skip, str) and provider_skip.strip():
        return provider_skip.strip()
    if composer.get("llm_guard_status") == "disabled":
        return "composer_disabled_by_config"
    return None


def llm_eligible(composer: dict[str, Any]) -> bool:
    return bool(composer.get("composer_is_enabled"))


def llm_attempted(composer: dict[str, Any]) -> bool:
    if composer.get("llm_composer_used"):
        return True
    if composer.get("llm_guard_status") == "blocked":
        return True
    reason = str(composer.get("llm_blocked_reason") or "")
    if composer.get("llm_fallback_used") and reason and reason not in LLM_EARLY_SKIP_REASONS:
        return True
    return False


def llm_skip_category(skip_reason: str | None, composer: dict[str, Any]) -> str | None:
    if skip_reason and any(marker in skip_reason.lower() for marker in _TIMEOUT_MARKERS):
        return "timeout_degraded"
    if skip_reason in LLM_EARLY_SKIP_REASONS:
        return "early_skip"
    if skip_reason == "composer_disabled_by_config" or composer.get("llm_guard_status") == "disabled":
        return "disabled_by_config"
    if skip_reason in {"Live LLM client is not configured.", "no_provider_configured"}:
        return "provider_not_configured"
    if composer.get("llm_guard_status") == "blocked":
        return "compose_validation_blocked"
    if composer.get("llm_fallback_used") and skip_reason:
        return "llm_call_or_validation_fallback"
    if skip_reason:
        return "other_skip"
    if not composer:
        return "no_composer_trace"
    return None


def build_narration_visibility(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Consolidated, auditable view of LLM narration usage for one answer."""
    composer = composer_trace_from_payload(payload)
    trace = (
        payload.get("control_plane_trace")
        if isinstance(payload, dict) and isinstance(payload.get("control_plane_trace"), dict)
        else {}
    )
    answer_guard = {}
    final_validation = {}
    if isinstance(payload, dict):
        answer_guard = payload.get("answer_guard") if isinstance(payload.get("answer_guard"), dict) else {}
        if not answer_guard and isinstance(trace.get("answer_guard"), dict):
            answer_guard = trace["answer_guard"]
        final_validation = (
            payload.get("final_answer_validation")
            if isinstance(payload.get("final_answer_validation"), dict)
            else {}
        )
        if not final_validation and isinstance(trace.get("final_answer_validation"), dict):
            final_validation = trace["final_answer_validation"]

    skip_reason = llm_skip_reason(composer)
    used = bool(composer.get("llm_composer_used"))
    skip_category = llm_skip_category(skip_reason, composer)
    return {
        "composer_eligible": llm_eligible(composer),
        "composer_attempted": llm_attempted(composer),
        "composer_used": used,
        "composer_enabled": bool(composer.get("llm_composer_enabled")),
        "guard_status": composer.get("llm_guard_status"),
        "guard_blocked": composer.get("llm_guard_status") == "blocked",
        "fallback_used": bool(composer.get("llm_fallback_used")),
        "timeout_or_degraded": skip_category == "timeout_degraded",
        "skip_reason": skip_reason,
        "skip_category": skip_category,
        "narration_llm_called": bool(trace.get("analyst_summary_narration_llm_called")),
        "answer_guard_status": answer_guard.get("guard_status"),
        "final_answer_guard_status": final_validation.get("guard_status"),
        "provider_configured": composer.get("provider_configured"),
        "final_answer_source": "llm_narration" if used else "deterministic_contract",
    }
