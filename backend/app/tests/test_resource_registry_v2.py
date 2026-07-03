"""T4.1 — resource registry schema v2, onboarding matrix, backwards compat."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.planner.resource_registry import (
    ResourceDescriptor,
    ResourceRegistry,
    clear_resource_registry_cache,
    is_fixture_dispatchable,
    is_live_dispatchable,
    is_registry_dispatchable,
    load_resource_registry,
    onboarding_rank,
)

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "planner" / "resource_registry_v1.json"
V1_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "resource_registry_v1_snapshot.json"


@pytest.fixture()
def registry():
    clear_resource_registry_cache()
    return load_resource_registry(reload=True)


def test_schema_version_is_v2(registry) -> None:
    assert registry.schema_version == 2


def test_cisco_api_placeholder_declared_only(registry) -> None:
    row = registry.by_id("http_api:cisco_api_placeholder")
    assert row is not None
    assert row.kind == "http_api"
    assert row.onboarding_status == "declared"
    assert row.availability == "not_implemented"
    assert not is_registry_dispatchable(row, mode="mock")
    assert not is_registry_dispatchable(row, mode="live")


def test_legacy_api_kind_alias_loads() -> None:
    payload = {
        "schema_version": 2,
        "resources": [
            {
                "resource_id": "api:legacy_vendor",
                "kind": "api",
                "availability": "not_implemented",
                "onboarding_status": "declared",
            }
        ],
    }
    reg = ResourceRegistry.model_validate(payload)
    assert reg.resources[0].kind == "http_api"


def test_dispatch_matrix_fixture_only() -> None:
    row = ResourceDescriptor(
        resource_id="mcp_tool:mock_search",
        kind="mcp_tool",
        availability="fixture_only",
        onboarding_status="fixture_tested",
    )
    assert is_fixture_dispatchable(row)
    assert is_registry_dispatchable(row, mode="mock")
    assert not is_live_dispatchable(row)
    assert not is_registry_dispatchable(row, mode="live")


def test_dispatch_matrix_live_smoked() -> None:
    row = ResourceDescriptor(
        resource_id="mcp_tool:live_search",
        kind="mcp_tool",
        availability="available",
        onboarding_status="live_smoked",
    )
    assert is_live_dispatchable(row)
    assert is_registry_dispatchable(row, mode="live")
    assert not is_fixture_dispatchable(row)


def test_declared_never_dispatchable() -> None:
    row = ResourceDescriptor(
        resource_id="http_api:vendor",
        kind="http_api",
        availability="fixture_only",
        onboarding_status="declared",
    )
    assert not is_registry_dispatchable(row, mode="mock")
    assert not is_registry_dispatchable(row, mode="live")


def test_not_implemented_never_dispatchable() -> None:
    row = ResourceDescriptor(
        resource_id="action_tool:itsm_ticket",
        kind="action_tool",
        availability="not_implemented",
        onboarding_status="fixture_tested",
    )
    assert not is_registry_dispatchable(row, mode="mock")


def test_onboarding_rank_order() -> None:
    assert onboarding_rank("declared") < onboarding_rank("contract_verified")
    assert onboarding_rank("contract_verified") < onboarding_rank("fixture_tested")
    assert onboarding_rank("fixture_tested") < onboarding_rank("live_smoked")


def test_v1_snapshot_rows_preserve_dispatch_behavior(registry) -> None:
    """Every fixture_only row in the committed registry stays mock-dispatchable."""
    for item in registry.resources:
        if item.availability == "fixture_only":
            assert item.onboarding_status in {"fixture_tested", "live_smoked"}, item.resource_id
            assert is_registry_dispatchable(item, mode="mock"), item.resource_id


def test_http_api_rows_migrated_from_api_kind(registry) -> None:
    http_rows = registry.by_kind("http_api")
    assert len(http_rows) >= 4
    assert all(row.kind == "http_api" for row in http_rows)
    assert registry.by_kind("api") == http_rows


def test_action_tool_kind_accepted() -> None:
    row = ResourceDescriptor(
        resource_id="action_tool:mock_itsm_create",
        kind="action_tool",
        availability="fixture_only",
        onboarding_status="fixture_tested",
        read_only=False,
    )
    assert not row.read_only
    assert is_registry_dispatchable(row, mode="mock")
