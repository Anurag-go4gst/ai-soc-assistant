from __future__ import annotations

from typing import Any

from app.skills.models import SkillSelectionResult
from app.skills.registry import build_skill_chain, get_skill
from app.use_cases.models import UseCaseSelection


def select_skill_chain(
    *,
    routed: dict[str, Any],
    selected_use_case: UseCaseSelection | None,
) -> SkillSelectionResult:
    """Create a registry-backed skill selection record without changing routing.

    The current deterministic router remains the authority for execution behavior.
    The registry is advisory in this phase and records where it agrees or disagrees.
    """
    selected_skill = str(routed["skill"])
    chain = build_skill_chain(selected_skill, selected_use_case)
    registry_primary = selected_use_case.primary_skill if selected_use_case else None
    llm_shadow = routed.get("llm_shadow") or {}
    llm_assisted_skill = str(llm_shadow.get("skill")) if llm_shadow.get("skill") else None
    alternatives = _alternatives(selected_skill, registry_primary, llm_assisted_skill)
    policy_notes = _policy_notes(selected_skill, registry_primary)

    return SkillSelectionResult(
        selected_skill=selected_skill,
        selected_use_case_id=selected_use_case.use_case_id if selected_use_case else None,
        selected_chain=chain,
        decision_source="deterministic_router",
        selection_status="selected",
        rule_based_skill=selected_skill,
        registry_primary_skill=registry_primary,
        llm_assisted_skill=llm_assisted_skill,
        alternatives=alternatives,
        policy_notes=policy_notes,
    )


def _alternatives(selected_skill: str, registry_primary: str | None, llm_assisted_skill: str | None) -> list[str]:
    alternatives: list[str] = []
    for candidate in (registry_primary, llm_assisted_skill):
        if candidate and candidate != selected_skill and candidate not in alternatives:
            alternatives.append(candidate)
    return alternatives


def _policy_notes(selected_skill: str, registry_primary: str | None) -> list[str]:
    notes = ["router_selection_preserved_for_phase_2"]
    skill = get_skill(selected_skill)
    if skill and not skill.routable:
        notes.append("selected_skill_not_routable_registry_mismatch")
    if registry_primary and registry_primary != selected_skill:
        notes.append("registry_primary_skill_recorded_as_advisory_alternative")
    return notes
