"""SKILL_ENUM must match between backend routing and test harness."""

from __future__ import annotations

from app.routing.skills import SKILL_ENUM as BACKEND_SKILL_ENUM
from test_harness.harness.interfaces import SKILL_ENUM as HARNESS_SKILL_ENUM


def test_skill_enum_matches_harness_contract() -> None:
    assert BACKEND_SKILL_ENUM == HARNESS_SKILL_ENUM
