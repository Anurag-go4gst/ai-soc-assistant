"""S6.2 provisional report fields derived from S6.1 runtime map rows (not a runtime contract)."""

from __future__ import annotations

from typing import Any, Final

# dependency_class / pattern_type → S6.2 dependency_type (report only).
_DEPENDENCY_CLASS_TO_TYPE: Final[dict[str, str]] = {
    "source_binding": "template",
    "threshold_baseline_plus_source": "template",
    "baseline_policy": "template",
    "source_plus_threshold": "template",
    "source_threshold_or_detection": "template",
    "local_lookup": "lookup",
    "notable_risk_source": "lookup",
    "case_history_source": "lookup",
    "detection_binding": "detection",
    "source_detection_blocked": "unsupported",
    "enrichment_lookup": "context",
    "composed_dependencies": "multi_signal",
    "metadata_inventory": "context",
    "policy_definition": "unknown",
}

_PATTERN_BLOCKED_TYPES: Final[frozenset[str]] = frozenset(
    {"cloud_activity", "other_or_unclear"},
)


def derive_dependency_type(pattern_type: str, dependency_class: str | None, *, route_blocked: bool) -> str:
    if route_blocked or pattern_type in _PATTERN_BLOCKED_TYPES:
        return "unsupported"
    if not dependency_class:
        return "unknown"
    return _DEPENDENCY_CLASS_TO_TYPE.get(dependency_class, "unknown")


def derive_provisional_status(
    *,
    pattern_type: str,
    proposed_primary_skill: str | None,
    dependency_type: str,
    route_blocked: bool,
    promoted_to_manifest: bool,
    skill_drift: bool,
) -> str:
    if route_blocked or pattern_type in _PATTERN_BLOCKED_TYPES:
        return "likely_unsupported"
    if proposed_primary_skill is None:
        return "likely_needs_review"
    if promoted_to_manifest and not skill_drift:
        return "likely_routable"
    if skill_drift:
        return "likely_needs_review"
    if dependency_type == "lookup":
        return "likely_needs_lookup"
    if dependency_type == "detection":
        return "likely_needs_detection"
    if dependency_type == "context":
        return "likely_needs_context"
    if dependency_type == "multi_signal":
        return "likely_multi_signal"
    if dependency_type == "unsupported":
        return "likely_unsupported"
    if dependency_type == "template":
        return "likely_routable"
    return "likely_needs_review"


def derive_source_class(dependency_class: str | None) -> str:
    return dependency_class or "unknown"


def build_report_entry(runtime_row: dict[str, Any]) -> dict[str, Any]:
    """Enrich an S6.1 map row with S6.2 provisional report fields."""
    pattern = str(runtime_row["pattern_type"])
    dependency_class = runtime_row.get("dependency_class")
    route_blocked = bool(runtime_row.get("route_blocked"))
    promoted = runtime_row.get("promotion_status") == "in_manifest"
    skill_drift = bool(runtime_row.get("skill_drift"))
    dependency_type = derive_dependency_type(pattern, dependency_class, route_blocked=route_blocked)
    provisional = derive_provisional_status(
        pattern_type=pattern,
        proposed_primary_skill=runtime_row.get("proposed_primary_skill"),
        dependency_type=dependency_type,
        route_blocked=route_blocked,
        promoted_to_manifest=promoted,
        skill_drift=skill_drift,
    )
    notes_parts: list[str] = []
    if skill_drift and runtime_row.get("skill_drift_note"):
        notes_parts.append(str(runtime_row["skill_drift_note"]))
    if runtime_row.get("authority_pilot_candidate"):
        notes_parts.append("S3 authority pilot candidate (observation only; not live authority).")
    if route_blocked:
        notes_parts.append("Pattern blocked for standalone primary fixture in current catalog.")

    report: dict[str, Any] = {
        "question_ref": runtime_row["question_ref"],
        "question_text": runtime_row["question"],
        "taxonomy_pattern": pattern,
        "likely_runtime_operation": runtime_row.get("proposed_primary_skill"),
        "source_class": derive_source_class(dependency_class),
        "dependency_type": dependency_type,
        "provisional_status": provisional,
        "notes": " ".join(notes_parts).strip(),
        "candidate_coverage_id": runtime_row.get("manifest_coverage_id"),
        "promoted_to_manifest": promoted,
    }
    if promoted and runtime_row.get("manifest_readiness") is not None:
        report["manifest_readiness"] = runtime_row["manifest_readiness"]
    return report
