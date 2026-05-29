"""Stage 3L-S5: Deterministic Q4A → manifest promotion gate evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.coverage.coverage_models import CoverageReadiness, PatternCoverageEntry
from app.routing.runtime_skill_catalog import RUNTIME_SKILL_CATALOG
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.spl.template_registry import get_spl_template

from registries import MANIFEST_PATH, RegistrySnapshot, load_registry_snapshot
from validator import validate_draft_entry


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
    authority_pilot_ready: bool
    checks: list[PromotionGateCheck] = field(default_factory=list)
    authority_checks: list[PromotionGateCheck] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _check(gate_id: str, passed: bool, detail: str) -> PromotionGateCheck:
    return PromotionGateCheck(gate_id=gate_id, passed=passed, detail=detail)


def _manifest_coverage_ids() -> frozenset[str]:
    import json

    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return frozenset(entry["coverage_id"] for entry in payload.get("entries", []))


def evaluate_promotion_gates(
    entry: PatternCoverageEntry,
    snapshot: RegistrySnapshot | None = None,
    *,
    manifest_ids: frozenset[str] | None = None,
) -> PromotionGateResult:
    """Evaluate whether a draft entry may be manually copied into pattern_coverage_v1.json."""
    snapshot = snapshot or load_registry_snapshot()
    manifest_ids = manifest_ids if manifest_ids is not None else _manifest_coverage_ids()

    validation_errors, validation_warnings = validate_draft_entry(entry, snapshot)
    checks: list[PromotionGateCheck] = []

    checks.append(
        _check(
            "draft_validation_clean",
            not validation_errors,
            "no validation_errors" if not validation_errors else f"{len(validation_errors)} validation error(s)",
        )
    )

    duplicate = entry.coverage_id in manifest_ids
    checks.append(
        _check(
            "coverage_id_not_in_manifest",
            not duplicate,
            "coverage_id available for new manifest row" if not duplicate else "coverage_id already in manifest",
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

    route_validation = validate_route_plan_candidate(entry.route_plan_shape)
    checks.append(
        _check(
            "route_plan_validator_pass",
            route_validation.is_valid,
            "valid" if route_validation.is_valid else ",".join(route_validation.blocking_findings[:3]),
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

    gov = entry.governance
    governance_ok = not any(
        (
            gov.execution_authorized,
            gov.spl_execution_enabled,
            gov.mcp_execution_enabled,
            gov.llm_final_synthesis_enabled,
            gov.answer_guard_enabled,
            gov.execution_eligible,
        )
    )
    checks.append(
        _check(
            "governance_flags_false",
            governance_ok,
            "all governance execution flags false",
        )
    )

    manifest_copy_ready = all(item.passed for item in checks)

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
            False,
            "COE Step 3 implementation approval still required (see stage3l_s3_step3_coe_gate_review.md)",
        )
    )
    authority_pilot_ready = all(item.passed for item in authority_checks)

    return PromotionGateResult(
        coverage_id=entry.coverage_id,
        question_ref=entry.question_ref,
        promotion_ready=manifest_copy_ready,
        manifest_copy_ready=manifest_copy_ready,
        authority_pilot_ready=authority_pilot_ready,
        checks=checks,
        authority_checks=authority_checks,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
    )
