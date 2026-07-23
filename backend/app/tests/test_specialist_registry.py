"""Specialist registry — disjoint ownership and canonical catalog validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.planner.planner_hierarchy import _SPECIALIST_OWNERSHIP
from app.planner.resource_registry import clear_resource_registry_cache, load_resource_registry
from app.planner.specialist_registry import (
    SpecialistRegistry,
    clear_specialist_registry_cache,
    derive_skill_specialist_skill_ids,
    derive_specialist_resource_ids,
    load_skill_catalog,
    load_specialist_registry,
    specialist_for_plan_purpose,
    specialist_owns_resource,
    validate_specialist_registry,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "skills" / "catalog.json"


@pytest.fixture(autouse=True)
def _clear_registry_caches() -> None:
    clear_resource_registry_cache()
    clear_specialist_registry_cache()


def test_specialist_registry_loads_four_lanes() -> None:
    registry = load_specialist_registry()
    assert isinstance(registry, SpecialistRegistry)
    assert {item.specialist_id for item in registry.specialists} == {
        "skill",
        "mcp",
        "knowledge",
        "spl",
    }


def test_specialist_ownership_is_disjoint() -> None:
    registry = load_specialist_registry()
    scopes: list[str] = []
    purposes: list[str] = []
    for item in registry.specialists:
        scopes.extend(item.ownership_scope)
        purposes.extend(item.plan_purposes)
    assert len(scopes) == len(set(scopes))
    assert len(purposes) == len(set(purposes))


def test_specialist_ownership_matches_hierarchy_contract() -> None:
    registry = load_specialist_registry()
    for item in registry.specialists:
        assert set(item.ownership_scope).issubset(_SPECIALIST_OWNERSHIP[item.specialist_id])


def test_every_specialist_resource_binding_exists_in_resource_registry() -> None:
    resource_registry = load_resource_registry(reload=True)
    specialist_registry = load_specialist_registry()
    known = {item.resource_id for item in resource_registry.resources}
    for lane in specialist_registry.specialists:
        bound = derive_specialist_resource_ids(lane, resource_registry)
        assert bound, lane.specialist_id
        assert all(resource_id in known for resource_id in bound), lane.specialist_id


def test_skill_specialist_covers_routable_catalog_skills() -> None:
    skill_catalog = load_skill_catalog()
    resource_registry = load_resource_registry(reload=True)
    skill_lane = load_specialist_registry().by_id("skill")
    assert skill_lane is not None
    routable = derive_skill_specialist_skill_ids(skill_catalog)
    bound_skills = {
        resource_id.rsplit(":", 1)[-1]
        for resource_id in derive_specialist_resource_ids(
            skill_lane,
            resource_registry,
            skill_catalog=skill_catalog,
        )
        if resource_id.startswith("skill:")
    }
    assert routable
    assert set(routable).issubset(bound_skills)


def test_mcp_specialist_only_binds_mcp_tools() -> None:
    resource_registry = load_resource_registry(reload=True)
    mcp_lane = load_specialist_registry().by_id("mcp")
    assert mcp_lane is not None
    bound = derive_specialist_resource_ids(mcp_lane, resource_registry)
    assert bound
    for resource_id in bound:
        descriptor = resource_registry.by_id(resource_id)
        assert descriptor is not None
        assert descriptor.kind == "mcp_tool"
        assert specialist_owns_resource("mcp", descriptor)


def test_knowledge_specialist_binds_rag_and_reference_analytics() -> None:
    resource_registry = load_resource_registry(reload=True)
    knowledge_lane = load_specialist_registry().by_id("knowledge")
    assert knowledge_lane is not None
    bound = derive_specialist_resource_ids(knowledge_lane, resource_registry)
    assert any(resource_id.startswith("rag_corpus:") for resource_id in bound)
    for resource_id in bound:
        descriptor = resource_registry.by_id(resource_id)
        assert descriptor is not None
        assert specialist_owns_resource("knowledge", descriptor)


def test_spl_specialist_binds_template_and_lab_draft_families() -> None:
    resource_registry = load_resource_registry(reload=True)
    spl_lane = load_specialist_registry().by_id("spl")
    assert spl_lane is not None
    bound = derive_specialist_resource_ids(spl_lane, resource_registry)
    kinds = {resource_registry.by_id(resource_id).kind for resource_id in bound}
    assert "spl_template_family" in kinds
    assert "spl_lab_draft_family" in kinds


def test_specialist_for_plan_purpose_maps_composer_purposes() -> None:
    registry = load_specialist_registry()
    assert specialist_for_plan_purpose("knowledge_retrieval", registry) == "knowledge"
    assert specialist_for_plan_purpose("spl_artifact", registry) == "spl"
    assert specialist_for_plan_purpose("mcp_execution", registry) == "mcp"
    assert specialist_for_plan_purpose("mitre_mapping", registry) == "knowledge"


def test_validate_specialist_registry_rejects_unknown_skill_reference() -> None:
    resource_registry = load_resource_registry(reload=True)
    skill_catalog = load_skill_catalog()
    registry = load_specialist_registry()
    spl_lane = registry.by_id("spl")
    assert spl_lane is not None
    broken = spl_lane.model_copy(update={"skill_ids": ["not_a_real_skill"]})
    broken_registry = registry.model_copy(
        update={"specialists": [item if item.specialist_id != "spl" else broken for item in registry.specialists]}
    )
    with pytest.raises(ValueError, match="unknown skills"):
        validate_specialist_registry(
            broken_registry,
            skill_catalog=skill_catalog,
            resource_registry=resource_registry,
        )


def test_skill_catalog_json_still_loads_for_crosswalk() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert "skills" in catalog
    assert len(catalog["skills"]) >= 5
