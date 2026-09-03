"""Budgeted LLM SPL drafting for universal utility authoring (PR #58).

Reuses ``spl_advisory_generator`` / ``generate_llm_spl_fallback`` with a bounded
hop, deterministic skeleton fallback, and the existing review-only postprocessor.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from app.config import settings
from app.chat.llm_interaction_trace import annotate_last_llm_interaction
from app.safeguards.spl_validator import validate_spl, validate_spl_lab_candidate
from app.spl.draft_preview import build_draft_preview
from app.spl.llm_fallback import (
    AUTHORING_SOURCE_ABSTAIN,
    AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE,
    AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED,
    AUTHORING_SOURCE_LLM_PATTERN_PRIMARY,
    AUTHORING_SOURCE_LLM_PATTERN_REPAIR,
    SPL_ADVISORY_ROLE,
    generate_llm_spl_fallback,
    select_vetted_authoring_pattern,
)
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.review_only_spl_postprocessor import finalize_review_only_spl
from app.spl.source_profile_catalog import list_source_profile_slot_definitions
from app.spl.source_profile_bindings import (
    build_source_profile_binding_slots,
    source_mappings_for_query,
)
from app.spl.source_profile_store import (
    load_persisted_source_profile,
    load_persisted_source_profile_document,
)
from app.spl.spl_intent_spec import build_spl_intent_spec, spl_intent_spec_for_prompt
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity
from app.spl.user_constraint_bindings import build_user_constraint_bindings


def _configured_profile_indexes(profile: dict[str, str]) -> set[str]:
    configured_index_slots = {
        str(item.get("slot_id") or "").strip()
        for item in list_source_profile_slot_definitions()
        if str(item.get("category") or "").strip() in {"index", "ot_index", "cisco_index"}
    }
    return {
        str(value).strip()
        for key, value in profile.items()
        if str(key).strip() in configured_index_slots and str(value).strip()
    }


def _single_approved_profile_index(profile: dict[str, str]) -> str | None:
    indexes = _configured_profile_indexes(profile)
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


def _policy_default_index() -> str | None:
    configured = [item.strip() for item in str(settings.spl_allowed_indexes or "").split(",") if item.strip()]
    if configured:
        return configured[0]
    return None


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
    allow_global_index_inference: bool | None = None,
) -> dict[str, Any]:
    bindings = build_user_constraint_bindings(user_query)
    user_index = str(bindings.normalized_slots.get("index") or "").strip()
    if not user_index and bindings.explicit_indexes:
        user_index = str(bindings.explicit_indexes[0]).strip()
    user_sourcetype = str(bindings.normalized_slots.get("sourcetype") or "").strip()
    user_time_window = (
        str(bindings.explicit_time_window or "").strip()
        or str(bindings.normalized_slots.get("time_window") or "").strip()
        or None
    )

    profile_doc = load_persisted_source_profile_document()
    profile = load_persisted_source_profile()
    contextual_bindings = build_source_profile_binding_slots(user_query)
    coe_contextual_index = str(contextual_bindings.slots.get("index") or "").strip()
    source_profile_index = str(profile.get("index") or "").strip()
    if allow_global_index_inference is None:
        allow_global_index_inference = is_universal_spl
    if not source_profile_index and allow_global_index_inference:
        source_profile_index = _single_approved_profile_index(profile) or ""
    if not source_profile_index and not is_universal_spl:
        # Non-universal lab drafts never attempt single-index inference above
        # (decoupled from the global heuristic); always give them a policy
        # default so generic <index> placeholders stay renderable.
        source_profile_index = _policy_default_index() or ""
    elif not source_profile_index and is_universal_spl and len(_configured_profile_indexes(profile)) > 1:
        # Universal drafts did attempt single-index inference above and came
        # up ambiguous (COE has *multiple* real indexes configured) — fall
        # back to a sensible policy default rather than a bare placeholder.
        # But if COE has configured *nothing* at all (zero index slots), stay
        # as an explicit <your_index> placeholder instead of guessing.
        source_profile_index = _policy_default_index() or ""
    utility_default_index, utility_default_source = _explicit_generic_utility_index(profile)

    user_time = bool(
        bindings.normalized_slots.get("earliest")
        or bindings.normalized_slots.get("latest")
        or bindings.explicit_time_window
        or bindings.normalized_slots.get("time_window")
        or user_time_window
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
        "user_explicit_time_bounds": user_time_window,
        "target_log_family": target_log_family,
    }


from app.spl.spl_provenance_trace import spl_artifact_source


_REPAIRABLE_VALIDATOR_REASONS = frozenset({
    "missing_aggregation",
    "disallowed_index",
    "missing_result_limit",
    "missing_time_bound",
    "blocked_command",
})
MAX_SPL_LLM_REPAIRS = 1
_HARD_AUTHORING_FAILURE_STAGES = frozenset(
    {
        "json_parse",
        "schema_validation",
        "content_validation",
        "draft_quality",
        "semantic_validation",
    }
)


def _copy_authoring_diagnostics(trace: dict[str, Any], result: Any | None) -> None:
    if result is None:
        return
    for attr in (
        "authoring_failure_stage",
        "authoring_failure_code",
        "authoring_failure_field",
        "finish_reason",
        "rejected_candidate_spl",
        "quality_findings",
        "quality_status",
        "hard_fail_count",
    ):
        value = getattr(result, attr, None)
        if value:
            trace[attr] = value


def _is_generic_lab_skeleton(spl: str) -> bool:
    """True for the non-semantic placeholder skeleton that must not masquerade as an answer."""
    normalized = " ".join(str(spl or "").lower().split())
    if "stats" in normalized or "timechart" in normalized or "tstats" in normalized:
        return False
    return (
        "| where 1=1" in normalized
        and "| table _time" in normalized
        and "| head 100" in normalized
    )


def _semantic_repair_feedback(
    validation: dict[str, Any],
    *,
    fidelity: dict[str, Any] | None = None,
) -> list[str]:
    reasons = validation.get("reject_reasons") or []
    if not isinstance(reasons, list):
        feedback: list[str] = []
    else:
        repairable = [str(item) for item in reasons if str(item) in _REPAIRABLE_VALIDATOR_REASONS]
        feedback = [f"validator_reject:{reason}" for reason in repairable]
    if isinstance(fidelity, dict):
        feedback.extend(str(item) for item in (fidelity.get("repair_feedback") or []))
    return feedback


def _build_authoring_intent_spec(
    user_query: str,
    *,
    resolved_query_contract: dict[str, Any] | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    mappings = source_mappings_for_query(user_query, family_id=family)
    rqc = resolved_query_contract if isinstance(resolved_query_contract, dict) else None
    return build_spl_intent_spec(
        user_query,
        resolved_query_contract=rqc,
        source_mappings=mappings,
    )


def _build_utility_llm_context(
    user_query: str,
    *,
    family: str | None,
    resolved_query_contract: dict[str, Any] | None = None,
    intent_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = intent_spec or _build_authoring_intent_spec(
        user_query,
        resolved_query_contract=resolved_query_contract,
        family=family,
    )
    ctx = build_utility_postprocessor_context(
        user_query,
        llm_generated=True,
        target_log_family=family,
        is_universal_spl=family == "universal_timestamp_spl",
    )
    bindings: dict[str, str] = {}
    for key in ("user_explicit_index", "user_explicit_sourcetype", "source_profile_index", "source_profile_sourcetype", "coe_environment_index"):
        value = str(ctx.get(key) or "").strip()
        if value:
            bindings[key] = value
    time_window = spec.get("search_horizon") or spec.get("time_window")
    if time_window:
        bindings["time_window"] = str(time_window)
    source = spec.get("source_constraints") if isinstance(spec.get("source_constraints"), dict) else {}
    for key in ("index", "sourcetype"):
        value = str(source.get(key) or "").strip()
        if value and key not in bindings:
            bindings[key] = value
    user_time = bool(ctx.get("user_explicit_time_window") or time_window)
    return {
        "review_only_posture": True,
        "do_not_invent_source_bindings": True,
        "flag_uncertain_field_mappings": True,
        "do_not_reinterpret_request": True,
        "deterministic_source_bindings": bindings,
        "semantic_analyst_intent": spec,
        "semantic_analyst_intent_text": spl_intent_spec_for_prompt(spec),
        "target_log_family": family,
        "user_explicit_time_window": user_time,
        "resolved_query_contract": resolved_query_contract,
    }


def _validate_review_only_candidate(spl: str) -> dict[str, Any]:
    return validate_spl_lab_candidate(spl)


def attempt_bounded_utility_spl_llm_draft(
    user_query: str,
    *,
    llm_raw_output_provider: Callable[[], str] | None = None,
    timeout_seconds: float | None = None,
    context: dict[str, Any] | None = None,
    relevance_feedback: list[str] | None = None,
    repair_attempt: bool = False,
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
        "utility_spl_repair_attempt": repair_attempt,
    }
    if repair_attempt:
        prior = 0
        if isinstance(context, dict):
            try:
                prior = int(context.get("repair_attempt_count") or 1)
            except (TypeError, ValueError):
                prior = 1
        if prior > MAX_SPL_LLM_REPAIRS:
            trace["llm_spl_draft_dropped_reason"] = "more_than_one_repair"
            trace["llm_spl_draft_skipped_reason"] = "more_than_one_repair"
            return None, trace
        trace["repair_attempt_count"] = min(prior, MAX_SPL_LLM_REPAIRS)

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
            context=context,
            relevance_feedback=relevance_feedback,
        )
        trace["llm_spl_draft_latency_ms"] = int((time.monotonic() - started) * 1000)
        if result is None or result.clarification_required or not result.candidate_spl.strip():
            _copy_authoring_diagnostics(trace, result)
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

    started = time.monotonic()
    result = generate_llm_spl_fallback(
        user_query=user_query,
        utility_authoring=True,
        context=context,
        relevance_feedback=relevance_feedback,
    )
    trace["llm_spl_draft_latency_ms"] = int((time.monotonic() - started) * 1000)
    if result is not None:
        trace["llm_spl_draft_provider_label"] = result.model or result.provider
    if result is None or result.clarification_required or not result.candidate_spl.strip():
        _copy_authoring_diagnostics(trace, result)
        trace["llm_spl_draft_dropped_reason"] = (
            result.clarification_reason if result else "llm_spl_fallback_unavailable"
        )
        trace["llm_spl_draft_skipped_reason"] = trace["llm_spl_draft_dropped_reason"]
        if result and result.adapter_errors:
            trace["llm_spl_draft_adapter_errors"] = list(result.adapter_errors)[:8]
        return None, trace

    trace["llm_spl_draft_completed"] = True
    trace["llm_spl_draft_used"] = True
    return result, trace


def _deterministic_utility_skeleton(
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
    if not draft:
        return None
    spl = str(draft.get("draft_spl") or "").strip()
    if not spl:
        return None
    return draft


def _deterministic_universal_skeleton(
    user_query: str,
    *,
    llm_intent_advisory: Any | None = None,
) -> dict[str, Any] | None:
    draft = _deterministic_utility_skeleton(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
    )
    if not draft or draft.get("detection_family") != "universal_timestamp_spl":
        return None
    return draft


def _utility_assumptions(
    *,
    postprocessor_trace: dict[str, Any],
    final_raw_spl_source: str,
    intent_spec: dict[str, Any] | None = None,
) -> list[str]:
    resolved_index = str(postprocessor_trace.get("resolved_index") or "").strip()
    resolution_source = str(postprocessor_trace.get("index_resolution_source") or "").strip()
    shape = str((intent_spec or {}).get("analysis_shape") or "")
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
        if final_raw_spl_source in {"llm_draft", "llm_repair"}
        else "Deterministic lab SPL draft normalized by deterministic postprocessor; not executed."
    )
    notes = [index_note]
    if shape not in {"first_seen", "sequence", "parent_child"}:
        notes.append(
            "Splunk %w (0=Sunday, 6=Saturday) drives the weekend filter; %A (day name) is display only."
        )
    notes.extend([window_note, source_note])
    return notes


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
    resolved_query_contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    draft = _deterministic_utility_skeleton(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
    )
    if draft is None:
        return None

    skeleton_spl = str(draft["draft_spl"])
    detection_family = str(draft.get("detection_family") or "lab_draft")
    is_universal = detection_family == "universal_timestamp_spl"
    intent_spec = _build_authoring_intent_spec(
        user_query,
        resolved_query_contract=resolved_query_contract,
        family=detection_family,
    )
    llm_context = _build_utility_llm_context(
        user_query,
        family=detection_family,
        resolved_query_contract=resolved_query_contract,
        intent_spec=intent_spec,
    )
    spl_draft_trace: dict[str, Any] = {
        "deterministic_skeleton_available": True,
        "deterministic_skeleton_used": False,
        "final_raw_spl_source": "deterministic_skeleton",
        "final_spl_authority": "deterministic_postprocessor",
        "postprocessor_applied": False,
        "bounded_repair_attempted": False,
        "bounded_repair_used": False,
        "semantic_intent_spec": intent_spec,
        "legacy_compiler_rescue": False,
    }
    pattern = select_vetted_authoring_pattern(intent_spec)
    if pattern:
        spl_draft_trace["pattern_id"] = str(pattern.get("pattern_id") or "")
        spl_draft_trace["pattern_selected"] = True
        spl_draft_trace["pattern_example_id"] = str(pattern.get("example_id") or "")

    llm_result, llm_trace = attempt_bounded_utility_spl_llm_draft(
        user_query,
        llm_raw_output_provider=llm_raw_output_provider,
        context=llm_context,
    )
    spl_draft_trace.update(llm_trace)
    rejected_raw = str(spl_draft_trace.get("rejected_candidate_spl") or "").strip()
    if rejected_raw and not str(spl_draft_trace.get("raw_llm_spl") or "").strip():
        spl_draft_trace["raw_llm_spl"] = rejected_raw[:8000]
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

    final_raw_spl_source = "deterministic_skeleton"
    repair_used = False
    validator_result: dict[str, Any] = {}
    postprocessor_trace: dict[str, Any] = {}
    postprocessor_warnings: list[str] = []
    final_spl = skeleton_spl
    fidelity_result: dict[str, Any] | None = None

    def _apply_candidate(raw_spl: str, *, llm_generated: bool) -> str:
        nonlocal postprocessor_trace, postprocessor_warnings
        ctx = build_utility_postprocessor_context(
            user_query,
            llm_generated=llm_generated,
            target_log_family=detection_family,
            is_universal_spl=is_universal,
        )
        ctx["semantic_analyst_intent"] = intent_spec
        normalized = finalize_review_only_spl(
            raw_spl,
            query=user_query,
            family=detection_family,
            llm_generated=llm_generated,
            postprocessor_context=ctx,
        )
        postprocessor_trace = dict(normalized.trace)
        postprocessor_warnings = list(normalized.warnings)
        return normalized.normalized_spl

    if llm_result is not None and llm_result.candidate_spl.strip():
        final_raw_spl_source = "llm_draft"
        spl_draft_trace["deterministic_skeleton_used"] = False
        raw_llm_spl = llm_result.candidate_spl.strip()
        spl_draft_trace["raw_llm_spl"] = raw_llm_spl[:8000]
        spl_draft_trace["preprocessor_input"] = raw_llm_spl[:8000]
        final_spl = _apply_candidate(raw_llm_spl, llm_generated=True)
        spl_draft_trace["preprocessor_changes"] = list(postprocessor_trace.get("changes") or [])
        spl_draft_trace["normalized_llm_spl"] = final_spl[:8000]
        validator_result = _validate_review_only_candidate(final_spl)
        fidelity_result = validate_semantic_fidelity(intent_spec, final_spl)
        spl_draft_trace["semantic_fidelity_initial"] = fidelity_result
        repair_feedback = _semantic_repair_feedback(validator_result, fidelity=fidelity_result)
        if (repair_feedback and not validator_result.get("lab_candidate_eligible")) or (
            not fidelity_result.get("passed") and repair_feedback
        ):
            spl_draft_trace["bounded_repair_attempted"] = True
            spl_draft_trace["repair_attempt_count"] = 1
            spl_draft_trace["max_spl_llm_repairs"] = MAX_SPL_LLM_REPAIRS
            spl_draft_trace["repair_feedback"] = list(repair_feedback)
            repair_context = {
                **llm_context,
                "previous_rejected_candidate": final_spl,
                "deterministic_losses": list(fidelity_result.get("losses") or []),
                "repair_scope": "syntax_and_declared_semantic_losses_only",
                "do_not_reinterpret_request": True,
                "immutable_semantic_contract": intent_spec,
                "repair_attempt_count": 1,
            }
            repair_result, repair_trace = attempt_bounded_utility_spl_llm_draft(
                user_query,
                llm_raw_output_provider=llm_raw_output_provider,
                context=repair_context,
                relevance_feedback=repair_feedback,
                repair_attempt=True,
            )
            spl_draft_trace["bounded_repair_trace"] = repair_trace
            if llm_turn_budget is not None and repair_trace.get("llm_spl_draft_requested"):
                outcome = "completed" if repair_trace.get("llm_spl_draft_completed") else "dropped"
                if repair_trace.get("llm_spl_draft_timed_out"):
                    outcome = "timed_out"
                record = getattr(llm_turn_budget, "record_sidecar", None)
                if callable(record):
                    record(
                        role=SPL_ADVISORY_ROLE,
                        provider_label=repair_trace.get("llm_spl_draft_provider_label"),
                        outcome=outcome,
                        latency_ms=repair_trace.get("llm_spl_draft_latency_ms"),
                    )
            if repair_result is not None and repair_result.candidate_spl.strip():
                repaired_spl = _apply_candidate(repair_result.candidate_spl.strip(), llm_generated=True)
                repaired_validation = _validate_review_only_candidate(repaired_spl)
                repaired_fidelity = validate_semantic_fidelity(intent_spec, repaired_spl)
                spl_draft_trace["semantic_fidelity_repair"] = repaired_fidelity
                original_rejects = len(list(validator_result.get("reject_reasons") or []))
                repaired_rejects = len(list(repaired_validation.get("reject_reasons") or []))
                fidelity_improved = bool(repaired_fidelity.get("passed")) and not fidelity_result.get("passed")
                if (
                    repaired_validation.get("lab_candidate_eligible")
                    or repaired_rejects < original_rejects
                    or fidelity_improved
                ):
                    repair_used = True
                    final_raw_spl_source = "llm_repair"
                    spl_draft_trace["bounded_repair_used"] = True
                    spl_draft_trace["repaired_spl"] = repaired_spl[:8000]
                    final_spl = repaired_spl
                    validator_result = repaired_validation
                    fidelity_result = repaired_fidelity
    else:
        stage = str(spl_draft_trace.get("authoring_failure_stage") or "")
        if stage in _HARD_AUTHORING_FAILURE_STAGES:
            spl_draft_trace["deterministic_skeleton_used"] = False
            final_raw_spl_source = "abstention"
            final_spl = ""
            validator_result = _validate_review_only_candidate("")
            fidelity_result = {
                "passed": False,
                "preserved": [],
                "losses": ["authoring_validation_failed"],
                "repair_feedback": [],
                "structural_errors": [],
            }
            spl_draft_trace["semantic_fidelity_initial"] = fidelity_result
        else:
            skeleton_applied = _apply_candidate(skeleton_spl, llm_generated=False)
            skeleton_validation = _validate_review_only_candidate(skeleton_applied)
            raw_fidelity = validate_semantic_fidelity(intent_spec, skeleton_spl)
            skeleton_fidelity = validate_semantic_fidelity(intent_spec, skeleton_applied)
            spl_draft_trace["semantic_fidelity_initial"] = skeleton_fidelity
            skeleton_admissible = (
                not _is_generic_lab_skeleton(skeleton_spl)
                and not _is_generic_lab_skeleton(skeleton_applied)
                and bool(raw_fidelity.get("passed") or skeleton_fidelity.get("passed"))
            )
            if skeleton_admissible:
                spl_draft_trace["deterministic_skeleton_used"] = True
                final_raw_spl_source = "deterministic_skeleton"
                final_spl = skeleton_applied
                validator_result = skeleton_validation
                fidelity_result = (
                    skeleton_fidelity if skeleton_fidelity.get("passed") else raw_fidelity
                )
            else:
                compiled = compile_intent_spec_to_spl(intent_spec)
                if compiled.strip():
                    compiled_applied = _apply_candidate(compiled, llm_generated=False)
                    compiled_validation = _validate_review_only_candidate(compiled_applied)
                    compiled_fidelity = validate_semantic_fidelity(intent_spec, compiled_applied)
                    spl_draft_trace["semantic_fidelity_compiler"] = compiled_fidelity
                    if compiled_fidelity.get("passed"):
                        spl_draft_trace["deterministic_skeleton_used"] = False
                        spl_draft_trace["deterministic_compiler_used"] = True
                        spl_draft_trace["legacy_compiler_rescue"] = True
                        final_raw_spl_source = "deterministic_compiler"
                        final_spl = compiled_applied
                        validator_result = compiled_validation
                        fidelity_result = compiled_fidelity
                    else:
                        spl_draft_trace["deterministic_skeleton_used"] = False
                        final_raw_spl_source = "abstention"
                        final_spl = ""
                        validator_result = compiled_validation
                        fidelity_result = compiled_fidelity
                else:
                    spl_draft_trace["deterministic_skeleton_used"] = False
                    final_raw_spl_source = "abstention"
                    final_spl = ""
                    validator_result = skeleton_validation
                    fidelity_result = skeleton_fidelity

    if (
        str(intent_spec.get("support_status") or "") == "supported"
        and not intent_spec.get("unresolved_required_fields")
        and (
            not str(final_spl or "").strip()
            or (fidelity_result is not None and not fidelity_result.get("passed"))
        )
    ):
        compiled = compile_intent_spec_to_spl(intent_spec)
        if compiled.strip():
            compiled_applied = _apply_candidate(compiled, llm_generated=False)
            compiled_validation = _validate_review_only_candidate(compiled_applied)
            compiled_fidelity = validate_semantic_fidelity(intent_spec, compiled_applied)
            spl_draft_trace["semantic_fidelity_compiler"] = compiled_fidelity
            if compiled_fidelity.get("passed"):
                spl_draft_trace["deterministic_skeleton_used"] = False
                spl_draft_trace["deterministic_compiler_used"] = True
                spl_draft_trace["compiler_rescued_unfaithful_or_failed_llm"] = True
                spl_draft_trace["legacy_compiler_rescue"] = True
                final_raw_spl_source = "deterministic_compiler"
                final_spl = compiled_applied
                validator_result = compiled_validation
                fidelity_result = compiled_fidelity

    unavailable = False
    unavailable_reason: str | None = None
    semantic_fidelity_unresolved = False
    if final_raw_spl_source == "abstention" or (
        final_raw_spl_source == "deterministic_skeleton" and _is_generic_lab_skeleton(final_spl)
    ):
        unavailable = True
        unavailable_reason = (
            spl_draft_trace.get("authoring_failure_code")
            or spl_draft_trace.get("llm_spl_draft_dropped_reason")
            or "authoring_validation_failed"
        )
        final_spl = ""
        if fidelity_result is not None and not fidelity_result.get("passed"):
            semantic_fidelity_unresolved = True
            spl_draft_trace["semantic_fidelity_unresolved"] = True
            spl_draft_trace["lost_semantics"] = list(fidelity_result.get("losses") or [])
    elif fidelity_result is not None and not fidelity_result.get("passed"):
        semantic_fidelity_unresolved = True
        spl_draft_trace["semantic_fidelity_unresolved"] = True
        spl_draft_trace["lost_semantics"] = list(fidelity_result.get("losses") or [])
        unavailable = True
        unavailable_reason = "semantic_fidelity_unresolved"
        final_spl = ""


    postprocessor_trace.setdefault("final_spl_authority", "deterministic_postprocessor")
    spl_draft_trace["final_raw_spl_source"] = final_raw_spl_source
    spl_draft_trace["final_spl_authority"] = postprocessor_trace.get("final_spl_authority")
    spl_draft_trace["postprocessor_applied"] = bool(postprocessor_trace.get("postprocessor_applied"))
    spl_draft_trace["review_only_spl_postprocessor_trace"] = postprocessor_trace
    spl_draft_trace["validator_result"] = {
        "lab_candidate_eligible": bool(validator_result.get("lab_candidate_eligible")),
        "reject_reasons": list(validator_result.get("reject_reasons") or []),
    }
    spl_draft_trace["semantic_fidelity_final"] = fidelity_result
    spl_draft_trace["validation_losses"] = list((fidelity_result or {}).get("losses") or [])
    if unavailable:
        spl_draft_trace["unavailable_reason"] = unavailable_reason

    lab_labels = {
        "governed": False,
        "catalog_approved": False,
        "execution_enabled": False,
        "execution_eligible": False,
        "review_required": True,
    }
    if unavailable:
        generation_mode = "spl_authoring_unavailable"
        provider = "unavailable"
        final_spl = ""
        authoring_source = AUTHORING_SOURCE_ABSTAIN
    elif final_raw_spl_source == "llm_repair":
        generation_mode = "utility_llm_spl_repair"
        provider = "utility_llm_spl_repair"
        authoring_source = AUTHORING_SOURCE_LLM_PATTERN_REPAIR
    elif final_raw_spl_source == "llm_draft":
        generation_mode = "utility_llm_spl_draft"
        provider = "utility_llm_spl_draft"
        changes = list(
            spl_draft_trace.get("preprocessor_changes")
            or postprocessor_trace.get("changes")
            or []
        )
        authoring_source = (
            AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED
            if changes
            else AUTHORING_SOURCE_LLM_PATTERN_PRIMARY
        )
    elif final_raw_spl_source == "deterministic_compiler":
        generation_mode = "deterministic_compiler_draft"
        provider = "deterministic_compiler_draft"
        authoring_source = AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE
        spl_draft_trace["legacy_compiler_rescue"] = True
    else:
        generation_mode = "deterministic_lab_draft"
        provider = "deterministic_lab_draft"
        authoring_source = AUTHORING_SOURCE_ABSTAIN

    spl_draft_trace["authoring_source"] = authoring_source
    # Compiler rescue is never LLM pattern success, even if a draft existed.
    spl_draft_trace["llm_pattern_success"] = authoring_source in {
        AUTHORING_SOURCE_LLM_PATTERN_PRIMARY,
        AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED,
        AUTHORING_SOURCE_LLM_PATTERN_REPAIR,
    }
    reject_reasons = list(validator_result.get("reject_reasons") or [])
    llm_accepted = bool(spl_draft_trace["llm_pattern_success"])
    annotate_last_llm_interaction(
        SPL_ADVISORY_ROLE,
        quality_status=(
            "passed"
            if validator_result.get("lab_candidate_eligible")
            else "failed"
            if validator_result
            else "not_run"
        ),
        reject_reasons=reject_reasons,
        accepted=llm_accepted,
        contributed_to_final_output=llm_accepted,
        fallback_selected=not llm_accepted,
        fallback_reason=None if llm_accepted else (reject_reasons[0] if reject_reasons else None),
    )

    assumptions = _utility_assumptions(
        postprocessor_trace=postprocessor_trace,
        final_raw_spl_source=final_raw_spl_source,
        intent_spec=intent_spec,
    )
    if semantic_fidelity_unresolved and not unavailable:
        assumptions = [
            *assumptions,
            "Semantic fidelity unresolved — this draft does not fully satisfy the analyst ask.",
            *[
                f"Lost semantics: {item}"
                for item in list((fidelity_result or {}).get("losses") or [])[:8]
            ],
        ]
    if unavailable:
        assumptions = [
            "Unable to produce a validated review-only SPL for this request.",
            *[
                f"Unresolved: {reason}"
                for reason in list(validator_result.get("reject_reasons") or [])[:5]
            ],
            *(
                [f"LLM draft unavailable: {unavailable_reason.replace('_', ' ')}"]
                if unavailable_reason and unavailable_reason != "semantic_fidelity_unresolved"
                else []
            ),
            *(
                [
                    "Semantic fidelity unresolved after bounded repair; "
                    "unfaithful SPL is not presented as satisfied.",
                    *[
                        f"Lost semantics: {item}"
                        for item in list((fidelity_result or {}).get("losses") or [])[:8]
                    ],
                ]
                if semantic_fidelity_unresolved
                else []
            ),
        ]

    candidate_payload: dict[str, Any] = {
        "trace_id": trace_id,
        "skill": skill,
        "user_query": user_query,
        "candidate_spl": final_spl,
        "generation_mode": generation_mode,
        "authoring_source": authoring_source,
        "confidence": 0.55 if final_raw_spl_source in {"llm_draft", "llm_repair"} else 0.5,
        "assumptions": assumptions,
        "warnings": (
            ["semantic_fidelity_unresolved", "review_only_universal_spl"]
            if semantic_fidelity_unresolved and is_universal
            else ["semantic_fidelity_unresolved", "review_only_spl_authoring"]
            if semantic_fidelity_unresolved
            else ["review_only_universal_spl"]
            if is_universal
            else ["review_only_spl_authoring"]
        ),
        "selected_candidate_spl_provider": provider,
        "fallback_required": final_raw_spl_source == "deterministic_skeleton",
        "candidate_spl_generated": not unavailable,
        "validation_required": True,
        "capability_profile": profile.model_dump(),
        "template_id": None,
        "llm_supported": True,
        "llm_fallback_used": final_raw_spl_source in {"llm_draft", "llm_repair"},
        "llm_fallback_status": (
            "utility_llm_draft"
            if final_raw_spl_source == "llm_draft"
            else "utility_llm_repair"
            if final_raw_spl_source == "llm_repair"
            else "lab_draft_fallback"
        ),
        "llm_fallback_reason": (
            "explicit_spl_authoring_utility_llm_draft"
            if final_raw_spl_source == "llm_draft"
            else "explicit_spl_authoring_utility_llm_repair"
            if final_raw_spl_source == "llm_repair"
            else "explicit_spl_authoring_deterministic_compiler"
            if final_raw_spl_source == "deterministic_compiler"
            else "explicit_spl_authoring_deterministic_skeleton"
        ),
        "deterministic_fallback_reason": (
            spl_draft_trace.get("llm_spl_draft_dropped_reason")
            if final_raw_spl_source == "deterministic_skeleton"
            else None
        ),
        "spl_authoring_unavailable": unavailable,
        "spl_authoring_unavailable_reason": unavailable_reason,
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "detection_family": detection_family,
        "utility_spl_draft_trace": spl_draft_trace,
        "review_only_spl_postprocessor_trace": postprocessor_trace,
        **lab_labels,
    }
    if postprocessor_warnings:
        candidate_payload["review_only_spl_postprocessor_warnings"] = postprocessor_warnings

    reject_reasons = (
        ["spl_authoring_unavailable", "semantic_fidelity_unresolved"]
        if unavailable and semantic_fidelity_unresolved
        else ["spl_authoring_unavailable"]
        if unavailable
        else ["semantic_fidelity_unresolved", "universal_spl_authoring_review_only"]
        if semantic_fidelity_unresolved and is_universal
        else ["semantic_fidelity_unresolved", "review_only_spl_authoring"]
        if semantic_fidelity_unresolved
        else ["universal_spl_authoring_review_only"]
        if is_universal
        else ["review_only_spl_authoring"]
    )
    validation_payload: dict[str, Any] = {
        "approved": False,
        "normalized_spl": None,
        "exposure_tier": "lab_candidate",
        "lab_tier_exposure": True,
        "reject_reasons": reject_reasons,
        "review_required_reason": reject_reasons[0],
        "warnings": candidate_payload["warnings"],
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
        "spl_authoring_unavailable": unavailable,
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
