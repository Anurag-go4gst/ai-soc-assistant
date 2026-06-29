"""Budgeted LLM SPL drafting for universal utility authoring (PR #58).

Reuses ``spl_advisory_generator`` / ``generate_llm_spl_fallback`` with a bounded
hop, deterministic skeleton fallback, and the existing review-only postprocessor.
"""

from __future__ import annotations

from typing import Any, Callable

from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.llm.sidecar_clients import invoke_sidecar_role
from app.spl.draft_preview import build_draft_preview
from app.spl.llm_fallback import (
    SPL_ADVISORY_ROLE,
    generate_llm_spl_fallback,
    spl_advisory_prompts,
)
from app.spl.review_only_spl_postprocessor import normalize_review_only_spl
from app.spl.source_profile_store import load_persisted_source_profile
from app.spl.user_constraint_bindings import build_user_constraint_bindings


def utility_spl_draft_enabled() -> bool:
    return bool(settings.ai_soc_llm_utility_spl_draft_enabled)


def utility_spl_draft_failover_enabled() -> bool:
    return bool(settings.ai_soc_llm_utility_spl_draft_failover_enabled)


def utility_spl_draft_timeout_seconds() -> float:
    configured = float(settings.ai_soc_llm_utility_spl_draft_timeout_seconds or 90.0)
    return max(10.0, configured)


def build_utility_postprocessor_context(
    user_query: str,
    *,
    llm_generated: bool,
) -> dict[str, Any]:
    bindings = build_user_constraint_bindings(user_query)
    user_index = str(bindings.normalized_slots.get("index") or "").strip()
    if not user_index and bindings.explicit_indexes:
        user_index = str(bindings.explicit_indexes[0]).strip()

    profile = load_persisted_source_profile()
    source_profile_index = str(profile.get("index") or "").strip()

    user_time = bool(
        bindings.normalized_slots.get("earliest")
        or bindings.normalized_slots.get("latest")
        or bindings.explicit_time_window
    )

    return {
        "is_explicit_spl_authoring": True,
        "is_universal_spl": True,
        "is_template_free": True,
        "llm_generated": llm_generated,
        "deterministic_generated": not llm_generated,
        "execution_authorized": False,
        "user_explicit_index": user_index or None,
        "source_profile_index": source_profile_index or None,
        "user_explicit_time_window": user_time,
    }


def attempt_bounded_utility_spl_llm_draft(
    user_query: str,
    *,
    llm_raw_output_provider: Callable[[], str] | None = None,
    timeout_seconds: float | None = None,
) -> tuple[Any | None, dict[str, Any]]:
    effective_timeout = (
        float(timeout_seconds)
        if timeout_seconds is not None
        else utility_spl_draft_timeout_seconds()
    )
    failover_enabled = utility_spl_draft_failover_enabled()
    trace: dict[str, Any] = {
        "llm_spl_draft_requested": True,
        "llm_spl_draft_completed": False,
        "llm_spl_draft_timed_out": False,
        "llm_spl_draft_used": False,
        "llm_spl_draft_dropped_reason": None,
        "budget_reallocated_to_spl_drafting": True,
        "utility_spl_draft_timeout_seconds": effective_timeout,
        "utility_spl_draft_failover_enabled": failover_enabled,
    }

    if not utility_spl_draft_enabled():
        trace["llm_spl_draft_requested"] = False
        trace["llm_spl_draft_dropped_reason"] = "utility_spl_draft_disabled"
        return None, trace

    if llm_raw_output_provider is not None:
        result = generate_llm_spl_fallback(
            user_query=user_query,
            utility_authoring=True,
            llm_raw_output_provider=llm_raw_output_provider,
        )
        if result is None or result.clarification_required or not result.candidate_spl.strip():
            trace["llm_spl_draft_dropped_reason"] = (
                result.clarification_reason if result else "llm_spl_fallback_unavailable"
            )
            return None, trace
        trace["llm_spl_draft_completed"] = True
        trace["llm_spl_draft_used"] = True
        return result, trace

    if not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        trace["llm_spl_draft_dropped_reason"] = "llm_disabled"
        trace["llm_spl_draft_requested"] = False
        return None, trace

    system_prompt, user_prompt = spl_advisory_prompts(user_query, utility_authoring=True)
    raw_output, timed_out, _label = invoke_sidecar_role(
        role=SPL_ADVISORY_ROLE,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=768,
        timeout_seconds=effective_timeout,
        temperature=0.0,
        allow_failover=failover_enabled,
    )
    if timed_out:
        trace["llm_spl_draft_timed_out"] = True
        trace["llm_spl_draft_dropped_reason"] = "llm_timed_out"
        return None, trace
    if not raw_output:
        trace["llm_spl_draft_dropped_reason"] = "no_provider_configured"
        return None, trace

    result = generate_llm_spl_fallback(
        user_query=user_query,
        utility_authoring=True,
        llm_raw_output_provider=lambda: raw_output,
    )
    if result is None or result.clarification_required or not result.candidate_spl.strip():
        trace["llm_spl_draft_dropped_reason"] = (
            result.clarification_reason if result else "llm_spl_fallback_parse_failed"
        )
        return None, trace

    trace["llm_spl_draft_completed"] = True
    trace["llm_spl_draft_used"] = True
    return result, trace


