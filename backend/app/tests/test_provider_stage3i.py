from __future__ import annotations

import json

from app.api.routes_settings import ProviderDraftCheckRequest, check_provider_draft, provider_settings_status
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.providers import (
    ProviderCapabilityProfile,
    ProviderOperationCategory,
    ProviderType,
    check_provider_operation_policy,
    mock_asset_inventory_profile,
    run_mock_asset_lookup,
    splunk_provider_profile,
)
from app.splunk.capabilities import build_splunk_capability_profile


def _registry(tools: list[str]) -> McpRegistryStatus:
    descriptors = [
        {
            "name": tool,
            "description": "",
            "capability": "spl_search" if "run_query" in tool else "metadata_lookup",
            "categories": [],
            "blocked": False,
            "blocked_reason": None,
        }
        for tool in tools
    ]
    return McpRegistryStatus(
        mode="mock",
        default_server="splunk_soc",
        global_execution_enabled=False,
        servers=[
            McpServerStatus(
                name="splunk_soc",
                type="splunk",
                enabled=True,
                implemented=True,
                configured=True,
                available=True,
                transport="mock",
                url_configured=False,
                command_configured=False,
                auth_mode="none",
                auth_configured=True,
                execution_enabled=False,
                discovered_tools_count=len(tools),
                discovered_tools_safe_names=tools,
                discovered_tools=descriptors,
                blocked_tools_count=0,
                blocked_tools_safe_names=[],
                splunk_app_id="7931",
                splunk_platform="mock",
                search_execution_allowed=False,
                saia_spl_generation_allowed=False,
                knowledge_object_discovery_allowed=True,
                list_tools_allowed=True,
            )
        ],
    )


def test_provider_profile_can_represent_splunk_mcp() -> None:
    splunk_profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]))
    provider = splunk_provider_profile(splunk_profile)

    assert provider.provider_id == "splunk_soc"
    assert provider.provider_type == ProviderType.SPLUNK_MCP
    assert ProviderOperationCategory.EVENT_QUERY in provider.discovered_operations
    assert ProviderOperationCategory.DISCOVERY in provider.discovered_operations
    assert provider.evidence_output_supported is True


def test_mock_asset_provider_returns_source_evidence() -> None:
    result = run_mock_asset_lookup(trace_id="trace-provider", query="host-a")

    assert result.status == "collected"
    assert result.source_evidence is not None
    assert result.source_evidence["source_type"] == "asset_inventory"
    assert result.source_evidence["provider_used"] == "mock_asset_inventory"
    assert result.source_evidence["collection_status"] == "collected"
    assert result.source_evidence["preview_rows"][0]["host"] == "host-a"


def test_blocked_operation_is_rejected() -> None:
    profile = mock_asset_inventory_profile()
    decision = check_provider_operation_policy(profile, ProviderOperationCategory.ADMIN_ACTION)

    assert decision.allowed is False
    assert decision.reason == "operation_blocked_by_policy"


def test_write_action_is_blocked_by_default() -> None:
    profile = ProviderCapabilityProfile(
        provider_id="future_ticketing",
        provider_type=ProviderType.TICKETING,
        available=True,
        environment_mode="coe",
        auth_configured=True,
        discovered_operations=[ProviderOperationCategory.WRITE_ACTION],
        allowed_operations=[ProviderOperationCategory.WRITE_ACTION],
        blocked_operations=[],
        read_only_supported=True,
        write_supported=False,
        evidence_output_supported=True,
    )

    decision = check_provider_operation_policy(profile, ProviderOperationCategory.WRITE_ACTION)

    assert decision.allowed is False
    assert decision.reason == "operation_blocked_by_policy"


def test_hil_required_operation_does_not_execute_without_approval() -> None:
    profile = mock_asset_inventory_profile(hil_required=True)
    result = run_mock_asset_lookup(trace_id="trace-provider-hil", query="host-a", profile=profile)

    assert result.status == "requires_human_review"
    assert result.source_evidence is None
    assert result.human_review is not None
    assert result.human_review["required"] is True
    assert result.reason == "human_review_required"


def test_provider_status_endpoint_returns_no_secrets(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://secret-user:secret-pass@example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "super-secret-token")

    serialized = json.dumps(provider_settings_status(), default=str).lower()

    for forbidden in ("super-secret-token", "secret-user", "secret-pass", "bearer "):
        assert forbidden not in serialized


def test_provider_status_includes_splunk_mcp_capability() -> None:
    payload = provider_settings_status()

    assert payload["splunk_capability"]["server_id"]
    assert any(provider["provider_type"] == "splunk_mcp" for provider in payload["providers"])
    assert "tool_groups" in payload


def test_provider_status_includes_mock_asset_inventory() -> None:
    payload = provider_settings_status()

    assert any(provider["provider_id"] == "mock_asset_inventory" for provider in payload["providers"])
    assert payload["tool_groups"]["asset_lookup"][0]["source_evidence_supported"] is True


def test_provider_status_hides_unconnected_planned_providers() -> None:
    payload = provider_settings_status()
    provider_types = {provider["provider_type"] for provider in payload["providers"]}

    assert provider_types == {"splunk_mcp", "asset_inventory"}
    assert "generic_mcp" not in provider_types
    assert "security_api" not in provider_types


def test_provider_draft_check_returns_no_secret() -> None:
    payload = check_provider_draft(
        ProviderDraftCheckRequest(
            provider_id="splunk_soc",
            provider_type="splunk_mcp",
            enabled=True,
            transport="streamable_http",
            auth_mode="bearer",
            base_url="",
            auth_token="super-secret-token",
        )
    )
    serialized = json.dumps(payload).lower()

    assert payload["validation_status"] == "fail"
    assert payload["auth_token_configured"] is True
    assert payload["not_persisted"] is True
    assert "super-secret-token" not in serialized
