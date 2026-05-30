from __future__ import annotations

from contracts.skill_enum import SKILL_ENUM


def validate_skill(skill: str) -> str:
    if skill not in SKILL_ENUM:
        raise ValueError(f"Invalid AI-SOC skill: {skill}")
    return skill


def valid_skill(skill: object) -> bool:
    return isinstance(skill, str) and skill in SKILL_ENUM
