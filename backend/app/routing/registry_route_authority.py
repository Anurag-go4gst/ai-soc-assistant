"""P2-9: Resolve effective workflow skill when registry operation authority is active."""

from __future__ import annotations

from typing import Any, Final

from app.routing.intent_to_operation_bridge import INTENT_TO_ALLOWED_PRIMARY_SKILLS

LEGACY_INTENT_MIRROR_ORDER: Final[tuple[str, ...]] = (
    "attack_discovery",
    "spl_generation",
    "knowledge_recall",
    "alert_summary",
)


def legacy_intent_authority_enabled() -> bool:
    from app.config import settings

    return settings.legacy_selected_skill_authority_enabled


def resolve_legacy_intent_for_primary_operation(primary_operation: str | None) -> str | None:
    if not isinstance(primary_operation, str) or not primary_operation.strip():
        return None
    operation = primary_operation.strip()
    for legacy_intent in LEGACY_INTENT_MIRROR_ORDER:
        allowed = INTENT_TO_ALLOWED_PRIMARY_SKILLS.get(legacy_intent)
        if allowed is None:
            continue
        if operation in allowed:
            return legacy_intent
    return None


def resolve_effective_routing_skill(
    *,
    selected_skill: str,
    route_authority: dict[str, object] | None,
    primary_operation: str | None,
) -> dict[str, Any]:
    """Choose skill for workflow/SPL stages without granting LLM authority."""
    legacy_authority = legacy_intent_authority_enabled()
    authority_applied = bool(
        isinstance(route_authority, dict) and route_authority.get("authority_decision") == "applied"
    )
    planning_operation = None
    if isinstance(route_authority, dict):
        value = route_authority.get("planning_primary_skill") or route_authority.get("candidate_primary_skill")
        if isinstance(value, str) and value.strip():
            planning_operation = value.strip()
    if planning_operation is None and isinstance(primary_operation, str):
        planning_operation = primary_operation.strip() or None

    if legacy_authority or not authority_applied:
        return {
            "effective_skill": selected_skill,
            "legacy_intent_authority": True,
            "skill_resolution": "legacy_selected_skill",
            "planning_primary_operation": planning_operation,
        }

    mirrored = resolve_legacy_intent_for_primary_operation(planning_operation)
    if mirrored:
        return {
            "effective_skill": mirrored,
            "legacy_intent_authority": False,
            "skill_resolution": "registry_operation_mirror",
            "planning_primary_operation": planning_operation,
            "legacy_intent_mirror": mirrored,
        }

    return {
        "effective_skill": selected_skill,
        "legacy_intent_authority": False,
        "skill_resolution": "legacy_fallback_no_mirror",
        "planning_primary_operation": planning_operation,
    }
