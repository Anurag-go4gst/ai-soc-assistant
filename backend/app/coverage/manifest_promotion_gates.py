"""Stage 3L-S5: Deterministic Q4A → manifest promotion gate evaluation (backend canonical)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.coverage.coverage_loader import list_coverage
from app.coverage.coverage_models import CoverageReadiness, PatternCoverageEntry
from app.coverage.manifest_entry_validator import validate_manifest_entry
from app.coverage.promotion_registry_snapshot import (
    PromotionRegistrySnapshot,
    load_promotion_registry_snapshot,
)
from app.routing.runtime_skill_catalog import RUNTIME_SKILL_CATALOG
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.spl.template_registry import get_spl_template

PromotionEvaluationMode = Literal["draft", "committed"]


@dataclass
class PromotionGateCheck:
    gate_id: str
    passed: bool
    detail: str


@dataclass
class PromotionGateResult:
    coverage_id: str
    question_ref: str
    promotion_ready: bool
    manifest_copy_ready: bool
    manifest_integrity_ok: bool
    authority_pilot_ready: bool
    evaluation_mode: str
    checks: list[PromotionGateCheck] = field(default_factory=list)
    authority_checks: list[PromotionGateCheck] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _check(gate_id: str, passed: bool, detail: str) -> PromotionGateCheck:
    return PromotionGateCheck(gate_id=gate_id, passed=passed, detail=detail)


def _governance_execution_flags_false(entry: PatternCoverageEntry) -> tuple[bool, str]:
    payload = entry.governance.model_dump()
    violations = [
        key
        for key, value in payload.items()
        if value is True
        and (key.endswith("_enabled") or key in ("execution_authorized", "execution_eligible"))
    ]
    if violations:
        return False, f"non-false flags: {violations}"
    return True, "all governance execution flags false"


def _filter_validation_for_committed(
    entry: PatternCoverageEntry,
    errors: list[str],
) -> list[str]:
    if entry.readiness != CoverageReadiness.COE_SYNTHETIC_FIXTURE:
        return errors
    return [item for item in errors if not item.startswith("sample_only_template_not_promoted:")]


def _manifest_coverage_ids() -> frozenset[str]:
    return frozenset(entry.coverage_id for entry in list_coverage())


def evaluate_promotion_gates(
    entry: PatternCoverageEntry,
    snapshot: PromotionRegistrySnapshot | None = None,
    *,
    mode: PromotionEvaluationMode = "draft",
    manifest_ids: frozenset[str] | None = None,
    coe_signoff_recorded: bool = False,
) -> PromotionGateResult:
    """Evaluate draft promotion or committed-manifest integrity (no manifest writes)."""
    snapshot = snapshot or load_promotion_registry_snapshot()
    manifest_ids = manifest_ids if manifest_ids is not None else _manifest_coverage_ids()

    validation_errors, validation_warnings = validate_manifest_entry(entry, snapshot)
    if mode == "committed":
        validation_errors = _filter_validation_for_committed(entry, validation_errors)
    checks: list[PromotionGateCheck] = []

    checks.append(
        _check(
            "registry_validation_clean",
            not validation_errors,
            "no validation_errors" if not validation_errors else f"{len(validation_errors)} validation error(s)",
        )
    )

    duplicate = entry.coverage_id in manifest_ids
    if mode == "draft":
        checks.append(
            _check(
                "coverage_id_not_in_manifest",
                not duplicate,
                "coverage_id available for new manifest row"
                if not duplicate
                else "coverage_id already in manifest",
            )
        )
    else:
        checks.append(
            _check(
                "coverage_id_in_manifest",
                duplicate,
                "coverage_id present in committed manifest"
                if duplicate
                else "coverage_id missing from committed manifest",
            )
        )

    shape_skill = str(entry.route_plan_shape.get("primary_skill") or "")
    checks.append(
        _check(
            "route_plan_primary_skill_matches_entry",
            shape_skill == entry.primary_skill,
            f"entry.primary_skill={entry.primary_skill!r} shape={shape_skill!r}",
        )
    )

    operation_type = str(entry.route_plan_shape.get("operation_type") or "")
    catalog = RUNTIME_SKILL_CATALOG.get(entry.primary_skill, {})
    allowed_ops = frozenset(catalog.get("allowed_operation_types") or [])
    checks.append(
        _check(
            "operation_type_allowed_for_skill",
            operation_type in allowed_ops,
            f"operation_type={operation_type!r} allowed={sorted(allowed_ops)}",
        )
    )

    if mode == "committed":
        shape = entry.route_plan_shape
        core_present = all(
            isinstance(shape.get(key), str) and str(shape.get(key)).strip()
            for key in ("primary_skill", "operation_type", "pattern_id")
        )
        checks.append(
            _check(
                "route_plan_core_fields_present",
                core_present,
                "primary_skill, operation_type, pattern_id present"
                if core_present
                else "missing route_plan_shape core fields",
            )
        )
        if entry.readiness == CoverageReadiness.COE_SYNTHETIC_FIXTURE:
            fixture_template_ok = True
            fixture_detail = "no template_ref"
            if entry.template_ref is not None:
                template = get_spl_template(entry.template_ref)
                if template is None:
                    fixture_template_ok = False
                    fixture_detail = f"unknown template_ref={entry.template_ref!r}"
                else:
                    fixture_detail = (
                        f"fixture allows sample_only={template.sample_only} "
                        f"template_ref={entry.template_ref}"
                    )
            checks.append(
                _check("fixture_template_bound", fixture_template_ok, fixture_detail)
            )
        else:
            template_ok = True
            template_detail = "no template_ref"
            if entry.template_ref is not None:
                template = get_spl_template(entry.template_ref)
                if template is None:
                    template_ok = False
                    template_detail = f"unknown template_ref={entry.template_ref!r}"
                elif template.sample_only:
                    template_ok = False
                    template_detail = f"sample_only_template_not_promoted:{entry.template_ref}"
                else:
                    template_detail = f"production template_ref={entry.template_ref}"
            checks.append(_check("template_promotion_policy", template_ok, template_detail))
    else:
        route_validation = validate_route_plan_candidate(entry.route_plan_shape)
        checks.append(
            _check(
                "route_plan_validator_pass",
                route_validation.is_valid,
                "valid"
                if route_validation.is_valid
                else ",".join(route_validation.blocking_findings[:3]),
            )
        )

        template_ok = True
        template_detail = "no template_ref"
        if entry.template_ref is not None:
            template = get_spl_template(entry.template_ref)
            if template is None:
                template_ok = False
                template_detail = f"unknown template_ref={entry.template_ref!r}"
            elif template.sample_only:
                template_ok = False
                template_detail = f"sample_only_template_not_promoted:{entry.template_ref}"
            else:
                template_detail = f"production template_ref={entry.template_ref}"
        checks.append(_check("template_promotion_policy", template_ok, template_detail))

    readiness_ok = entry.readiness != CoverageReadiness.DEPENDENCY_MISSING or bool(entry.expected_blockers)
    checks.append(
        _check(
            "readiness_or_documented_blockers",
            readiness_ok,
            f"readiness={entry.readiness.value} blockers={entry.expected_blockers}",
        )
    )

    governance_ok, governance_detail = _governance_execution_flags_false(entry)
    checks.append(_check("governance_flags_false", governance_ok, governance_detail))

    manifest_integrity_ok = all(item.passed for item in checks)
    manifest_copy_ready = manifest_integrity_ok if mode == "draft" else False

    authority_checks = list(checks)
    authority_checks.append(
        _check(
            "authority_pilot_question_ref",
            entry.question_ref == "q0.q046",
            f"question_ref={entry.question_ref!r}",
        )
    )
    authority_checks.append(
        _check(
            "authority_pilot_coverage_id",
            entry.coverage_id == "cov.q046.excessive_failed_logins_sample",
            f"coverage_id={entry.coverage_id!r}",
        )
    )
    authority_checks.append(
        _check(
            "coe_signoff_recorded",
            coe_signoff_recorded,
            "COE Step 3 sign-off recorded"
            if coe_signoff_recorded
            else "COE Step 3 sign-off required (see stage3l_s3_step3_coe_gate_review.md)",
        )
    )
    authority_pilot_ready = all(item.passed for item in authority_checks)

    return PromotionGateResult(
        coverage_id=entry.coverage_id,
        question_ref=entry.question_ref,
        promotion_ready=manifest_integrity_ok if mode == "committed" else manifest_copy_ready,
        manifest_copy_ready=manifest_copy_ready,
        manifest_integrity_ok=manifest_integrity_ok,
        authority_pilot_ready=authority_pilot_ready,
        evaluation_mode=mode,
        checks=checks,
        authority_checks=authority_checks,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
    )
