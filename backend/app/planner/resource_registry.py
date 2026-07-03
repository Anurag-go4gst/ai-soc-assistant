"""Resource Capability Registry — deterministic view of planner-composable resources.

Registry data lives in ``resource_registry_v1.json`` (schema v2). Planner code
selects rows; execution still flows through validators and gates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_REGISTRY_PATH = Path(__file__).resolve().parent / "resource_registry_v1.json"
_REGISTRY_CACHE: "ResourceRegistry | None" = None

ResourceKind = Literal[
    "mcp_tool",
    "rag_corpus",
    "deterministic_analytic",
    "spl_template_family",
    "spl_lab_draft_family",
    "llm_role",
    "http_api",
    "api",
    "skill",
    "action_tool",
]

Availability = Literal["available", "fixture_only", "not_implemented", "blocked"]

OnboardingStatus = Literal[
    "declared",
    "contract_verified",
    "fixture_tested",
    "live_smoked",
]

DispatchMode = Literal["mock", "live"]

_ONBOARDING_RANK: dict[OnboardingStatus, int] = {
    "declared": 0,
    "contract_verified": 1,
    "fixture_tested": 2,
    "live_smoked": 3,
}

_BUILTIN_KINDS = frozenset({
    "skill",
    "llm_role",
    "rag_corpus",
    "spl_template_family",
    "spl_lab_draft_family",
    "deterministic_analytic",
})


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
    read_only: bool = True
    auth_contract: dict[str, Any] = Field(default_factory=dict)
    onboarding_status: OnboardingStatus = "declared"

    @field_validator("kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: Any) -> str:
        kind = str(value or "").strip()
        if kind == "api":
            return "http_api"
        return kind

    @model_validator(mode="after")
    def _apply_v2_defaults(self) -> "ResourceDescriptor":
        if self.kind == "mcp_tool" and "read_only" not in self.model_fields_set:
            object.__setattr__(self, "read_only", _default_read_only_mcp(self))
        return self


class ResourceRegistry(BaseModel):
    schema_version: int
    resources: list[ResourceDescriptor]

    def by_id(self, resource_id: str) -> ResourceDescriptor | None:
        return self._index().get(resource_id)

    def by_kind(self, kind: ResourceKind | str) -> list[ResourceDescriptor]:
        normalized = "http_api" if kind == "api" else kind
        return [item for item in self.resources if item.kind == normalized]

    def _index(self) -> dict[str, ResourceDescriptor]:
        return {item.resource_id: item for item in self.resources}


def onboarding_rank(status: OnboardingStatus | str) -> int:
    return _ONBOARDING_RANK.get(str(status), -1)  # type: ignore[arg-type]


def is_fixture_dispatchable(descriptor: ResourceDescriptor) -> bool:
    if descriptor.availability != "fixture_only":
        return False
    return onboarding_rank(descriptor.onboarding_status) >= onboarding_rank("fixture_tested")


def is_live_dispatchable(descriptor: ResourceDescriptor) -> bool:
    if descriptor.availability != "available":
        return False
    return descriptor.onboarding_status == "live_smoked"


def is_registry_dispatchable(descriptor: ResourceDescriptor, *, mode: DispatchMode) -> bool:
    if descriptor.availability in {"blocked", "not_implemented"}:
        return False
    if descriptor.onboarding_status == "declared":
        return False
    if mode == "live":
        return is_live_dispatchable(descriptor)
    if descriptor.availability == "fixture_only":
        return is_fixture_dispatchable(descriptor)
    if descriptor.availability == "available":
        return onboarding_rank(descriptor.onboarding_status) >= onboarding_rank("fixture_tested")
    return False


def registry_dispatch_mode() -> DispatchMode:
    from app.config import settings

    return "live" if settings.mcp_mode.strip().lower() == "registry" else "mock"


def is_composer_dispatchable(descriptor: ResourceDescriptor, *, mode: DispatchMode | None = None) -> bool:
    """Built-in planner resources keep legacy reachability; external connectors use onboarding matrix."""
    dispatch_mode = mode or registry_dispatch_mode()
    kind = descriptor.kind
    if kind in _BUILTIN_KINDS or kind == "skill":
        return descriptor.availability in {"available", "fixture_only"}
    return is_registry_dispatchable(descriptor, mode=dispatch_mode)


def load_resource_registry(*, reload: bool = False) -> ResourceRegistry:
    global _REGISTRY_CACHE
    if not reload and _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 1)) < 2:
        payload = _upgrade_payload_to_v2(payload)
        _REGISTRY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    registry = ResourceRegistry.model_validate(payload)
    _validate_registry(registry)
    _REGISTRY_CACHE = registry
    return registry


def clear_resource_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


def _upgrade_payload_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for row in payload.get("resources") or []:
        if not isinstance(row, dict):
            continue
        upgraded = dict(row)
        if upgraded.get("kind") == "api":
            upgraded["kind"] = "http_api"
        upgraded.setdefault("read_only", _default_read_only_from_dict(upgraded))
        upgraded.setdefault("auth_contract", {})
        upgraded.setdefault("onboarding_status", _default_onboarding_status_from_dict(upgraded))
        resources.append(upgraded)
    if not any(r.get("resource_id") == "http_api:cisco_api_placeholder" for r in resources):
        resources.append({
            "resource_id": "http_api:cisco_api_placeholder",
            "kind": "http_api",
            "capabilities": ["vendor_intel_lookup"],
            "input_contract": {},
            "cost_class": "cheap",
            "availability": "not_implemented",
            "policy_tier": 2,
            "read_only": True,
            "auth_contract": {"bearer_token_env": "CISCO_API_TOKEN"},
            "onboarding_status": "declared",
            "notes": "Declared-only placeholder until operator provides Cisco API contract",
        })
    return {"schema_version": 2, "resources": resources}


def _default_onboarding_status(item: ResourceDescriptor) -> OnboardingStatus:
    return _default_onboarding_status_from_dict(item.model_dump())


def _default_onboarding_status_from_dict(row: dict[str, Any]) -> OnboardingStatus:
    availability = str(row.get("availability") or "not_implemented")
    if availability == "blocked":
        return "declared"
    if availability in {"fixture_only", "available"}:
        return "fixture_tested"
    return "declared"


def _default_read_only_mcp(item: ResourceDescriptor) -> bool:
    return _default_read_only_from_dict(item.model_dump())


def _default_read_only_from_dict(row: dict[str, Any]) -> bool:
    kind = str(row.get("kind") or "")
    if kind == "api":
        kind = "http_api"
    if kind == "action_tool":
        return False
    if kind == "mcp_tool":
        name = str(row.get("resource_id") or "").rsplit(":", 1)[-1]
        if any(token in name for token in ("run_query", "saved_search", "run_saved_search")):
            return False
        return True
    return True


def _validate_registry(registry: ResourceRegistry) -> None:
    if registry.schema_version < 2:
        raise ValueError("resource registry schema_version must be >= 2")
    ids = [item.resource_id for item in registry.resources]
    duplicates = {item for item in ids if ids.count(item) > 1}
    if duplicates:
        raise ValueError(f"duplicate resource ids: {sorted(duplicates)}")
    known = set(ids)
    for item in registry.resources:
        if item.fallback_of is not None and item.fallback_of not in known:
            raise ValueError(f"{item.resource_id}: fallback_of {item.fallback_of!r} not in registry")
        if item.kind == "mcp_tool" and _is_mutating_tool(item) and item.availability != "blocked":
            raise ValueError(f"{item.resource_id}: mutating/admin MCP tool must be blocked")
        if item.onboarding_status == "declared" and item.availability in {"available", "fixture_only"}:
            raise ValueError(f"{item.resource_id}: declared onboarding incompatible with {item.availability}")


def _is_mutating_tool(item: ResourceDescriptor) -> bool:
    name = item.resource_id.rsplit(":", 1)[-1]
    return any(token in name for token in ("create_", "delete_", "write", "admin"))
