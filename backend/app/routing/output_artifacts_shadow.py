"""Stage 3L-S2B: Surface resolved output_artifacts on route_plan_shadow only."""

from __future__ import annotations

from typing import Any

from app.routing.intent_to_operation_bridge import IntentOperationBridgeResult
from app.routing.output_artifacts import resolve_output_artifacts


def apply_output_artifacts_to_shadow(
    shadow: dict[str, Any],
    *,
    legacy_intent: str,
    bridge_result: IntentOperationBridgeResult | None = None,
) -> dict[str, Any]:
    """Resolve artifact tokens for lineage; never mutates route plan or selected_skill."""
    resolution = resolve_output_artifacts(legacy_intent, bridge=bridge_result)
    shadow["output_artifacts"] = {
        "legacy_intent": resolution.legacy_intent,
        "resolved_artifacts": list(resolution.tokens),
        "resolution_source": resolution.resolution_source,
        "bridge_hint_applied": resolution.bridge_hint_applied,
        "unknown_legacy_intent": resolution.unknown_legacy_intent,
        "renderer_applied": False,
    }
    return shadow["output_artifacts"]
