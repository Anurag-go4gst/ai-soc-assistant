"""Deterministic DetailTool multi-select."""

from __future__ import annotations

from typing import Any

from app.chat.known_detail_completion import MissingFieldCategory

_TOOL_BY_GAP: dict[MissingFieldCategory, list[str]] = {
    "tool_discoverable": ["knowledge_recall", "spl_generation", "attack_discovery", "alert_summary"],
    "planner_required": [],
    "user_only": [],
    "optional": [],
}

_ANSWER_GOAL_TOOLS: dict[str, list[str]] = {
    "reference_explanation": ["knowledge_recall"],
    "alert_summary": ["alert_summary", "knowledge_recall"],
    "live_investigation": ["attack_discovery", "spl_generation", "knowledge_recall"],
    "spl_generation": ["spl_generation", "knowledge_recall"],
    "exposure_status": ["knowledge_recall", "attack_discovery", "alert_summary"],
    "guided_investigation": ["attack_discovery", "knowledge_recall"],
}


def select_detail_tools(
    *,
    intent_family: str,
    answer_goal: str,
    missing_categories: dict[str, MissingFieldCategory],
    reference_ids: list[str] | None = None,
    original_skill: str | None = None,
    unsafe: bool = False,
) -> list[str]:
    if unsafe:
        return []

    selected: list[str] = []
    for _field, category in missing_categories.items():
        if category == "tool_discoverable":
            selected.extend(_TOOL_BY_GAP["tool_discoverable"])

    goal_tools = list(_ANSWER_GOAL_TOOLS.get(answer_goal, []))
    if intent_family in {"reference_knowledge", "knowledge_only"}:
        goal_tools = ["knowledge_recall"]
    elif intent_family == "alert_summary":
        goal_tools = ["alert_summary", "knowledge_recall"]
    elif intent_family in {"spl_generation_only", "spl_generation_and_run"}:
        goal_tools = ["spl_generation", "knowledge_recall"]
    elif intent_family == "guided_investigation":
        goal_tools = ["attack_discovery", "knowledge_recall"]

    if original_skill and original_skill not in goal_tools:
        goal_tools.insert(0, original_skill)

    if reference_ids and "knowledge_recall" not in goal_tools:
        goal_tools.insert(0, "knowledge_recall")

    selected.extend(goal_tools)
    # Stable dedupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for tool in selected:
        if tool in seen:
            continue
        seen.add(tool)
        ordered.append(tool)
    return ordered or ["attack_discovery"]
