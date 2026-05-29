"""Stage 3L-S3 Steps 1–2: Unified shadow compare for legacy intent vs runtime operation."""

from __future__ import annotations

from typing import Any, Final

from app.config import settings

AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL: Final[str] = "legacy_selected_skill"
MIGRATION_PHASE_S3_STEPS_1_2: Final[str] = "S3_steps_1_2_shadow_compare"


def build_route_authority_compare(
    *,
    selected_skill: str,
    route_plan_shadow: dict[str, Any],
    routing_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble RouteAuthorityCompare metadata for shadow/lineage (non-authoritative)."""
    bridge = route_plan_shadow.get("intent_operation_bridge")
    bridge_dict = dict(bridge) if isinstance(bridge, dict) else {}
    primary_observed = route_plan_shadow.get("primary_skill")
    skill_observed = (
        str(primary_observed).strip()
        if isinstance(primary_observed, str) and str(primary_observed).strip()
        else None
    )
    comparison = dict(routing_comparison) if isinstance(routing_comparison, dict) else {}

    return {
        "migration_phase": MIGRATION_PHASE_S3_STEPS_1_2,
        "compare_enabled": settings.route_authority_compare_enabled,
        "operation_authoritative_enabled": settings.route_authority_operation_authoritative_enabled,
        "authority_holder": AUTHORITY_HOLDER_LEGACY_SELECTED_SKILL,
        "dual_run_active": True,
        "selected_skill": selected_skill,
        "route_plan_primary_skill_observed": skill_observed,
        "legacy_skill_router_match": comparison.get("match"),
        "legacy_skill_router_skill_match": comparison.get("skill_match"),
        "legacy_skill_router_tool_plan_match": comparison.get("tool_plan_match"),
        "intent_operation_bridge_status": bridge_dict.get("bridge_status"),
        "intent_bridge_compatible": bridge_dict.get("compatible"),
        "route_plan_shadow_disagreements": list(route_plan_shadow.get("disagreements") or []),
        "intent_bridge_disagreements": list(bridge_dict.get("disagreements") or []),
    }


def apply_route_authority_compare_to_shadow(
    shadow: dict[str, Any],
    *,
    selected_skill: str,
    routing_comparison: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Populate ``route_authority_compare`` on shadow when S3 Steps 1–2 compare is enabled."""
    if not settings.route_authority_compare_enabled:
        shadow["route_authority_compare"] = None
        return None
    payload = build_route_authority_compare(
        selected_skill=selected_skill,
        route_plan_shadow=shadow,
        routing_comparison=routing_comparison,
    )
    shadow["route_authority_compare"] = payload
    return payload
