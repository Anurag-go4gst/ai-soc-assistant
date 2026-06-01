"""P5-10: LLM MITRE candidate mapper sidecar.

Advisory only. Parallel to route_plan sidecar; not synthesis.
Populates review queue / trace only.
Never writes status=supported or mitre_permitted[] without SOC approval.

Config gate: AI_SOC_LLM_MITRE_CANDIDATE_MAPPING_ENABLED=true (default false).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.llm.adapter.role_results import adapt_llm_output
from app.llm.sidecar_governance import (
    REASONING_REJECTION_ROUTING,
    SKIP_LLM_DISABLED,
    build_sidecar_metadata_payload,
    resolve_sidecar_role_status,
    run_sidecar_llm_with_timeout,
)
from app.threat.mitre_permitted_builder import (
    STATUS_CANDIDATE,
    STATUS_NEEDS_REVIEW,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_MAPPED,
    STATUS_SUPPORTED,
    MitrePermittedEntry,
    build_mitre_permitted_for_question,
    technique_in_local_bundle,
)

_MITRE_MAPPER_ROLE = "mitre_candidate_mapper"

# Confidence values that indicate weak rationale from LLM.
_WEAK_CONFIDENCE_VALUES = frozenset({"low"})


@dataclass
class MitreCandidateMapResult:
    question_ref: str
    deterministic_entries: list[MitrePermittedEntry] = field(default_factory=list)
    llm_candidate_entries: list[dict[str, Any]] = field(default_factory=list)
    merged_entries: list[dict[str, Any]] = field(default_factory=list)
    llm_mitre_candidate_used: bool = False
    llm_mitre_parse_status: str = "not_run"
    llm_mitre_parse_repaired: bool = False
    llm_mitre_candidate_validation: str = "not_run"
    requires_soc_review: bool = True
    overall_status: str = STATUS_NOT_MAPPED
    sidecar_metadata: dict[str, Any] = field(default_factory=dict)
    trace_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_ref": self.question_ref,
            "deterministic_entries": [e.to_dict() for e in self.deterministic_entries],
            "llm_candidate_entries": self.llm_candidate_entries,
            "merged_entries": self.merged_entries,
            "llm_mitre_candidate_used": self.llm_mitre_candidate_used,
            "llm_mitre_parse_status": self.llm_mitre_parse_status,
            "llm_mitre_parse_repaired": self.llm_mitre_parse_repaired,
            "llm_mitre_candidate_validation": self.llm_mitre_candidate_validation,
            "requires_soc_review": self.requires_soc_review,
            "overall_status": self.overall_status,
            "sidecar_metadata": self.sidecar_metadata,
            "trace_fields": self.trace_fields,
        }


def _validate_llm_technique(
    technique_id: str,
    technique_name: str,
    confidence: str,
    reason: str,
    *,
    is_primary: bool,
) -> tuple[str, str]:
    """Validate a single LLM-suggested technique; return (status, validation_note).

    Rules (plan Section H authority table):
    - ID not in local bundle → not_mapped / needs_review + unknown_id note
    - weak confidence (low) → needs_review + weak_rationale note
    - valid ID in bundle → candidate (never supported from LLM alone)
    """
    if not technique_id or not technique_id.strip().startswith("T"):
        return STATUS_NOT_MAPPED, "malformed_id"

    if not technique_in_local_bundle(technique_id):
        return STATUS_NEEDS_REVIEW, "unknown_id"

    if confidence in _WEAK_CONFIDENCE_VALUES and not is_primary:
        return STATUS_NEEDS_REVIEW, "weak_rationale"

    # Valid ID in bundle → candidate (never supported from LLM output alone)
    return STATUS_CANDIDATE, "valid"


def _entries_from_llm_payload(
    payload: dict[str, Any],
    *,
    use_case_id: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Extract and validate LLM techniques; return (entries, validation_status)."""
    entries: list[dict[str, Any]] = []
    validation_statuses: list[str] = []

    for is_primary, key in ((True, "primary_techniques"), (False, "secondary_techniques")):
        for item in payload.get(key, []):
            technique_id = str(item.get("technique_id") or "").strip()
            technique_name = str(item.get("technique_name") or "").strip()
            confidence = str(item.get("confidence") or "low").strip().lower()
            reason = str(item.get("reason") or "").strip()

            status, validation_note = _validate_llm_technique(
                technique_id,
                technique_name,
                confidence,
                reason,
                is_primary=is_primary,
            )
            validation_statuses.append(validation_note)

            entries.append({
                "technique_id": technique_id,
                "technique_name": technique_name,
                "tactic": "unknown",
                "status": status,
                "source": "llm_candidate",
                "use_case_ids": [use_case_id] if use_case_id else [],
                "in_local_bundle": technique_in_local_bundle(technique_id),
                "soc_approved": False,
                "requires_soc_review": True,
                "confidence": confidence,
                "reason": reason,
                "is_primary": is_primary,
                "llm_validation_note": validation_note,
                "notes": [f"llm_candidate:{validation_note}"],
            })

    if not validation_statuses:
        return entries, "not_run"
    if "malformed_id" in validation_statuses:
        return entries, "malformed_id"
    if "unknown_id" in validation_statuses:
        return entries, "unknown_id"
    if "weak_rationale" in validation_statuses:
        return entries, "weak_rationale"
    return entries, "valid"


