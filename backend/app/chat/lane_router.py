"""Lane routing from deterministic match_path — initial tier and processing lane."""

from __future__ import annotations

from typing import Literal

from app.chat.contracts.canonical_planning_input import CatalogueTier, ProcessingLane

T1_PATHS = frozenset({"exact_105_question", "exact_105_plus_use_case_catalog"})
T2_PATHS = frozenset({"use_case_catalog"})
T3_PATHS = frozenset({"near_105_question", "semantic_105_question", "fuzzy_alias_catalog"})
T4_PATHS = frozenset(
    {
        "out_of_registry",
        "semantic_out_of_registry",
        "query_understanding_weak",
        "qu_unavailable",
        "",
    }
)

ProcessingLaneLiteral = Literal["known", "guided", "knowledge_short_circuit", "clarification"]


def initial_tier_for_match_path(match_path: str | None) -> CatalogueTier:
    path = str(match_path or "").strip()
    if path in T1_PATHS:
        return "T1"
    if path in T2_PATHS:
        return "T2"
    if path in T3_PATHS:
        return "T3"
    return "T4"


def processing_lane_for_initial_tier(
    initial_tier: CatalogueTier,
    *,
    resolved_tier: CatalogueTier | None = None,
) -> ProcessingLane:
    if resolved_tier == "T0":
        return "knowledge_short_circuit"
    if initial_tier in {"T1", "T2", "T3"}:
        return "known"
    return "guided"


def lane_for_match_path(
    match_path: str | None,
    *,
    resolved_tier: CatalogueTier | None = None,
) -> tuple[CatalogueTier, CatalogueTier, ProcessingLane]:
    """Return (initial_tier, resolved_tier, processing_lane).

    T0 is never returned from parser match_path; pass resolved_tier='T0' after
  T4 qualification to obtain knowledge_short_circuit lane.
    """
    initial = initial_tier_for_match_path(match_path)
    resolved = resolved_tier or initial
    lane = processing_lane_for_initial_tier(initial, resolved_tier=resolved)
    return initial, resolved, lane


def is_known_catalogue_match(match_path: str | None) -> bool:
    return initial_tier_for_match_path(match_path) in {"T1", "T2", "T3"}
