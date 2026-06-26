from __future__ import annotations

from typing import Any

AUTHORITY_READY_EFFECTIVE = "authority_ready"
DEMOTED_THIS_TURN = "demoted_this_turn"
NOT_PROMOTED = "not_promoted"


def promotion_gate_decision(
    *,
    stored_promotion_status: str | None,
    reviewed_pack_loaded: bool,
    golden_passed: bool,
    s3_authority_ready: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not reviewed_pack_loaded:
        blockers.append("reviewed_answer_pack_required")
    if not golden_passed:
        blockers.append("golden_test_required")
    if not s3_authority_ready:
        blockers.append("s3_authority_ready_required")
    return {
        "stored_promotion_status": stored_promotion_status,
        "promotion_allowed": not blockers,
        "blockers": blockers,
        "authority_of_record": "catalogue_runtime_map",
    }


def effective_promotion_status(
    *,
    stored_promotion_status: str | None,
    row_authority_summary: dict[str, Any] | None = None,
    source_profile_binding_summary: dict[str, Any] | None = None,
    answer_pack_summary: dict[str, Any] | None = None,
    golden_passed: bool | None = None,
    mitre_validation_conflict: bool = False,
) -> dict[str, Any]:
    """Return the per-turn effective status without mutating stored metadata."""
    stored = str(stored_promotion_status or "")
    s3_ready = bool((row_authority_summary or {}).get("s3_authority_ready"))
    reasons = _demotion_reasons(
        row_authority_summary=row_authority_summary,
        source_profile_binding_summary=source_profile_binding_summary,
        golden_passed=golden_passed,
        mitre_validation_conflict=mitre_validation_conflict,
    )
    if stored == "in_manifest" and s3_ready and not reasons:
        effective = AUTHORITY_READY_EFFECTIVE
    elif stored == "in_manifest" and reasons:
        effective = DEMOTED_THIS_TURN
    else:
        effective = NOT_PROMOTED
    return {
        "stored_promotion_status": stored_promotion_status,
        "effective_promotion_status": effective,
        "runtime_demoted": effective == DEMOTED_THIS_TURN,
        "demotion_reasons": reasons,
        "stored_status_mutated": False,
        "authority_of_record": "catalogue_runtime_map",
        "answer_pack_loaded": bool(answer_pack_summary),
    }


def can_skip_llm_for_t0(lifecycle_summary: dict[str, Any] | None) -> bool:
    summary = lifecycle_summary if isinstance(lifecycle_summary, dict) else {}
    return summary.get("effective_promotion_status") == AUTHORITY_READY_EFFECTIVE


def _demotion_reasons(
    *,
    row_authority_summary: dict[str, Any] | None,
    source_profile_binding_summary: dict[str, Any] | None,
    golden_passed: bool | None,
    mitre_validation_conflict: bool,
) -> list[str]:
    reasons: list[str] = []
    if source_profile_binding_summary and source_profile_binding_summary.get("source_profile_bindings_missing"):
        reasons.append("environment_mapping_drift")
    row_status = str((row_authority_summary or {}).get("row_authority_status") or "")
    if row_status.endswith("_needs_lookup"):
        reasons.append("lookup_dependency_unavailable")
    if row_status.endswith("_needs_detection_binding"):
        reasons.append("detection_binding_unavailable")
    if row_status.endswith("_needs_context_binding"):
        reasons.append("context_dependency_unavailable")
    if golden_passed is False:
        reasons.append("golden_test_failed")
    if mitre_validation_conflict:
        reasons.append("mitre_validation_conflict")
    return list(dict.fromkeys(reasons))