def _merge_entries(
    deterministic: list[MitrePermittedEntry],
    llm_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Merge deterministic + LLM entries; deterministic wins on conflict."""
    deterministic_ids = {e.technique_id for e in deterministic}
    merged: list[dict[str, Any]] = [e.to_dict() for e in deterministic]

    for llm_entry in llm_entries:
        technique_id = llm_entry.get("technique_id", "")
        if technique_id not in deterministic_ids:
            merged.append(llm_entry)

    if not merged:
        overall = STATUS_NOT_MAPPED
    elif any(e.get("status") == STATUS_SUPPORTED for e in merged):
        overall = STATUS_SUPPORTED
    elif any(e.get("status") == STATUS_CANDIDATE for e in merged):
        overall = STATUS_CANDIDATE
    elif any(e.get("status") == STATUS_NEEDS_REVIEW for e in merged):
        overall = STATUS_NEEDS_REVIEW
    else:
        overall = STATUS_NOT_MAPPED

    return merged, overall


def run_mitre_candidate_mapping(
    question_ref: str,
    *,
    use_case_id: str | None = None,
    query_text: str | None = None,
    llm_raw_output_provider: Any = None,
) -> MitreCandidateMapResult:
    """Run deterministic + optional LLM MITRE candidate mapping.

    Args:
        question_ref: Registry row identifier (e.g. "q0.q001").
        use_case_id: Optional explicit use-case ID.
        query_text: Optional free-text query for use-case matching.
        llm_raw_output_provider: Callable returning raw LLM string, or None.
            When None or config-gated off, runs deterministic only.

    Returns:
        MitreCandidateMapResult with trace fields for review queue.
    """
    from app.config import settings  # avoid circular at module level

    det_result = build_mitre_permitted_for_question(
        question_ref,
        use_case_id=use_case_id,
        query_text=query_text,
    )
    resolved_use_case_id = det_result.use_case_id

    # Check if LLM sidecar is enabled and configured.
    llm_enabled = (
        settings.ai_soc_llm_mitre_candidate_mapping_enabled
        and llm_raw_output_provider is not None
    )

    if not llm_enabled:
        skip_reason = SKIP_LLM_DISABLED if not settings.ai_soc_llm_mitre_candidate_mapping_enabled else "no_provider_callable"
        merged, overall = _merge_entries(det_result.entries, [])
        return MitreCandidateMapResult(
            question_ref=question_ref,
            deterministic_entries=det_result.entries,
            llm_candidate_entries=[],
            merged_entries=merged,
            llm_mitre_candidate_used=False,
            llm_mitre_parse_status="not_run",
            llm_mitre_parse_repaired=False,
            llm_mitre_candidate_validation="not_run",
            requires_soc_review=True,
            overall_status=overall,
            sidecar_metadata=build_sidecar_metadata_payload(skipped_reason=skip_reason),
            trace_fields={
                "mitre_mapping_source": det_result.mitre_mapping_source,
                "llm_mitre_candidate_used": False,
                "llm_mitre_parse_status": "not_run",
                "llm_mitre_candidate_validation": "not_run",
                "requires_soc_review": True,
            },
        )

    # assist_invoked=True: skip provider-configured check but still enforce
    # ai_soc_llm_mode=disabled kill-switch and reasoning-model rejection.
    role_status = resolve_sidecar_role_status(
        _MITRE_MAPPER_ROLE,
        reasoning_rejection_reason=REASONING_REJECTION_ROUTING,
        assist_invoked=True,
    )
    if not role_status.enabled:
        skip_reason = role_status.llm_assist_skipped_reason or role_status.rejected_reason or "role_disabled"
        merged, overall = _merge_entries(det_result.entries, [])
        return MitreCandidateMapResult(
            question_ref=question_ref,
            deterministic_entries=det_result.entries,
            merged_entries=merged,
            llm_mitre_candidate_used=False,
            llm_mitre_parse_status="not_run",
            llm_mitre_candidate_validation="not_run",
            overall_status=overall,
            sidecar_metadata=build_sidecar_metadata_payload(
                skipped_reason=skip_reason,
                rejected_reason=role_status.rejected_reason,
            ),
            trace_fields={"llm_mitre_candidate_used": False, "llm_mitre_parse_status": "not_run"},
        )

    call_result = run_sidecar_llm_with_timeout(llm_raw_output_provider)
    if call_result.timed_out or call_result.raw_output is None:
        merged, overall = _merge_entries(det_result.entries, [])
        return MitreCandidateMapResult(
            question_ref=question_ref,
            deterministic_entries=det_result.entries,
            merged_entries=merged,
            llm_mitre_candidate_used=False,
            llm_mitre_parse_status="not_run",
            llm_mitre_candidate_validation="not_run",
            overall_status=overall,
            sidecar_metadata=build_sidecar_metadata_payload(timed_out=True),
            trace_fields={"llm_mitre_candidate_used": False, "llm_mitre_parse_status": "timed_out"},
        )

    adapter_result = adapt_llm_output(role=_MITRE_MAPPER_ROLE, raw_output=call_result.raw_output)
    parse_repaired = "json_extracted_from_markdown_fence" in adapter_result.warnings or "prose_before_json_ignored" in adapter_result.warnings

    if not adapter_result.accepted or adapter_result.normalized_payload is None:
        merged, overall = _merge_entries(det_result.entries, [])
        return MitreCandidateMapResult(
            question_ref=question_ref,
            deterministic_entries=det_result.entries,
            merged_entries=merged,
            llm_mitre_candidate_used=False,
            llm_mitre_parse_status="failed",
            llm_mitre_parse_repaired=parse_repaired,
            llm_mitre_candidate_validation="parse_failed",
            overall_status=overall,
            sidecar_metadata=build_sidecar_metadata_payload(),
            trace_fields={
                "llm_mitre_candidate_used": False,
                "llm_mitre_parse_status": "failed",
                "llm_mitre_parse_repaired": parse_repaired,
                "llm_mitre_candidate_validation": "parse_failed",
                "adapter_warnings": adapter_result.warnings,
                "adapter_errors": adapter_result.errors,
            },
        )

    parse_status = "repaired" if parse_repaired else "valid"
    llm_entries, validation_status = _entries_from_llm_payload(
        adapter_result.normalized_payload,
        use_case_id=resolved_use_case_id,
    )
    merged, overall = _merge_entries(det_result.entries, llm_entries)

    return MitreCandidateMapResult(
        question_ref=question_ref,
        deterministic_entries=det_result.entries,
        llm_candidate_entries=llm_entries,
        merged_entries=merged,
        llm_mitre_candidate_used=bool(llm_entries),
        llm_mitre_parse_status=parse_status,
        llm_mitre_parse_repaired=parse_repaired,
        llm_mitre_candidate_validation=validation_status,
        requires_soc_review=True,
        overall_status=overall,
        sidecar_metadata=build_sidecar_metadata_payload(
            extra={
                "adapter_warnings": adapter_result.warnings,
                "dropped_fields": adapter_result.dropped_fields,
            }
        ),
        trace_fields={
            "mitre_mapping_source": det_result.mitre_mapping_source,
            "llm_mitre_candidate_used": bool(llm_entries),
            "llm_mitre_parse_status": parse_status,
            "llm_mitre_parse_repaired": parse_repaired,
            "llm_mitre_candidate_validation": validation_status,
            "requires_soc_review": True,
        },
    )