def _deterministic_universal_skeleton(
    user_query: str,
    *,
    llm_intent_advisory: Any | None = None,
) -> dict[str, Any] | None:
    draft = build_draft_preview(
        user_query,
        live_data_request=True,
        llm_intent_advisory=llm_intent_advisory,
        query_understanding=None,
    )
    if not draft or draft.get("detection_family") != "universal_timestamp_spl":
        return None
    spl = str(draft.get("draft_spl") or "").strip()
    if not spl:
        return None
    return draft


def candidate_from_universal_utility_authoring(
    *,
    trace_id: str,
    skill: str,
    user_query: str,
    telemetry: Any,
    profile: Any,
    spl_governance: dict[str, Any] | None,
    llm_intent_advisory: Any | None = None,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    draft = _deterministic_universal_skeleton(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
    )
    if draft is None:
        return None

    skeleton_spl = str(draft["draft_spl"])
    spl_draft_trace: dict[str, Any] = {
        "deterministic_skeleton_available": True,
        "deterministic_skeleton_used": False,
        "final_raw_spl_source": "deterministic_skeleton",
        "final_spl_authority": "deterministic_postprocessor",
        "postprocessor_applied": False,
    }

    llm_result, llm_trace = attempt_bounded_utility_spl_llm_draft(
        user_query,
        llm_raw_output_provider=llm_raw_output_provider,
    )
    spl_draft_trace.update(llm_trace)

    if llm_result is not None and llm_result.candidate_spl.strip():
        raw_spl = llm_result.candidate_spl.strip()
        spl_draft_trace["final_raw_spl_source"] = "llm_draft"
        spl_draft_trace["deterministic_skeleton_used"] = False
        ctx = build_utility_postprocessor_context(user_query, llm_generated=True)
        normalized = normalize_review_only_spl(raw_spl, ctx)
        final_spl = normalized.normalized_spl
        postprocessor_trace = dict(normalized.trace)
        postprocessor_warnings = list(normalized.warnings)
    else:
        spl_draft_trace["deterministic_skeleton_used"] = True
        ctx = build_utility_postprocessor_context(user_query, llm_generated=False)
        normalized = normalize_review_only_spl(skeleton_spl, ctx)
        final_spl = normalized.normalized_spl
        postprocessor_trace = dict(normalized.trace)
        postprocessor_warnings = list(normalized.warnings)

    postprocessor_trace["postprocessor_applied"] = True
    postprocessor_trace.setdefault("final_spl_authority", "deterministic_postprocessor")
    spl_draft_trace["postprocessor_applied"] = True
    spl_draft_trace["review_only_spl_postprocessor_trace"] = postprocessor_trace

    lab_labels = {
        "governed": False,
        "catalog_approved": False,
        "execution_enabled": False,
        "execution_eligible": False,
        "review_required": True,
    }
    final_raw_spl_source = spl_draft_trace["final_raw_spl_source"]
    generation_mode = (
        "utility_llm_spl_draft" if final_raw_spl_source == "llm_draft" else "deterministic_lab_draft"
    )
    provider = (
        "utility_llm_spl_draft" if final_raw_spl_source == "llm_draft" else "deterministic_lab_draft"
    )

    candidate_payload: dict[str, Any] = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": generation_mode,
        "confidence": 0.55 if final_raw_spl_source == "llm_draft" else 0.5,
        "assumptions": list(draft.get("assumptions") or [])
        + (
            ["Bounded LLM SPL draft normalized by deterministic postprocessor — not executed."]
            if final_raw_spl_source == "llm_draft"
            else [
                "Deterministic lab SPL draft — not governed, not catalog-approved, not executable.",
            ]
        ),
        "warnings": ["review_only_universal_spl"],
        "selected_candidate_spl_provider": provider,
        "fallback_required": final_raw_spl_source == "deterministic_skeleton",
        "candidate_spl_generated": True,
        "validation_required": True,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": final_raw_spl_source == "llm_draft",
        "llm_fallback_status": "utility_llm_draft" if final_raw_spl_source == "llm_draft" else "lab_draft_fallback",
        "llm_fallback_reason": (
            "explicit_spl_authoring_utility_llm_draft"
            if final_raw_spl_source == "llm_draft"
            else "explicit_spl_authoring_deterministic_skeleton"
        ),
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "detection_family": "universal_timestamp_spl",
        "utility_spl_draft_trace": spl_draft_trace,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **lab_labels,
    }
    if postprocessor_warnings:
        candidate_payload["review_only_spl_postprocessor_warnings"] = postprocessor_warnings

    validation_payload: dict[str, Any] = {
        "approved": False,
        "normalized_spl": None,
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "reject_reasons": ["universal_spl_authoring_review_only"],
        "review_required_reason": "universal_spl_authoring_review_only",
        "warnings": ["review_only_universal_spl"],
        "enforced_limits": validate_spl("").get("enforced_limits") or {},
        "policy_version": validate_spl("").get("policy_version"),
        "selected_candidate_spl_provider": provider,
        "candidate_provider_reason": candidate_payload["llm_fallback_reason"],
        "saia_available": False,
        "fallback_required": candidate_payload["fallback_required"],
        "spl_explanation_provider": "rule_based",
        "spl_optimization_provider": "rule_based",
        "spl_guidance_provider": "scd_rag",
        "optimization_applied": False,
        "optimization_revalidation_status": None,
        "optimization_revalidation_approved": False,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": candidate_payload["llm_fallback_used"],
        "llm_fallback_status": candidate_payload["llm_fallback_status"],
        "llm_fallback_reason": candidate_payload["llm_fallback_reason"],
        "utility_spl_draft_trace": spl_draft_trace,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **lab_labels,
    }

    from app.chat.pipeline import _mark_spl_review_status, _merge_spl_governance

    _merge_spl_governance(candidate_payload, validation_payload, spl_governance)
    _mark_spl_review_status(candidate_payload, validation_payload)

    telemetry.record_step(
        trace_id,
        "candidate_spl_generated",
        "completed",
        skill=skill,
        generation_mode=generation_mode,
        confidence=candidate_payload["confidence"],
        warnings=candidate_payload["warnings"],
        selected_candidate_spl_provider=provider,
        fallback_required=candidate_payload["fallback_required"],
        final_raw_spl_source=final_raw_spl_source,
    )
    telemetry.record_spl_validation(
        trace_id,
        stage="spl_validation_result",
        approved=False,
        reject_reasons=validation_payload["reject_reasons"],
        warnings=validation_payload["warnings"],
        policy_version=validation_payload.get("policy_version"),
    )
    return candidate_payload, validation_payload
