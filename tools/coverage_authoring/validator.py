"""Validate Q4A draft entries against closed registries."""

from __future__ import annotations

from app.coverage.coverage_models import CoverageReadiness, PatternCoverageEntry
from app.spl.template_registry import get_spl_template

from registries import RegistrySnapshot, evidence_contract_exists


def validate_draft_entry(
    entry: PatternCoverageEntry,
    snapshot: RegistrySnapshot,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if entry.primary_skill not in snapshot.runtime_skills:
        errors.append(f"unknown_primary_skill:{entry.primary_skill}")

    if entry.expected_route_status not in snapshot.route_status_values:
        errors.append(f"unknown_expected_route_status:{entry.expected_route_status}")

    if entry.readiness.value not in snapshot.readiness_labels:
        errors.append(f"unknown_readiness:{entry.readiness}")

    _validate_governance(entry, errors)

    if entry.template_ref is not None:
        if entry.template_ref not in snapshot.template_refs:
            errors.append(f"unknown_template_ref:{entry.template_ref}")
        else:
            template = get_spl_template(entry.template_ref)
            if template is not None and template.sample_only:
                errors.append(f"sample_only_template_not_promoted:{entry.template_ref}")

    if entry.lookup_ref is not None and entry.lookup_ref not in snapshot.lookup_refs:
        errors.append(f"unknown_lookup_ref:{entry.lookup_ref}")

    if entry.detection_ref is not None:
        if entry.detection_ref not in snapshot.detection_refs_all:
            errors.append(f"unknown_detection_ref:{entry.detection_ref}")
        elif entry.detection_ref not in snapshot.detection_refs_bindable:
            errors.append(f"unvetted_detection_ref:{entry.detection_ref}")

    _validate_evidence_contract(entry, errors)

    if entry.readiness == CoverageReadiness.DEPENDENCY_MISSING and not entry.expected_blockers:
        warnings.append("dependency_missing_without_expected_blockers")

    return errors, warnings


def _validate_governance(entry: PatternCoverageEntry, errors: list[str]) -> None:
    gov = entry.governance
    if gov.execution_authorized:
        errors.append("governance.execution_authorized_must_be_false")
    if gov.spl_execution_enabled:
        errors.append("governance.spl_execution_enabled_must_be_false")
    if gov.mcp_execution_enabled:
        errors.append("governance.mcp_execution_enabled_must_be_false")
    if gov.llm_final_synthesis_enabled:
        errors.append("governance.llm_final_synthesis_enabled_must_be_false")
    if gov.answer_guard_enabled:
        errors.append("governance.answer_guard_enabled_must_be_false")
    if gov.execution_eligible:
        errors.append("governance.execution_eligible_must_be_false")


def _validate_evidence_contract(entry: PatternCoverageEntry, errors: list[str]) -> None:
    ref = entry.evidence_contract_ref
    if entry.readiness == CoverageReadiness.DEPENDENCY_MISSING:
        if not evidence_contract_exists(ref):
            if not _blocker_mentions(ref, entry.expected_blockers, "evidence_contract"):
                errors.append(
                    "dependency_missing_requires_blocker_for_unknown_evidence_contract_ref"
                )
        return

    if not evidence_contract_exists(ref):
        errors.append(f"unknown_evidence_contract_ref:{ref}")


def _blocker_mentions(ref: str, blockers: list[str], keyword: str) -> bool:
    joined = " ".join(blockers).lower()
    return keyword in joined or ref.lower() in joined
