"""Budgeted LLM SPL drafting for universal utility authoring (PR #58).

Reuses ``spl_advisory_generator`` / ``generate_llm_spl_fallback`` with a bounded
hop, deterministic skeleton fallback, and the existing review-only postprocessor.
"""

from __future__ import annotations

import time
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
from app.spl.review_only_spl_postprocessor import finalize_review_only_spl
from app.spl.source_profile_bindings import build_source_profile_binding_slots
from app.spl.source_profile_store import (
    load_persisted_source_profile,
    load_persisted_source_profile_document,
)
from app.spl.user_constraint_bindings import build_user_constraint_bindings


def _single_approved_profile_index(profile: dict[str, str]) -> str | None:
    indexes = {
        str(value).strip()
        for key, value in profile.items()
        if str(key).endswith("_index") and str(value).strip()
    }
    if len(indexes) == 1:
        return next(iter(indexes))
    return None


def _explicit_generic_utility_index(profile: dict[str, str]) -> tuple[str | None, str | None]:
    configured = str(settings.ai_soc_utility_spl_default_index or "").strip()
    if configured:
        return configured, "coe_generic_utility_default"
    for key in ("utility_spl_default_index", "generic_utility_default_index"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value, "coe_generic_utility_default"
    return None, None


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
    target_log_family: str | None = "universal_timestamp_spl",
    is_universal_spl: bool = True,
) -> dict[str, Any]:
    bindings = build_user_constraint_bindings(user_query)
    user_index = str(bindings.normalized_slots.get("index") or "").strip()
    if not user_index and bindings.explicit_indexes:
        user_index = str(bindings.explicit_indexes[0]).strip()
    user_sourcetype = str(bindings.normalized_slots.get("sourcetype") or "").strip()

    profile_doc = load_persisted_source_profile_document()
    profile = load_persisted_source_profile()
    contextual_bindings = build_source_profile_binding_slots(user_query)
    coe_contextual_index = str(contextual_bindings.slots.get("index") or "").strip()
    source_profile_index = str(profile.get("index") or "").strip()
    if not source_profile_index:
        source_profile_index = _single_approved_profile_index(profile) or ""
    utility_default_index, utility_default_source = _explicit_generic_utility_index(profile)

    user_time = bool(
        bindings.normalized_slots.get("earliest")
        or bindings.normalized_slots.get("latest")
        or bindings.explicit_time_window
    )

    return {
        "is_explicit_spl_authoring": True,
        "is_universal_spl": is_universal_spl,
        "is_template_free": True,
        "llm_generated": llm_generated,
        "deterministic_generated": not llm_generated,
        "execution_authorized": False,
        "user_explicit_index": user_index or None,
        "user_explicit_sourcetype": user_sourcetype or None,
        "coe_environment_index": coe_contextual_index or None,
        "source_profile_index": source_profile_index or None,
        "source_profile_sourcetype": str(profile.get("sourcetype") or "").strip() or None,
        "coe_generic_utility_default_sourcetype": str(
            profile.get("utility_spl_default_sourcetype") or ""
        ).strip()
        or None,
        "coe_generic_utility_default_index": utility_default_index,
        "coe_generic_utility_default_source": utility_default_source,
        "source_profile_resolution_trace": {
            "contextual_bindings": contextual_bindings.trace(),
            "single_approved_index_used": bool(source_profile_index)
            and not coe_contextual_index
            and not str(profile.get("index") or "").strip(),
            "source_profile_updated_at": profile_doc.get("updated_at"),
        },
        "user_explicit_time_window": user_time,
        "target_log_family": target_log_family,
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
        "llm_spl_draft_enabled": utility_spl_draft_enabled(),
        "llm_spl_draft_requested": True,
        "llm_spl_draft_completed": False,
        "llm_spl_draft_timed_out": False,
        "llm_spl_draft_used": False,
        "llm_spl_draft_dropped_reason": None,
        "llm_spl_draft_skipped_reason": None,
        "llm_spl_draft_provider_label": None,
        "budget_reallocated_to_spl_drafting": True,
        "utility_spl_draft_timeout_seconds": effective_timeout,
        "utility_spl_draft_failover_enabled": failover_enabled,
    }

    if not utility_spl_draft_enabled():
        trace["llm_spl_draft_requested"] = False
        trace["llm_spl_draft_dropped_reason"] = "utility_spl_draft_disabled"
        trace["llm_spl_draft_skipped_reason"] = "utility_spl_draft_disabled"
        return None, trace

    if llm_raw_output_provider is not None:
        started = time.monotonic()
        result = generate_llm_spl_fallback(
            user_query=user_query,
            utility_authoring=True,
            llm_raw_output_provider=llm_raw_output_provider,
        )
        trace["llm_spl_draft_latency_ms"] = int((time.monotonic() - started) * 1000)
        if result is None or result.clarification_required or not result.candidate_spl.strip():
            trace["llm_spl_draft_dropped_reason"] = (
                result.clarification_reason if result else "llm_spl_fallback_unavailable"
            )
            trace["llm_spl_draft_skipped_reason"] = trace["llm_spl_draft_dropped_reason"]
            return None, trace
        trace["llm_spl_draft_completed"] = True
        trace["llm_spl_draft_used"] = True
        return result, trace

    if not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        trace["llm_spl_draft_dropped_reason"] = "llm_disabled"
        trace["llm_spl_draft_skipped_reason"] = "llm_disabled"
        trace["llm_spl_draft_requested"] = False
        return None, trace

    system_prompt, user_prompt = spl_advisory_prompts(user_query, utility_authoring=True)
    started = time.monotonic()
    raw_output, timed_out, _label = invoke_sidecar_role(
        role=SPL_ADVISORY_ROLE,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=768,
        timeout_seconds=effective_timeout,
        temperature=0.0,
        allow_failover=failover_enabled,
    )
    trace["llm_spl_draft_latency_ms"] = int((time.monotonic() - started) * 1000)
    trace["llm_spl_draft_provider_label"] = _label
    if timed_out:
        trace["llm_spl_draft_timed_out"] = True
        trace["llm_spl_draft_dropped_reason"] = "llm_timed_out"
        trace["llm_spl_draft_skipped_reason"] = "llm_timed_out"
        return None, trace
    if not raw_output:
        trace["llm_spl_draft_dropped_reason"] = "no_provider_configured"
        trace["llm_spl_draft_skipped_reason"] = "no_provider_configured"
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
        trace["llm_spl_draft_skipped_reason"] = trace["llm_spl_draft_dropped_reason"]
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


