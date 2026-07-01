"""Resource Capability Registry (T0.1) — one deterministic view of every
resource the planner may compose: MCP tools, RAG corpora, SPL template and
lab-draft families, LLM roles, skills, and future APIs.

The registry is data (`resource_registry_v1.json`), never behavior. Planner
code selects registry rows; execution still flows through the existing
validators and gates. Mutating/admin MCP tools are registered with
`availability="blocked"` so plans can name them only to refuse them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import json

from pydantic import BaseModel, Field

_REGISTRY_PATH = Path(__file__).resolve().parent / "resource_registry_v1.json"
_REGISTRY_CACHE: "ResourceRegistry | None" = None

ResourceKind = Literal[
    "mcp_tool",
    "rag_corpus",
    "deterministic_analytic",
    "spl_template_family",
    "spl_lab_draft_family",
    "llm_role",
    "api",
    "skill",
]

Availability = Literal["available", "fixture_only", "not_implemented", "blocked"]


class ResourceDescriptor(BaseModel):
    resource_id: str
    kind: ResourceKind
    capabilities: list[str] = Field(default_factory=list)
    input_contract: dict[str, Any] = Field(default_factory=dict)
    cost_class: Literal["free", "cheap", "expensive"] = "cheap"
    availability: Availability = "not_implemented"
    policy_tier: int = 1
    fallback_of: str | None = None
    notes: str | None = None
    capability_class: str | None = None


class ResourceRegistry(BaseModel):
    schema_version: int
    resources: list[ResourceDescriptor]

    def by_id(self, resource_id: str) -> ResourceDescriptor | None:
        return self._index().get(resource_id)

    def by_kind(self, kind: ResourceKind) -> list[ResourceDescriptor]:
        return [item for item in self.resources if item.kind == kind]

    def _index(self) -> dict[str, ResourceDescriptor]:
        return {item.resource_id: item for item in self.resources}


def load_resource_registry(*, reload: bool = False) -> ResourceRegistry:
    global _REGISTRY_CACHE
    if not reload and _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry = ResourceRegistry.model_validate(payload)
    _validate_registry(registry)
    _REGISTRY_CACHE = registry
    return registry


def clear_resource_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


def _validate_registry(registry: ResourceRegistry) -> None:
    ids = [item.resource_id for item in registry.resources]
    duplicates = {item for item in ids if ids.count(item) > 1}
    if duplicates:
        raise ValueError(f"duplicate resource ids: {sorted(duplicates)}")
    known = set(ids)
    for item in registry.resources:
        if item.fallback_of is not None and item.fallback_of not in known:
            raise ValueError(
                f"{item.resource_id}: fallback_of {item.fallback_of!r} not in registry"
            )
        if item.kind == "mcp_tool" and _is_mutating_tool(item) and item.availability != "blocked":
            raise ValueError(
                f"{item.resource_id}: mutating/admin MCP tool must be blocked"
            )


def _is_mutating_tool(item: ResourceDescriptor) -> bool:
    name = item.resource_id.rsplit(":", 1)[-1]
    return any(token in name for token in ("create_", "delete_", "write", "admin"))
