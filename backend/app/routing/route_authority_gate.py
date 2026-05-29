"""Stage 3L-S3.3A: Route authority gate evaluation (fallback harness only).

Does not change ``selected_skill`` or apply operation authority unless explicitly
enabled in config and all gates pass. Production default: authority off, allowlist empty.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

from app.coverage.coverage_loader import coverage_for_id, list_coverage
from app.routing.intent_operation_bridge_shadow import BRIDGE_STATUS_COMPATIBLE, BRIDGE_STATUS_INCOMPATIBLE
from app.routing.route_authority_allowlist import (
    COV_Q046_PILOT_COVERAGE_ID,
    parse_route_authority_coverage_allowlist,
)

BLOCKED_COVERAGE_Q007: Final[str] = "cov.q007.dga_detection_binding"
BLOCKED_PRIMARY_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "entity_context_lookup",
        "notable_risk_lookup",
    }
)

FALLBACK_GLOBAL_KILL_SWITCH_DISABLED: Final[str] = "global_kill_switch_disabled"
FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED: Final[str] = "coverage_id_not_allowlisted"
FALLBACK_BRIDGE_INCOMPATIBLE: Final[str] = "bridge_incompatible"
FALLBACK_VALIDATOR_BLOCKED: Final[str] = "validator_blocked"
FALLBACK_MISSING_THRESHOLD_REF: Final[str] = "missing_required_threshold_ref"
FALLBACK_MISSING_TIME_WINDOW: Final[str] = "missing_required_time_window"
FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW: Final[str] = "no_validated_route_plan_shadow"
FALLBACK_BLOCKED_PRIMARY_FIXTURE_ABSENT: Final[str] = "blocked_primary_fixture_absent"
FALLBACK_BLOCKED_DETECTION_DEPENDENT: Final[str] = "blocked_detection_dependent"

BLOCKED_ROUTE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "blocked_invalid_parameters",
        "blocked_invalid_composition",
        "cannot_route_missing_lookup",
        "cannot_route_missing_detection",
        "cannot_route_missing_template",
        "clarification_required",
    }
)


@dataclass
class RouteAuthorityEvaluation:
    authority_eligible: bool
    authority_applied: bool
    authority_fallback_reason: str | None
    coverage_id: str | None
    selected_skill_before: str
    candidate_primary_skill: str | None
    bridge_status: str | None
    validator_status: str | None
    global_enabled: bool
    coverage_id_allowlisted: bool

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def resolve_coverage_id_from_shadow(route_plan_shadow: dict[str, Any]) -> str | None:
    pattern_id = route_plan_shadow.get("pattern_id")
    if not isinstance(pattern_id, str) or not pattern_id.strip():
        return None
    matches = [
        entry.coverage_id
        for entry in list_coverage()
        if entry.route_plan_shape.get("pattern_id") == pattern_id
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _validator_status_from_shadow(route_plan_shadow: dict[str, Any]) -> str:
    route_status = route_plan_shadow.get("route_status")
    if isinstance(route_status, str) and route_status.strip():
        return route_status.strip()
    validation = route_plan_shadow.get("validation_result")
    if isinstance(validation, dict) and validation.get("is_valid") is False:
        return "validation_rejected"
    if route_plan_shadow.get("normalized_plan_available"):
        return "route_ready"
    if route_plan_shadow.get("candidate_available"):
        return "candidate_unvalidated"
    return "no_candidate"


def _route_plan_parameters(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    """Best-effort parameters view for clarification slot checks (shadow only)."""
    # Shadow does not embed full normalized plan; tests may pass parameters via shadow key.
    embedded = route_plan_shadow.get("route_plan_parameters")
    if isinstance(embedded, dict):
        return dict(embedded)
    return {}


def _missing_clarification_slots(
    coverage_id: str | None,
    route_plan_shadow: dict[str, Any],
    *,
    explicit_missing: list[str] | None = None,
) -> list[str]:
    if explicit_missing:
        return list(explicit_missing)
    entry = coverage_for_id(coverage_id) if coverage_id else None
    if entry is None:
        return []
    params = _route_plan_parameters(route_plan_shadow)
    plan_time_window = route_plan_shadow.get("route_plan_time_window")
    missing: list[str] = []
    for slot in entry.clarification_required:
        if slot == "threshold_ref" and not params.get("threshold_ref"):
            missing.append("threshold_ref")
        elif slot == "time_window":
            if not params.get("time_window") and not (
                isinstance(plan_time_window, str) and plan_time_window.strip()
            ):
                missing.append("time_window")
    return missing


def evaluate_route_authority(
    *,
    selected_skill: str,
    route_plan_shadow: dict[str, Any],
    coverage_id: str | None = None,
    clarification_slots_missing: list[str] | None = None,
) -> RouteAuthorityEvaluation:
    """Evaluate operation-authority eligibility without mutating router outputs."""
    from app.config import settings

    global_enabled = settings.route_authority_operation_authoritative_enabled
    allowlist = parse_route_authority_coverage_allowlist(
        settings.route_authority_operation_coverage_allowlist,
    )
    resolved_coverage_id = coverage_id or resolve_coverage_id_from_shadow(route_plan_shadow)
    allowlisted = bool(
        resolved_coverage_id and resolved_coverage_id in allowlist
    )

    bridge = route_plan_shadow.get("intent_operation_bridge") or {}
    bridge_status = bridge.get("bridge_status") if isinstance(bridge, dict) else None
    primary_observed = route_plan_shadow.get("primary_skill")
    candidate_primary = (
        str(primary_observed).strip()
        if isinstance(primary_observed, str) and primary_observed.strip()
        else None
    )
    validator_status = _validator_status_from_shadow(route_plan_shadow)

    fallback: str | None = None

    if not global_enabled:
        fallback = FALLBACK_GLOBAL_KILL_SWITCH_DISABLED
    elif candidate_primary in BLOCKED_PRIMARY_SKILLS:
        fallback = FALLBACK_BLOCKED_PRIMARY_FIXTURE_ABSENT
    elif resolved_coverage_id == BLOCKED_COVERAGE_Q007:
        fallback = FALLBACK_BLOCKED_DETECTION_DEPENDENT
    elif resolved_coverage_id:
        entry = coverage_for_id(resolved_coverage_id)
        if entry is not None and entry.coverage_group == "detection_dependent":
            fallback = FALLBACK_BLOCKED_DETECTION_DEPENDENT
    if fallback is None and not allowlisted:
        fallback = FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED
    if fallback is None and (
        bridge_status == BRIDGE_STATUS_INCOMPATIBLE or bridge.get("compatible") is False
    ):
        fallback = FALLBACK_BRIDGE_INCOMPATIBLE
    if fallback is None and (
        validator_status in BLOCKED_ROUTE_STATUSES or validator_status == "validation_rejected"
    ):
        fallback = FALLBACK_VALIDATOR_BLOCKED
    if fallback is None and (
        not route_plan_shadow.get("normalized_plan_available") or candidate_primary is None
    ):
        fallback = FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW
    if fallback is None:
        missing_slots = _missing_clarification_slots(
            resolved_coverage_id,
            route_plan_shadow,
            explicit_missing=clarification_slots_missing,
        )
        if "threshold_ref" in missing_slots:
            fallback = FALLBACK_MISSING_THRESHOLD_REF
        elif "time_window" in missing_slots:
            fallback = FALLBACK_MISSING_TIME_WINDOW

    authority_eligible = fallback is None
    authority_applied = authority_eligible and global_enabled

    return RouteAuthorityEvaluation(
        authority_eligible=authority_eligible,
        authority_applied=authority_applied,
        authority_fallback_reason=fallback,
        coverage_id=resolved_coverage_id,
        selected_skill_before=selected_skill,
        candidate_primary_skill=candidate_primary,
        bridge_status=str(bridge_status) if bridge_status is not None else None,
        validator_status=validator_status,
        global_enabled=global_enabled,
        coverage_id_allowlisted=allowlisted,
    )


def authority_evaluation_to_shadow_fields(evaluation: RouteAuthorityEvaluation) -> dict[str, Any]:
    """Shadow/debug fields for route_authority_compare (non-authoritative by default)."""
    return {
        "authority_eligible": evaluation.authority_eligible,
        "authority_applied": evaluation.authority_applied,
        "operation_authoritative_applied": evaluation.authority_applied,
        "authority_fallback_reason": evaluation.authority_fallback_reason,
        "coverage_id_resolved": evaluation.coverage_id,
        "coverage_id_allowlisted": evaluation.coverage_id_allowlisted,
        "global_enabled": evaluation.global_enabled,
        "validator_status": evaluation.validator_status,
        "candidate_primary_skill": evaluation.candidate_primary_skill,
        "selected_skill_before": evaluation.selected_skill_before,
    }
