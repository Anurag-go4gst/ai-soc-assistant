"""Read-model projection for SPL artifact degrade-chain status (trace only)."""

from __future__ import annotations

from typing import Any

from app.spl.spl_provenance_trace import (
    build_spl_provenance_summary,
    fallback_reason,
    llm_failover_used_factual,
    spl_artifact_source,
)

_LAB_PREVIEW_MODES = frozenset({
    "deterministic_lab_draft",
    "user_bound_skeleton",
    "partial_custom_draft",
})


def build_spl_artifact_handoff_summary(
    *,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    spl_draft_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge authoritative SPL fields into one trace/read-model surface.

    This projection must never become runtime execution authority.
    """
    candidate = candidate_spl if isinstance(candidate_spl, dict) else {}
    validation = spl_validation if isinstance(spl_validation, dict) else {}
    preview = spl_draft_preview if isinstance(spl_draft_preview, dict) else {}

    generation_mode = str(
        candidate.get("generation_mode")
        or validation.get("generation_mode")
        or preview.get("generation_mode")
        or ""
    )
    provider = str(
        validation.get("selected_candidate_spl_provider")
        or candidate.get("selected_candidate_spl_provider")
        or ""
    ).strip()
    provider_reason = str(
        validation.get("candidate_provider_reason")
        or candidate.get("candidate_provider_reason")
        or validation.get("llm_fallback_reason")
        or candidate.get("llm_fallback_reason")
        or ""
    ).strip()

    t2_native = generation_mode == "t2_spl_native_review" or bool(candidate.get("t2_spl_native"))
    lab_preview = bool(preview.get("draft_spl")) or generation_mode in _LAB_PREVIEW_MODES
    artifact_source = spl_artifact_source(candidate, validation)
    llm_failover = llm_failover_used_factual(
        candidate_spl=candidate,
        spl_validation=validation,
        budget_records=None,
    )
    governed_template_bound = bool(
        validation.get("approved")
        and validation.get("normalized_spl")
        and not lab_preview
        and not t2_native
    )

    execution_eligible = bool(candidate.get("execution_eligible"))
    review_only = not execution_eligible

    if generation_mode == "clarification_required":
        status = "clarification_required"
    elif t2_native:
        status = "t2_native_review_only"
    elif lab_preview:
        status = "lab_preview_review_only"
    elif governed_template_bound:
        status = "governed_template_candidate"
    elif llm_failover:
        status = "llm_failover_advisory"
    elif candidate.get("candidate_spl") or preview.get("draft_spl"):
        status = "review_only_candidate"
    else:
        status = "no_spl_artifact"

    validator_status = "not_run"
    if validation:
        validator_status = "approved" if validation.get("approved") else "rejected"

    must_not_execute_reason = str(
        validation.get("review_required_reason")
        or candidate.get("llm_fallback_reason")
        or ("execution_disabled_by_policy" if review_only else "")
        or ""
    ).strip() or None

    provenance = build_spl_provenance_summary(candidate, validation, budget_records=None)

    return {
        "spl_artifact_status": status,
        "spl_artifact_source": artifact_source,
        "candidate_provider": provider or None,
        "candidate_provider_reason": provider_reason or None,
        "governed_template_bound": governed_template_bound,
        "t2_native_shape": t2_native,
        "lab_preview_used": lab_preview,
        "llm_failover_used": llm_failover,
        "deterministic_fallback_used": provenance.get("deterministic_fallback_used"),
        "llm_candidate_generated": provenance.get("llm_candidate_generated"),
        "fallback_reason": fallback_reason(candidate) or provenance.get("fallback_reason"),
        "validator_status": validator_status,
        "review_only": review_only,
        "execution_eligible": execution_eligible,
        "must_not_execute_reason": must_not_execute_reason,
        "trace_authority": "read_model_projection_only",
    }
