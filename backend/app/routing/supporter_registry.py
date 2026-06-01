from __future__ import annotations

from typing import Any

from app.config import settings
from app.intel.ioc_lookup import evaluate_registry_staleness


READ_ONLY_SUPPORTERS = (
    "route_plan_preflight",
    "ioc_registry_staleness_check",
    "detection_registry_ref_check",
    "precondition_shadow_evaluation",
)


def build_supporter_trace(route_plan: dict[str, Any] | None) -> dict[str, Any]:
    """Trace read-only supporter functions for OOD route-plan review.

    Supporters are deterministic local helpers. They do not call MCP, execute
    SPL, or grant route authority; their output is evidence for review only.
    """
    trace: dict[str, Any] = {
        "enabled": True,
        "authority": "advisory_read_only",
        "mcp_called": False,
        "spl_generated": False,
        "execution_authorized": False,
        "supporters": [],
        "warnings": [],
    }
    for supporter_id in READ_ONLY_SUPPORTERS:
        trace["supporters"].append(_supporter_status(supporter_id, route_plan))
    return trace


def _supporter_status(supporter_id: str, route_plan: dict[str, Any] | None) -> dict[str, Any]:
    if supporter_id == "route_plan_preflight":
        return {"supporter_id": supporter_id, "status": "already_applied", "side_effects": False}
    if supporter_id == "precondition_shadow_evaluation":
        return {"supporter_id": supporter_id, "status": "applied_later_in_shadow", "side_effects": False}
    if supporter_id == "ioc_registry_staleness_check":
        return _ioc_registry_status(route_plan)
    if supporter_id == "detection_registry_ref_check":
        return _detection_registry_status(route_plan)
    return {"supporter_id": supporter_id, "status": "unknown_supporter", "side_effects": False}


def _ioc_registry_status(route_plan: dict[str, Any] | None) -> dict[str, Any]:
    required = _lookup_required(route_plan)
    status = {
        "supporter_id": "ioc_registry_staleness_check",
        "status": "not_required",
        "side_effects": False,
        "lookup_required": required,
    }
    if not required:
        return status
    if not settings.ioc_registry_enabled:
        return {**status, "status": "blocked_registry_disabled"}
    try:
        staleness = evaluate_registry_staleness()
    except (OSError, ValueError) as exc:
        return {**status, "status": "blocked_registry_unavailable", "reason": str(exc)}
    return {**status, "status": "checked", "staleness_status": staleness.value}


def _detection_registry_status(route_plan: dict[str, Any] | None) -> dict[str, Any]:
    detection_ref = None
    parameters = route_plan.get("parameters") if isinstance(route_plan, dict) else None
    if isinstance(parameters, dict):
        detection_ref = parameters.get("detection_ref")
    return {
        "supporter_id": "detection_registry_ref_check",
        "status": "candidate_ref_present" if detection_ref else "not_required",
        "side_effects": False,
        "detection_ref_present": bool(detection_ref),
    }


def _lookup_required(route_plan: dict[str, Any] | None) -> bool:
    if not isinstance(route_plan, dict):
        return False
    evidence_needs = route_plan.get("evidence_needs")
    if isinstance(evidence_needs, dict) and evidence_needs.get("lookup_required") is True:
        return True
    parameters = route_plan.get("parameters")
    if isinstance(parameters, dict) and parameters.get("lookup_ref"):
        return True
    return route_plan.get("primary_skill") == "lookup_correlation"
