"""Closed legacy intent enum shared by backend routing and test harness."""

from __future__ import annotations

from typing import Final

SKILL_ENUM: Final[tuple[str, ...]] = (
    "alert_summary",
    "spl_generation",
    "attack_discovery",
    "knowledge_recall",
    "guided_investigation",
)
