"""Stage 3L-S7.4: Align S5 promotion audit with S7 hard-precondition evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.config import Settings, settings as default_settings
from app.coverage.coverage_models import CoverageReadiness, PatternCoverageEntry
from app.coverage.manifest_promotion_gates import PromotionGateResult, evaluate_promotion_gates
from app.routing.precondition_dependency_state import (
    _merge_plan_with_coverage,
    build_hard_precondition_dependency_state,
)
from app.routing.precondition_evaluator import (
    FINDING_MISSING_CONFIGURED_DETECTION,
    FINDING_MISSING_CONFIGURED_LOOKUP,
    FINDING_MISSING_EVIDENCE_CONTRACT,
    FINDING_MISSING_TEMPLATE,
    HardPreconditionEvaluationResult,
    evaluate_hard_preconditions,
)
from app.routing.route_plan_models import RouteStatus
from app.spl.template_registry import get_spl_template

AlignmentStatus = Literal["aligned", "documented_gap", "drift"]

# S5 manifest validation error prefixes → S7 precondition ids (author-time vs plan-time).
VALIDATION_ERROR_TO_PRECONDITION: dict[str, str] = {
    "unknown_template_ref": "template_available",
    "sample_only_template_not_promoted": "template_available",
    "unknown_evidence_contract_ref": "evidence_contract_available",
    "unknown_lookup_ref": "lookup_available",
    "unknown_detection_ref": "detection_registered",
    "unvetted_detection_ref": "detection_vetted",
}


@dataclass
class ManifestPreconditionAlignment:
    coverage_id: str
    question_ref: str
    promotion_integrity_ok: bool
    precondition_route_status: str
    precondition_blocking_findings: list[str]
    precondition_failed_ids: list[str]
    matches_manifest_expectation: bool
    promotion_precondition_consistent: bool
    alignment_status: AlignmentStatus
    documented_gap_ids: list[str] = field(default_factory=list)
    alignment_notes: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


_MANIFEST_BLOCKER_ALIASES: dict[str, str] = {
    "missing_vetted_detection": FINDING_MISSING_CONFIGURED_DETECTION,
    "missing_configured_lookup": FINDING_MISSING_CONFIGURED_LOOKUP,
}


def _normalize_blocker_token(blocker: str) -> str:
    token = blocker.split(":", 1)[0].strip()
    return _MANIFEST_BLOCKER_ALIASES.get(token, token)


def _validation_error_prefix(error: str) -> str:
    return error.split(":", 1)[0].strip()


def _matches_manifest_expectation(
    entry: PatternCoverageEntry,
    evaluation: HardPreconditionEvaluationResult,
) -> bool:
    if evaluation.route_status != entry.expected_route_status:
        return False
    expected = {_normalize_blocker_token(item) for item in entry.expected_blockers}
    actual = set(evaluation.blocking_findings)
    if not expected:
        return not actual
    return expected <= actual


def _promotion_precondition_consistent(
    entry: PatternCoverageEntry,
    gate: PromotionGateResult,
    evaluation: HardPreconditionEvaluationResult,
) -> tuple[bool, list[str]]:
    """True when S5 validation errors imply the same S7 precondition failures."""
    notes: list[str] = []
    failed_preconditions = set(evaluation.preconditions_failed)

    for error in gate.validation_errors:
        prefix = _validation_error_prefix(error)
        precondition_id = VALIDATION_ERROR_TO_PRECONDITION.get(prefix)
        if precondition_id and precondition_id not in failed_preconditions:
            notes.append(
                f"S5 validation error {error!r} without matching S7 failure {precondition_id!r}"
            )

    if entry.template_ref:
        template = get_spl_template(entry.template_ref)
        if template is not None and template.sample_only:
            if "template_available" not in failed_preconditions:
                notes.append("sample_only template present but S7 did not fail template_available")

    if notes:
        return False, notes
    return True, notes


def _documented_gap_ids(
    entry: PatternCoverageEntry,
    evaluation: HardPreconditionEvaluationResult,
) -> list[str]:
    gaps: list[str] = []
    template = get_spl_template(entry.template_ref) if entry.template_ref else None
    if (
        entry.readiness == CoverageReadiness.COE_SYNTHETIC_FIXTURE
        and template is not None
        and template.sample_only
        and evaluation.route_status == RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value
        and entry.expected_route_status == RouteStatus.ROUTE_READY.value
    ):
        gaps.append("coe_fixture_sample_template_blocks_s7")

    if entry.expected_route_status == RouteStatus.CLARIFICATION_REQUIRED.value and (
        evaluation.route_status == RouteStatus.CANNOT_ROUTE_UNSUPPORTED_SOURCE.value
        or (
            evaluation.route_status == RouteStatus.CLARIFICATION_REQUIRED.value
            and set(evaluation.blocking_findings)
            - {
                FINDING_MISSING_REQUIRED_THRESHOLD_REF,
                FINDING_MISSING_REQUIRED_TIME_WINDOW,
            }
        )
    ):
        gaps.append("manifest_clarification_vs_s7_preconditions")

    return gaps


def evaluate_manifest_precondition_alignment(
    entry: PatternCoverageEntry,
    gate: PromotionGateResult | None = None,
    *,
    settings: Settings | None = None,
    coe_signoff_recorded: bool = True,
) -> ManifestPreconditionAlignment:
    """Cross-check committed manifest row: S5 gates + S7 evaluator (read-only)."""
    active_settings = settings or default_settings
    gate = gate or evaluate_promotion_gates(
        entry,
        mode="committed",
        coe_signoff_recorded=coe_signoff_recorded,
    )
    plan = _merge_plan_with_coverage(None, entry)
    dependency_state = build_hard_precondition_dependency_state(plan, entry, active_settings)
    evaluation = evaluate_hard_preconditions(plan, dependency_state)

    matches_manifest = _matches_manifest_expectation(entry, evaluation)
    promo_consistent, promo_notes = _promotion_precondition_consistent(entry, gate, evaluation)
    documented_gaps = _documented_gap_ids(entry, evaluation)

    if matches_manifest and promo_consistent:
        status: AlignmentStatus = "aligned"
        notes = promo_notes
    elif documented_gaps and not matches_manifest:
        status = "documented_gap"
        notes = promo_notes + [
            f"manifest expected_route_status={entry.expected_route_status!r} "
            f"differs from S7 {evaluation.route_status!r}; gap documented"
        ]
    elif matches_manifest and not promo_consistent:
        status = "drift"
        notes = promo_notes
    elif documented_gaps:
        status = "documented_gap"
        notes = promo_notes
    else:
        status = "drift"
        notes = promo_notes + [
            f"unexpected S7 vs manifest: expected {entry.expected_route_status!r}, "
            f"got {evaluation.route_status!r}"
        ]

    return ManifestPreconditionAlignment(
        coverage_id=entry.coverage_id,
        question_ref=entry.question_ref,
        promotion_integrity_ok=gate.manifest_integrity_ok,
        precondition_route_status=evaluation.route_status,
        precondition_blocking_findings=list(evaluation.blocking_findings),
        precondition_failed_ids=list(evaluation.preconditions_failed),
        matches_manifest_expectation=matches_manifest,
        promotion_precondition_consistent=promo_consistent,
        alignment_status=status,
        documented_gap_ids=documented_gaps,
        alignment_notes=notes,
    )


def audit_committed_precondition_alignment(
    *,
    settings: Settings | None = None,
    coe_signoff_recorded: bool = True,
) -> dict[str, Any]:
    from app.coverage.coverage_loader import list_coverage

    alignments = [
        evaluate_manifest_precondition_alignment(
            entry,
            settings=settings,
            coe_signoff_recorded=coe_signoff_recorded,
        ).model_dump()
        for entry in list_coverage()
    ]
    all_ok = all(
        item["alignment_status"] in ("aligned", "documented_gap") for item in alignments
    )
    return {
        "entry_count": len(alignments),
        "all_precondition_alignment_ok": all_ok,
        "entries": alignments,
    }
