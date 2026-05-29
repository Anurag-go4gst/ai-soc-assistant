"""Stage 3L-S2B: Resolve output artifact tokens for shadow/lineage only.

Does not change renderer, analyst card, or /chat answer text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Final

from app.routing.intent_to_operation_bridge import (
    OUTPUT_ARTIFACT_HINT_CANDIDATE_SPL_VISIBLE,
    IntentOperationBridgeResult,
)
from app.routing.skills import valid_skill

OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE: Final[str] = "candidate_spl_visible"
OUTPUT_ARTIFACT_ANALYST_SUMMARY_ONLY: Final[str] = "analyst_summary_only"
OUTPUT_ARTIFACT_KNOWLEDGE_ONLY: Final[str] = "knowledge_only"

OUTPUT_ARTIFACT_TOKENS: Final[frozenset[str]] = frozenset(
    {
        OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE,
        OUTPUT_ARTIFACT_ANALYST_SUMMARY_ONLY,
        OUTPUT_ARTIFACT_KNOWLEDGE_ONLY,
    }
)

LEGACY_INTENT_DEFAULT_TOKENS: Final[dict[str, tuple[str, ...]]] = {
    "attack_discovery": (OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE,),
    "spl_generation": (OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE,),
    "knowledge_recall": (OUTPUT_ARTIFACT_KNOWLEDGE_ONLY,),
    "alert_summary": (OUTPUT_ARTIFACT_ANALYST_SUMMARY_ONLY,),
}


@dataclass
class OutputArtifactsResolution:
    legacy_intent: str
    tokens: list[str] = field(default_factory=list)
    resolution_source: str = "s2b_registry"
    bridge_hint_applied: bool = False
    unknown_legacy_intent: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def resolve_output_artifacts(
    legacy_intent: str,
    *,
    bridge: IntentOperationBridgeResult | None = None,
) -> OutputArtifactsResolution:
    """Map legacy router intent (+ optional bridge hints) to approved artifact tokens."""
    intent = legacy_intent.strip() if isinstance(legacy_intent, str) else ""

    if not valid_skill(intent):
        return OutputArtifactsResolution(
            legacy_intent=intent or str(legacy_intent),
            tokens=[],
            unknown_legacy_intent=True,
            resolution_source="none",
        )

    if bridge is not None and bridge.spl_generation_modifier_detected:
        hint = bridge.output_artifact_hint or OUTPUT_ARTIFACT_HINT_CANDIDATE_SPL_VISIBLE
        token = hint if hint in OUTPUT_ARTIFACT_TOKENS else OUTPUT_ARTIFACT_CANDIDATE_SPL_VISIBLE
        return OutputArtifactsResolution(
            legacy_intent=intent,
            tokens=[token],
            bridge_hint_applied=True,
        )

    defaults = LEGACY_INTENT_DEFAULT_TOKENS.get(intent, ())
    return OutputArtifactsResolution(
        legacy_intent=intent,
        tokens=list(defaults),
    )