def _utility_assumptions(
    *,
    postprocessor_trace: dict[str, Any],
    final_raw_spl_source: str,
) -> list[str]:
    resolved_index = str(postprocessor_trace.get("resolved_index") or "").strip()
    resolution_source = str(postprocessor_trace.get("index_resolution_source") or "").strip()
    if resolution_source == "placeholder" or not resolved_index or resolved_index == "<your_index>":
        index_note = (
            "Universal/template-free review-only SPL using a <your_index> placeholder; "
            "not tied to a company template registry."
        )
        window_note = (
            "Replace <your_index> and adjust the time window to your environment before any future execution review."
        )
    else:
        index_note = (
            f"Universal/template-free review-only SPL using COE-resolved index `{resolved_index}`; "
            "not tied to a company template registry."
        )
        window_note = "Adjust `earliest`/`latest` to your review time window before any future execution review."

    source_note = (
        "Bounded LLM SPL draft normalized by deterministic postprocessor; not executed."
        if final_raw_spl_source == "llm_draft"
        else "Deterministic lab SPL draft normalized by deterministic postprocessor; not executed."
    )
    return [
        index_note,
        "Splunk %w (0=Sunday, 6=Saturday) drives the weekend filter; %A (day name) is display only.",
        window_note,
        source_note,
    ]


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
    llm_turn_budget: Any | None = None,
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
    if llm_turn_budget is not None and spl_draft_trace.get("llm_spl_draft_requested"):
        outcome = "completed" if spl_draft_trace.get("llm_spl_draft_completed") else "dropped"
        if spl_draft_trace.get("llm_spl_draft_timed_out"):
            outcome = "timed_out"
        record = getattr(llm_turn_budget, "record_sidecar", None)
        if callable(record):
            record(
                role=SPL_ADVISORY_ROLE,
                provider_label=spl_draft_trace.get("llm_spl_draft_provider_label"),
                outcome=outcome,
                latency_ms=spl_draft_trace.get("llm_spl_draft_latency_ms"),
            )

    if llm_result is not None and llm_result.candidate_spl.strip():
        raw_spl = llm_result.candidate_spl.strip()
        spl_draft_trace["final_raw_spl_source"] = "llm_draft"
        spl_draft_trace["deterministic_skeleton_used"] = False
        ctx = build_utility_postprocessor_context(user_query, llm_generated=True)
        normalized = finalize_review_only_spl(
            raw_spl,
            query=user_query,
            family="universal_timestamp_spl",
            llm_generated=True,
            postprocessor_context=ctx,
        )
        final_spl = normalized.normalized_spl
        postprocessor_trace = dict(normalized.trace)
        postprocessor_warnings = list(normalized.warnings)
    else:
        spl_draft_trace["deterministic_skeleton_used"] = True
        ctx = build_utility_postprocessor_context(user_query, llm_generated=False)
        normalized = finalize_review_only_spl(
            skeleton_spl,
            query=user_query,
            family="universal_timestamp_spl",
            llm_generated=False,
            postprocessor_context=ctx,
        )
        final_spl = normalized.normalized_spl
        postprocessor_trace = dict(normalized.trace)
        postprocessor_warnings = list(normalized.warnings)

    postprocessor_trace.setdefault("final_spl_authority", "deterministic_postprocessor")
    spl_draft_trace["final_spl_authority"] = postprocessor_trace.get("final_spl_authority")
    spl_draft_trace["postprocessor_applied"] = bool(postprocessor_trace.get("postprocessor_applied"))
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
        "assumptions": _utility_assumptions(
            postprocessor_trace=postprocessor_trace,
            final_raw_spl_source=final_raw_spl_source,
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
