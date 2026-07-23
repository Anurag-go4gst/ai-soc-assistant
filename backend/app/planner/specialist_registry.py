"""Specialist registry — lane definitions validated against canonical catalogs.

Derived resource and skill bindings are checked against
``skills/catalog.json`` and ``resource_registry_v1.json`` so the specialist
registry cannot drift into parallel authority.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.planner.planner_hierarchy import SpecialistId, _SPECIALIST_OWNERSHIP
from app.planner.resource_registry import ResourceDescriptor, ResourceRegistry, load_resource_registry

_REGISTRY_PATH = Path(__file__).resolve().parent / "specialist_registry.json"
_SKILL_CATALOG_PATH = Path(__file__).resolve().parents[1] / "skills" / "catalog.json"


class SpecialistDescriptor(BaseModel):
    specialist_id: SpecialistId
    display_name: str
    ownership_scope: list[str] = Field(default_factory=list)
    resource_kinds: list[str] = Field(default_factory=list)
    plan_purposes: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _ownership_matches_hierarchy_contract(self) -> SpecialistDescriptor:
        allowed = _SPECIALIST_OWNERSHIP[self.specialist_id]
        unknown = [item for item in self.ownership_scope if item not in allowed]
        if unknown:
            msg = f"{self.specialist_id} has out-of-lane ownership_scope: {unknown}"
            raise ValueError(msg)
        return self


class SpecialistRegistry(BaseModel):
    schema_version: int
    specialists: list[SpecialistDescriptor]

    def by_id(self, specialist_id: SpecialistId | str) -> SpecialistDescriptor | None:
        for item in self.specialists:
            if item.specialist_id == specialist_id:
                return item
        return None


def load_skill_catalog(*, path: Path | None = None) -> dict[str, Any]:
    payload = json.loads((path or _SKILL_CATALOG_PATH).read_text(encoding="utf-8"))
    skills = payload.get("skills") or []
    return {str(item["skill_id"]): item for item in skills if isinstance(item, dict) and item.get("skill_id")}


def derive_specialist_resource_ids(
    descriptor: SpecialistDescriptor,
    resource_registry: ResourceRegistry,
    *,
    skill_catalog: dict[str, Any] | None = None,
) -> list[str]:
    kinds = frozenset(descriptor.resource_kinds)
    bound = [item.resource_id for item in resource_registry.resources if item.kind in kinds]
    if descriptor.specialist_id == "skill":
        skill_catalog = skill_catalog or load_skill_catalog()
        routable = frozenset(derive_skill_specialist_skill_ids(skill_catalog))
        bound = [
            resource_id
            for resource_id in bound
            if resource_id.rsplit(":", 1)[-1] in routable
        ]
    if descriptor.specialist_id == "spl":
        skill_ids = frozenset(descriptor.skill_ids)
        bound.extend(
            item.resource_id
            for item in resource_registry.resources
            if item.kind == "skill" and item.resource_id.rsplit(":", 1)[-1] in skill_ids
        )
    return sorted(set(bound))


def derive_skill_specialist_skill_ids(skill_catalog: dict[str, Any]) -> list[str]:
    return sorted(
        skill_id
        for skill_id, row in skill_catalog.items()
        if bool(row.get("routable"))
    )


def validate_specialist_registry(
    registry: SpecialistRegistry,
    *,
    skill_catalog: dict[str, Any] | None = None,
    resource_registry: ResourceRegistry | None = None,
) -> None:
    skill_catalog = skill_catalog or load_skill_catalog()
    resource_registry = resource_registry or load_resource_registry()

    if len(registry.specialists) != 4:
        raise ValueError("specialist registry must define exactly four specialists")

    seen_ownership: set[str] = set()
    seen_purposes: set[str] = set()
    known_resources = {item.resource_id for item in resource_registry.resources}

    for descriptor in registry.specialists:
        overlap = seen_ownership.intersection(descriptor.ownership_scope)
        if overlap:
            raise ValueError(f"ownership_scope overlap: {sorted(overlap)}")
        seen_ownership.update(descriptor.ownership_scope)

        purpose_overlap = seen_purposes.intersection(descriptor.plan_purposes)
        if purpose_overlap:
            raise ValueError(f"plan_purpose overlap: {sorted(purpose_overlap)}")
        seen_purposes.update(descriptor.plan_purposes)

        bound_ids = derive_specialist_resource_ids(descriptor, resource_registry)
        missing = [item for item in bound_ids if item not in known_resources]
        if missing:
            raise ValueError(f"{descriptor.specialist_id} references unknown resources: {missing[:5]}")

        if descriptor.specialist_id == "skill":
            routable = derive_skill_specialist_skill_ids(skill_catalog)
            skill_resources = {
                resource_id.rsplit(":", 1)[-1]
                for resource_id in bound_ids
                if resource_id.startswith("skill:")
            }
            missing_skills = sorted(set(routable) - skill_resources)
            if missing_skills:
                raise ValueError(f"skill specialist missing routable skills: {missing_skills[:5]}")

        if descriptor.skill_ids:
            unknown_skills = [item for item in descriptor.skill_ids if item not in skill_catalog]
            if unknown_skills:
                raise ValueError(f"{descriptor.specialist_id} references unknown skills: {unknown_skills}")


def specialist_for_plan_purpose(purpose: str, registry: SpecialistRegistry | None = None) -> SpecialistId | None:
    registry = registry or load_specialist_registry()
    for descriptor in registry.specialists:
        if purpose in descriptor.plan_purposes:
            return descriptor.specialist_id
    return None


def specialist_owns_resource(
    specialist_id: SpecialistId,
    descriptor: ResourceDescriptor,
    *,
    registry: SpecialistRegistry | None = None,
) -> bool:
    registry = registry or load_specialist_registry()
    lane = registry.by_id(specialist_id)
    if lane is None:
        return False
    if descriptor.kind not in lane.resource_kinds:
        return False
    if specialist_id == "spl" and descriptor.kind == "skill":
        skill_name = descriptor.resource_id.rsplit(":", 1)[-1]
        return skill_name in lane.skill_ids
    return True


@lru_cache(maxsize=1)
def load_specialist_registry() -> SpecialistRegistry:
    payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry = SpecialistRegistry.model_validate(payload)
    validate_specialist_registry(registry)
    return registry


def clear_specialist_registry_cache() -> None:
    load_specialist_registry.cache_clear()
