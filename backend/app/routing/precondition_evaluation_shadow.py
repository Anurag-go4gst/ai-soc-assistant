"""Stage 3L-S7.3: Hard-precondition evaluation on route_plan_shadow (observational only)."""

from __future__ import annotations

from typing import Any

from app.coverage.coverage_loader import coverage_for_id
from app.routing.precondition_dependency_state import build_hard_precondition_dependency_state
from app.routing.precondition_evaluator import evaluate_hard_preconditions
from app.routing.route_authority_gate import resolve_coverage_id_from_shadow


def _coverage_id_from_shadow(route_plan_shadow: dict[str, Any]) -> str | None:
    compare = route_plan_shadow.get("route_authority_compare")
    if isinstance(compare, dict):
        resolved = compare.get("coverage_id_resolved")
        if isinstance(resolved, str) and resolved.strip():
            return resolved.strip()
    return resolve_coverage_id_from_shadow(route_plan_shadow)


def _route_plan_from_shadow(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {}
    for key in (
        "primary_skill",
        "pattern_id",
        "route_status",
        "source_class",
        "template_ref",
        "evidence_contract_ref",
        "lookup_ref",
        "detection_ref",
        "detection_family",
    ):
        value = route_plan_shadow.get(key)
        if value is not None:
            plan[key] = value

    parameters = route_plan_shadow.get("route_plan_parameters")
    if isinstance(parameters, dict):
        plan["parameters"] = dict(parameters)

    time_window = route_plan_shadow.get("route_plan_time_window")
    if isinstance(time_window, dict):
        plan["time_window"] = time_window
    elif isinstance(time_window, str) and time_window.strip():
        plan["time_window"] = time_window

    return plan


def resolve_precondition_evaluation_for_shadow(
    route_plan_shadow: dict[str, Any],
) -> dict[str, Any]:
    """Build registry-backed dependency state and evaluate; does not change routing authority."""
    plan = _route_plan_from_shadow(route_plan_shadow)
    if not plan.get("primary_skill") and not plan.get("pattern_id"):
        return {
            "observation_only": True,
            "evaluation_skipped": True,
            "skip_reason": "insufficient_shadow_route_plan",
            "route_status": None,
            "blocking_findings": [],
            "preconditions_checked": [],
            "preconditions_passed": [],
            "preconditions_failed": [],
            "dependency_readiness": "unknown",
        }

    coverage_id = _coverage_id_from_shadow(route_plan_shadow)
    entry = coverage_for_id(coverage_id) if coverage_id else None
    dependency_state = build_hard_precondition_dependency_state(plan, entry)
    evaluation = evaluate_hard_preconditions(plan, dependency_state)

    payload = evaluation.model_dump()
    payload["observation_only"] = True
    payload["evaluation_skipped"] = False
    payload["coverage_id"] = coverage_id
    return payload


def apply_precondition_evaluation_to_shadow(route_plan_shadow: dict[str, Any]) -> dict[str, Any]:
    payload = resolve_precondition_evaluation_for_shadow(route_plan_shadow)
    route_plan_shadow["precondition_evaluation"] = payload
    return payload
