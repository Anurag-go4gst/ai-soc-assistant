from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.skills.models import SkillChain, SkillDefinition
from app.use_cases.models import UseCaseSelection

CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_skill_registry() -> list[SkillDefinition]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [SkillDefinition(**item) for item in payload.get("skills", [])]


def get_skill(skill_id: str) -> SkillDefinition | None:
    return next((item for item in load_skill_registry() if item.skill_id == skill_id), None)


def build_skill_chain(selected_skill: str, use_case: UseCaseSelection | None) -> SkillChain:
    skill = get_skill(selected_skill)
    default_workflow = list(skill.default_workflow if skill else [])
    stages = ["query_understanding", *default_workflow]
    if "context_sufficiency" not in stages:
        stages.append("context_sufficiency")

    alternatives = []
    if use_case:
        alternatives = [item for item in [use_case.primary_skill] if item != selected_skill]

    return SkillChain(
        chain_id=f"chain:{use_case.use_case_id if use_case else selected_skill}",
        selected_skill=selected_skill,
        stages=stages,
        routable_skill=selected_skill,
        pipeline_stages=[stage for stage in stages if stage != selected_skill],
        alternatives=alternatives,
        selection_reason="use_case_registry_advisory_mapping" if use_case else "router_selected_without_use_case_match",
    )
