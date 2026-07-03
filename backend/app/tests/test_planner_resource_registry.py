"""T0.1 — resource capability registry: load, uniqueness, safety invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.planner.resource_registry import (
    ResourceRegistry,
    clear_resource_registry_cache,
    load_resource_registry,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "skills" / "catalog.json"


@pytest.fixture()
def registry():
    clear_resource_registry_cache()
    return load_resource_registry(reload=True)


def test_registry_loads_with_unique_ids(registry) -> None:
    ids = [item.resource_id for item in registry.resources]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 70


def test_every_catalog_skill_has_a_registry_entry(registry) -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    registry_skills = {item.resource_id for item in registry.by_kind("skill")}
    for skill in catalog["skills"]:
        assert f"skill:{skill['skill_id']}" in registry_skills


def test_every_fallback_of_resolves(registry) -> None:
    known = {item.resource_id for item in registry.resources}
    for item in registry.resources:
        if item.fallback_of is not None:
            assert item.fallback_of in known, item.resource_id


def test_mutating_mcp_tools_are_blocked(registry) -> None:
    for item in registry.by_kind("mcp_tool"):
        name = item.resource_id.rsplit(":", 1)[-1]
        if name.startswith(("create_", "delete_")):
            assert item.availability == "blocked", item.resource_id
            assert item.policy_tier >= 3, item.resource_id


def test_no_mcp_tool_is_marked_available(registry) -> None:
    """Real MCP transport is not implemented; nothing may claim live availability."""
    for item in registry.by_kind("mcp_tool"):
        assert item.availability in {"not_implemented", "fixture_only", "blocked"}, item.resource_id


def test_active_template_families_have_lab_draft_fallbacks(registry) -> None:
    templates = {item.resource_id for item in registry.by_kind("spl_template_family")}
    assert templates, "expected governed template families"
    fallback_targets = {
        item.fallback_of for item in registry.by_kind("spl_lab_draft_family") if item.fallback_of
    }
    assert templates <= fallback_targets


def test_validation_rejects_unknown_fallback() -> None:
    broken = ResourceRegistry.model_validate(
        {
            "schema_version": 2,
            "resources": [
                {
                    "resource_id": "rag_corpus:x",
                    "kind": "rag_corpus",
                    "availability": "not_implemented",
                    "onboarding_status": "declared",
                    "fallback_of": "missing:resource",
                }
            ],
        }
    )
    from app.planner.resource_registry import _validate_registry

    with pytest.raises(ValueError, match="fallback_of"):
        _validate_registry(broken)
