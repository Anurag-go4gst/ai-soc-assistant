"""P2-open: structural and policy validation for non-seed primary_skill values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

from app.routing.route_plan_models import runtime_skill_values
from app.routing.runtime_skill_catalog import get_skill_contract

OPEN_OPERATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
FORBIDDEN_OPERATION_MARKERS: Final[tuple[str, ...]] = (
    "splunk_run",
    "execute_spl",
    "write_index",
    "delete_",
    "external_ti",
    "virustotal",
    "shodan",
    "generative_spl",
    "saia_",
    "action_chain",
    "llm_",
)
FORBIDDEN_OPERATION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "raw_spl",
        "spl_execute",
        "write",
        "admin",
        "generative",
    }
)
POLICY_VIOLATION_MARKERS: Final[tuple[str, ...]] = (
    "|",
    "search ",
    "tstats",
    "from datamodel",
    "stats ",
)


@dataclass(frozen=True)
class OpenOperationValidation:
    is_seed_catalog: bool
    is_open_operation: bool
    operation_provenance: str
    structurally_valid: bool
    policy_passed: bool
    blocking_findings: tuple[str, ...]
    warnings: tuple[str, ...]


def classify_operation_provenance(primary_skill: str | None) -> str:
    if not isinstance(primary_skill, str) or not primary_skill.strip():
        return "unset"
    skill = primary_skill.strip()
    if skill in runtime_skill_values():
        return "seed_catalog"
    if get_skill_contract(skill):
        return "seed_catalog"
    return "open_proposed"


def validate_open_operation(
    plan: dict[str, Any],
    *,
    open_operations_enabled: bool,
) -> OpenOperationValidation:
    primary_skill = plan.get("primary_skill")
    if not isinstance(primary_skill, str) or not primary_skill.strip():
        return OpenOperationValidation(
            is_seed_catalog=False,
            is_open_operation=False,
            operation_provenance="unset",
            structurally_valid=False,
            policy_passed=False,
            blocking_findings=("missing_primary_skill",),
            warnings=(),
        )

    skill = primary_skill.strip()
    provenance = classify_operation_provenance(skill)
    if provenance == "seed_catalog":
        return OpenOperationValidation(
            is_seed_catalog=True,
            is_open_operation=False,
            operation_provenance=provenance,
            structurally_valid=True,
            policy_passed=True,
            blocking_findings=(),
            warnings=(),
        )

    if not open_operations_enabled:
        return OpenOperationValidation(
            is_seed_catalog=False,
            is_open_operation=True,
            operation_provenance=provenance,
            structurally_valid=False,
            policy_passed=False,
            blocking_findings=(f"unknown_primary_skill:{skill}",),
            warnings=(),
        )

    blocking: list[str] = []
    warnings: list[str] = []
    if not OPEN_OPERATION_ID_PATTERN.match(skill):
        blocking.append(f"open_operation_invalid_identifier:{skill}")
    operation_type = plan.get("operation_type")
    if isinstance(operation_type, str) and operation_type.strip().lower() in FORBIDDEN_OPERATION_TYPES:
        blocking.append(f"open_operation_type_forbidden:{operation_type}")
    lowered_skill = skill.lower()
    for marker in FORBIDDEN_OPERATION_MARKERS:
        if marker in lowered_skill:
            blocking.append(f"open_operation_forbidden_marker:{marker}")
    _scan_policy_violations(plan, blocking)
    structurally_valid = not any(f.startswith("open_operation_invalid") for f in blocking)
    policy_passed = structurally_valid and not blocking
    if policy_passed:
        warnings.append("open_operation_structural_pass_advisory_only")
    return OpenOperationValidation(
        is_seed_catalog=False,
        is_open_operation=True,
        operation_provenance=provenance,
        structurally_valid=structurally_valid,
        policy_passed=policy_passed,
        blocking_findings=tuple(blocking),
        warnings=tuple(warnings),
    )


def _scan_policy_violations(plan: dict[str, Any], blocking: list[str]) -> None:
    for key in ("rationale", "notes", "spl", "query"):
        value = plan.get(key)
        if isinstance(value, str) and _contains_policy_violation(value):
            blocking.append(f"open_operation_policy_violation_field:{key}")
    metadata = plan.get("model_advisory_metadata")
    if isinstance(metadata, dict):
        rationale = metadata.get("rationale")
        if isinstance(rationale, str) and _contains_policy_violation(rationale):
            blocking.append("open_operation_policy_violation_rationale")
    parameters = plan.get("parameters")
    if isinstance(parameters, dict):
        for slot, value in parameters.items():
            if isinstance(value, str) and _contains_policy_violation(value):
                blocking.append(f"open_operation_policy_violation_parameter:{slot}")


def _contains_policy_violation(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in POLICY_VIOLATION_MARKERS)
