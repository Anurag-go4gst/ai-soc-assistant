from __future__ import annotations

from typing import Any

from app.config import settings
from app.intel.ioc_lookup import evaluate_registry_staleness
from app.orchestration.evidence_mcp_mapping import (
    SPLUNK_AUTH_EVIDENCE,
    SPLUNK_METADATA_DISCOVERY,
    map_evidence_need_to_mcp_tools,
)
from app.routing.precondition_evaluation_shadow import resolve_precondition_evaluation_for_shadow
from app.routing.route_plan_preflight import preflight_route_plan
from app.use_cases.registry import match_use_cases


READ_ONLY_SUPPORTERS = (
    "route_plan_preflight",
    "ioc_registry_staleness_check",
    "detection_registry_ref_check",
    "precondition_shadow_evaluation",
)


def build_supporter_trace(
    route_plan: dict[str, Any] | None,
    *,
    query: str | None = None,
    shadow: dict[str, Any] | None = None,
    runtime_invoked: bool = False,
) -> dict[str, Any]:
    """Trace read-only supporter functions for OOD route-plan review.

    Supporters are deterministic local helpers. They do not call MCP, execute
    SPL, or grant route authority; their output is evidence for review only.
    """
    if runtime_invoked and settings.route_plan_supporters_runtime_enabled:
        return run_read_only_supporters(route_plan, query=query, shadow=shadow)
    trace: dict[str, Any] = {
        "enabled": True,
        "authority": "advisory_read_only",
        "runtime_invoked": False,
        "mcp_called": False,
        "spl_generated": False,
        "execution_authorized": False,
        "supporters": [],
        "warnings": [],
    }
    for supporter_id in READ_ONLY_SUPPORTERS:
        trace["supporters"].append(_supporter_status(supporter_id, route_plan, query=query, shadow=shadow))
    return trace


def run_read_only_supporters(
    route_plan: dict[str, Any] | None,
    *,
    query: str | None = None,
    shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute allowlisted supporter helpers during Q1F sidecar (read-only)."""
    trace: dict[str, Any] = {
        "enabled": True,
        "authority": "advisory_read_only",
        "runtime_invoked": True,
        "mcp_called": False,
        "spl_generated": False,
        "execution_authorized": False,
        "supporters": [],
        "warnings": [],
    }
    extended = (
        *READ_ONLY_SUPPORTERS,
        "match_use_cases",
        "map_evidence_needs",
    )
    for supporter_id in extended:
        trace["supporters"].append(_supporter_status(supporter_id, route_plan, query=query, shadow=shadow))
    return trace


def _supporter_status(
    supporter_id: str,
    route_plan: dict[str, Any] | None,
    *,
    query: str | None = None,
    shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if supporter_id == "route_plan_preflight":
        if query:
            preflight = preflight_route_plan(query)
            return {
                "supporter_id": supporter_id,
                "status": "checked",
                "side_effects": False,
                "route_status": preflight.route_status.value if preflight.route_status else None,
                "missing_slots": list(preflight.missing_slots),
            }
        return {"supporter_id": supporter_id, "status": "already_applied", "side_effects": False}
    if supporter_id == "precondition_shadow_evaluation":
        if isinstance(shadow, dict):
            evaluation = resolve_precondition_evaluation_for_shadow(shadow)
            return {
                "supporter_id": supporter_id,
                "status": "checked",
                "side_effects": False,
                "evaluation": evaluation,
            }
        return {"supporter_id": supporter_id, "status": "shadow_context_missing", "side_effects": False}
    if supporter_id == "ioc_registry_staleness_check":
        return _ioc_registry_status(route_plan)
    if supporter_id == "detection_registry_ref_check":
        return _detection_registry_status(route_plan)
    if supporter_id == "match_use_cases" and query:
        matches = match_use_cases(query, limit=2)
        return {
            "supporter_id": supporter_id,
            "status": "checked",
            "side_effects": False,
            "match_count": len(matches),
            "top_use_case_id": matches[0].use_case_id if matches else None,
        }
    if supporter_id == "map_evidence_needs":
        return _evidence_needs_status(route_plan)
    return {"supporter_id": supporter_id, "status": "unknown_supporter", "side_effects": False}


def _evidence_needs_status(route_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(route_plan, dict):
        return {"supporter_id": "map_evidence_needs", "status": "not_required", "side_effects": False}
    primary_skill = route_plan.get("primary_skill")
    if not isinstance(primary_skill, str) or not primary_skill.strip():
        return {"supporter_id": "map_evidence_needs", "status": "not_required", "side_effects": False}
    skill = primary_skill.strip()
    evidence_need = (
        SPLUNK_METADATA_DISCOVERY if skill == "metadata_discovery" else SPLUNK_AUTH_EVIDENCE
    )
    mapping = map_evidence_need_to_mcp_tools(evidence_need=evidence_need)
    return {
        "supporter_id": "map_evidence_needs",
        "status": "checked",
        "side_effects": False,
        "evidence_need": evidence_need,
        "mapping": mapping,
    }


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
