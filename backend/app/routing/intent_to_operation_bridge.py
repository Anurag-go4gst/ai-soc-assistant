"""Stage 3L-S2A: Legacy intent (SKILL_ENUM) ↔ runtime primary_skill compatibility bridge.

Advisory/validating only — does not change selected_skill authority or route plans.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Final

from app.llm.sidecar_governance import build_advisory_disagreement
from app.routing.route_plan_models import runtime_skill_values
from app.routing.skills import SKILL_ENUM, valid_skill

INTENT_MODIFIER_CANDIDATE_SPL_REQUESTED: Final[str] = "candidate_spl_requested"
OUTPUT_ARTIFACT_HINT_CANDIDATE_SPL_VISIBLE: Final[str] = "candidate_spl_visible"

ATTACK_DISCOVERY_PRIMARY_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "aggregate_and_rank",
        "threshold_anomaly",
        "sequence_detection",
        "lookup_correlation",
        "behavioral_detection_binding",
        "multi_signal_correlation",
        "entity_timeline",
    }
)

KNOWLEDGE_RECALL_PRIMARY_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "metadata_discovery",
        "entity_context_lookup",
        "notable_risk_lookup",
    }
)

ALERT_SUMMARY_PRIMARY_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "notable_risk_lookup",
        "entity_context_lookup",
        "entity_timeline",
    }
)

# None = no primary_skill restriction (spl_generation modifier path).
INTENT_TO_ALLOWED_PRIMARY_SKILLS: Final[dict[str, frozenset[str] | None]] = {
    "attack_discovery": ATTACK_DISCOVERY_PRIMARY_SKILLS,
    "spl_generation": None,
    "knowledge_recall": KNOWLEDGE_RECALL_PRIMARY_SKILLS,
    "alert_summary": ALERT_SUMMARY_PRIMARY_SKILLS,
}


@dataclass
class IntentOperationBridgeResult:
    legacy_intent: str
    primary_skill: str | None
    compatible: bool
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    rejection_reason: str | None = None
    spl_generation_modifier_detected: bool = False
    output_artifacts_deferred_to_s2b: bool = False
    intent_modifier: str | None = None
    output_artifact_hint: str | None = None
    underlying_operation: str | None = None
    allowed_primary_skills: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def list_bridge_legacy_intents() -> tuple[str, ...]:
    return SKILL_ENUM


def allowed_primary_skills_for_intent(legacy_intent: str) -> list[str] | None:
    """Return allowed primary_skill IDs, or None when intent imposes no restriction (spl_generation)."""
    if legacy_intent not in INTENT_TO_ALLOWED_PRIMARY_SKILLS:
        return None
    allowed = INTENT_TO_ALLOWED_PRIMARY_SKILLS[legacy_intent]
    if allowed is None:
        return None
    return sorted(allowed)


def evaluate_intent_operation_bridge(
    legacy_intent: str,
    primary_skill: str | None,
) -> IntentOperationBridgeResult:
    """Check legacy router intent against route_plan.primary_skill without mutating inputs."""
    intent = legacy_intent.strip() if isinstance(legacy_intent, str) else ""
    skill = primary_skill.strip() if isinstance(primary_skill, str) else None

    if not valid_skill(intent):
        return IntentOperationBridgeResult(
            legacy_intent=intent or str(legacy_intent),
            primary_skill=skill,
            compatible=False,
            rejection_reason="unknown_legacy_intent",
        )

    if skill is not None and skill not in runtime_skill_values():
        return IntentOperationBridgeResult(
            legacy_intent=intent,
            primary_skill=skill,
            compatible=False,
            rejection_reason="unknown_primary_skill",
        )

    if intent == "spl_generation":
        return IntentOperationBridgeResult(
            legacy_intent=intent,
            primary_skill=skill,
            compatible=True,
            spl_generation_modifier_detected=True,
            output_artifacts_deferred_to_s2b=True,
            intent_modifier=INTENT_MODIFIER_CANDIDATE_SPL_REQUESTED,
            output_artifact_hint=OUTPUT_ARTIFACT_HINT_CANDIDATE_SPL_VISIBLE,
            underlying_operation=skill,
            allowed_primary_skills=[],
        )

    allowed = INTENT_TO_ALLOWED_PRIMARY_SKILLS[intent]
    assert allowed is not None
    allowed_list = sorted(allowed)

    if skill is None:
        return IntentOperationBridgeResult(
            legacy_intent=intent,
            primary_skill=None,
            compatible=True,
            allowed_primary_skills=allowed_list,
        )

    if skill in allowed:
        return IntentOperationBridgeResult(
            legacy_intent=intent,
            primary_skill=skill,
            compatible=True,
            allowed_primary_skills=allowed_list,
        )

    disagreement = build_advisory_disagreement(
        field="intent_to_operation_bridge",
        llm_value=skill,
        deterministic_value=intent,
        reason_for_deterministic_win=(
            f"legacy_intent_not_compatible_with_primary_skill:{intent}:{skill}"
        ),
    )
    return IntentOperationBridgeResult(
        legacy_intent=intent,
        primary_skill=skill,
        compatible=False,
        disagreements=[disagreement],
        allowed_primary_skills=allowed_list,
    )
