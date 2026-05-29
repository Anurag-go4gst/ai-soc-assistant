"""Stage 3L-S2A-FOLLOWUP: Surface intent↔operation bridge on route_plan_shadow only."""

from __future__ import annotations

from typing import Any, Final

from app.routing.intent_to_operation_bridge import (
    IntentOperationBridgeResult,
    evaluate_intent_operation_bridge,
)

BRIDGE_STATUS_COMPATIBLE: Final[str] = "compatible"
BRIDGE_STATUS_INCOMPATIBLE: Final[str] = "incompatible"
BRIDGE_STATUS_MODIFIER_ONLY: Final[str] = "modifier_only"
BRIDGE_STATUS_NOT_EVALUATED: Final[str] = "not_evaluated"
BRIDGE_STATUS_UNKNOWN_LEGACY_INTENT: Final[str] = "unknown_legacy_intent"
BRIDGE_STATUS_UNKNOWN_PRIMARY_SKILL: Final[str] = "unknown_primary_skill"


def bridge_status_from_result(
    result: IntentOperationBridgeResult,
    *,
    primary_skill_observed: bool,
) -> str:
    if result.rejection_reason == "unknown_legacy_intent":
        return BRIDGE_STATUS_UNKNOWN_LEGACY_INTENT
    if result.rejection_reason == "unknown_primary_skill":
        return BRIDGE_STATUS_UNKNOWN_PRIMARY_SKILL
    if result.spl_generation_modifier_detected:
        return BRIDGE_STATUS_MODIFIER_ONLY
    if not primary_skill_observed:
        return BRIDGE_STATUS_NOT_EVALUATED
    if result.compatible:
        return BRIDGE_STATUS_COMPATIBLE
    return BRIDGE_STATUS_INCOMPATIBLE


def apply_intent_operation_bridge_to_shadow(
    shadow: dict[str, Any],
    *,
    legacy_intent: str,
) -> IntentOperationBridgeResult:
    """Evaluate legacy selected_skill against shadow primary_skill; never mutates route plan."""
    primary_skill_observed = shadow.get("primary_skill")
    skill_for_bridge = (
        str(primary_skill_observed).strip() if isinstance(primary_skill_observed, str) and primary_skill_observed.strip() else None
    )
    result = evaluate_intent_operation_bridge(legacy_intent, skill_for_bridge)
    status = bridge_status_from_result(
        result,
        primary_skill_observed=skill_for_bridge is not None,
    )
    shadow["intent_operation_bridge"] = {
        "bridge_status": status,
        "legacy_intent": result.legacy_intent,
        "primary_skill_observed": skill_for_bridge,
        "compatible": result.compatible,
        "rejection_reason": result.rejection_reason,
        "disagreements": list(result.disagreements),
        "allowed_primary_skills": list(result.allowed_primary_skills),
        "spl_generation_modifier_detected": result.spl_generation_modifier_detected,
        "output_artifacts_deferred_to_s2b": result.output_artifacts_deferred_to_s2b,
        "intent_modifier": result.intent_modifier,
        "output_artifact_hint": result.output_artifact_hint,
        "underlying_operation": result.underlying_operation,
    }
    return result
