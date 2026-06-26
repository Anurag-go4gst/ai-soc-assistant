"""Row-authority classification for known runtime-map rows.

This module is deterministic and side-effect free. It does not make routing or
execution decisions; callers use it to project the existing runtime-map metadata
into one reasoned status plus the existing ``s3_authority_ready`` boolean.
"""

from __future__ import annotations

from typing import Any

AUTHORITY_READY = "exact_known_authority_ready"
WEAK_NEEDS_ENRICHMENT = "exact_known_weak_needs_enrichment"
NEEDS_LOOKUP = "exact_known_needs_lookup"
NEEDS_DETECTION_BINDING = "exact_known_needs_detection_binding"
NEEDS_CONTEXT_BINDING = "exact_known_needs_context_binding"
NEEDS_CLARIFICATION = "exact_known_needs_clarification"
UNSUPPORTED = "exact_known_unsupported"

AUTHORITY_READY_READINESS = frozenset({"source_ready"})
LOOKUP_READINESS = frozenset({"ioc_dependent", "lookup_dependent"})
DETECTION_READINESS = frozenset({"detection_dependent"})
CONTEXT_READINESS = frozenset({"blocked_missing_context", "context_dependent"})
CLARIFICATION_REFS = frozenset({"q0.q045", "q0.q103", "q0.q104", "q0.q105"})


def project_s3_authority_ready(row_authority_status: str) -> bool:
    return row_authority_status == AUTHORITY_READY


def classify_runtime_row_authority(
    entry: dict[str, Any],
    manifest_entry: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Return ``(row_authority_status, blockers)`` for one runtime-map row."""
    blockers: list[str] = []
    question_ref = str(entry.get("question_ref") or "")
    readiness = entry.get("manifest_readiness")
    promotion_status = entry.get("promotion_status")
    dependency_class = entry.get("dependency_class")

    if entry.get("route_blocked") is True or not entry.get("proposed_primary_skill"):
        if entry.get("route_blocked") is True:
            blockers.append("route_blocked")
        if not entry.get("proposed_primary_skill"):
            blockers.append("missing_proposed_primary_skill")
        return UNSUPPORTED, blockers

    if question_ref in CLARIFICATION_REFS:
        blockers.append("requires_clarification_or_case_context")
        return NEEDS_CLARIFICATION, blockers

    if readiness in LOOKUP_READINESS or dependency_class == "local_lookup":
        blockers.append(f"manifest_readiness:{readiness or 'missing'}")
        return NEEDS_LOOKUP, blockers

    if readiness in DETECTION_READINESS or dependency_class == "detection_binding":
        blockers.append(f"manifest_readiness:{readiness or 'missing'}")
        return NEEDS_DETECTION_BINDING, blockers

    if readiness in CONTEXT_READINESS:
        blockers.append(f"manifest_readiness:{readiness}")
        return NEEDS_CONTEXT_BINDING, blockers

    existing_ready = entry.get("s3_authority_ready") is True
    manifest_execution_eligible = False
    if isinstance(manifest_entry, dict):
        governance = manifest_entry.get("governance")
        if isinstance(governance, dict):
            manifest_execution_eligible = governance.get("execution_eligible") is True

    if existing_ready and promotion_status == "in_manifest" and readiness in AUTHORITY_READY_READINESS:
        if manifest_execution_eligible:
            return AUTHORITY_READY, blockers
        blockers.append("manifest_execution_eligible_false")
        return WEAK_NEEDS_ENRICHMENT, blockers

    if promotion_status != "in_manifest":
        blockers.append(f"promotion_status:{promotion_status or 'missing'}")
    if not readiness:
        blockers.append("manifest_readiness:missing")
    elif readiness not in AUTHORITY_READY_READINESS:
        blockers.append(f"manifest_readiness:{readiness}")
    if entry.get("skill_drift") is True:
        blockers.append("skill_drift")
    for blocker in entry.get("s3_authority_blockers") or []:
        if isinstance(blocker, str) and blocker not in blockers:
            blockers.append(blocker)
    return WEAK_NEEDS_ENRICHMENT, blockers
