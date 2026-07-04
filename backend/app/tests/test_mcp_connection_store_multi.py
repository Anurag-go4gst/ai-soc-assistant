import json
import os

from app.config import settings
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.connection_store import (
    apply_to_settings,
    effective_connection,
    list_other_servers,
    record_splunk_check,
    save_connection,
    save_other_server,
)
from app.connectors.mcp.registry import load_mcp_registry_status


def _use_temp_store(monkeypatch, tmp_path):
    store_path = tmp_path / "mcp_connection.json"
    monkeypatch.setattr(settings, "ai_soc_mcp_connection_store_path", str(store_path))
    for key in list(os.environ):
        if key == "MCP_MODE" or key == "MCP_SERVERS" or key == "MCP_DEFAULT_SERVER" or key == "MCP_GLOBAL_EXECUTION_ENABLED" or key.startswith("MCP_SERVER_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings, "mcp_mode", "mock")
    monkeypatch.setattr(settings, "mcp_servers", "")
    monkeypatch.setattr(settings, "mcp_default_server", "splunk_soc")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_environment_mode", "coe")
    monkeypatch.setattr(settings, "splunk_mcp_enabled", False)
    monkeypatch.setattr(settings, "splunk_mcp_discovery_mode", "dynamic")
    monkeypatch.setattr(settings, "splunk_mcp_base_url", "")
    monkeypatch.setattr(settings, "splunk_mcp_token", "")
    monkeypatch.setattr(settings, "splunk_saia_tools_enabled", True)
    monkeypatch.setattr(settings, "splunk_ai_assistant_mode", "auto")
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", False)
    return store_path


def test_save_splunk_uses_multi_section_document_and_preserves_other_servers(monkeypatch, tmp_path) -> None:
    store_path = _use_temp_store(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "splunk": {"enabled": False, "url": "", "bearer_token": "old-token"},
                "other_servers": [
                    {
                        "server_id": "asset_inventory",
                        "display_name": "Asset inventory",
                        "provider_type": "asset_inventory",
                        "enabled": True,
                        "transport": "sse",
                        "url": "https://assets.example.invalid/sse",
                        "auth_method": "none",
                        "execution_enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token=None,
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=True,
        updated_by="pytest",
    )

    document = json.loads(store_path.read_text(encoding="utf-8"))
    assert set(document) == {"other_servers", "splunk"}
    assert document["splunk"]["bearer_token"] == "old-token"
    assert [server["server_id"] for server in document["other_servers"]] == ["asset_inventory"]
    assert os.environ["MCP_SERVERS"] == "splunk_soc,asset_inventory"
    assert settings.mcp_mode == "registry"
    assert settings.mcp_global_execution_enabled is True


def test_apply_legacy_flat_document_sets_settings_and_global_execution(monkeypatch, tmp_path) -> None:
    store_path = _use_temp_store(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "deployment_mode": "coe",
                "discovery_policy": "dynamic",
                "transport": "streamable_http",
                "auth_method": "bearer",
                "url": "https://splunk-mcp.example.invalid/mcp",
                "bearer_token": "legacy-token",
                "timeout_seconds": 9,
                "execution_enabled": True,
            }
        ),
        encoding="utf-8",
    )

    apply_to_settings()

    assert settings.mcp_mode == "registry"
    assert settings.mcp_servers == "splunk_soc"
    assert settings.mcp_global_execution_enabled is True
    assert settings.splunk_mcp_base_url == "https://splunk-mcp.example.invalid/mcp"
    assert settings.splunk_mcp_token == "legacy-token"
    assert os.environ["MCP_GLOBAL_EXECUTION_ENABLED"] == "true"
    assert os.environ["MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED"] == "true"


def test_other_server_save_merges_with_splunk_and_defaults_execution_false(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token="splunk-token",
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=True,
        updated_by="pytest",
    )

    save_other_server(
        server_id="asset_inventory",
        display_name="Asset inventory",
        provider_type="asset_inventory",
        url="https://assets.example.invalid/mcp",
        bearer_token=None,
        auth_method="none",
        discovered_tools=["asset_lookup"],
        updated_by="pytest",
    )

    status = load_mcp_registry_status()
    by_name = {server.name: server for server in status.servers}
    assert list(by_name) == ["splunk_soc", "asset_inventory"]
    assert by_name["splunk_soc"].execution_enabled is True
    assert by_name["asset_inventory"].execution_enabled is False
    assert by_name["asset_inventory"].discovered_tools_safe_names == ["asset_lookup"]


def test_connector_and_registry_use_applied_splunk_flags(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token="splunk-token",
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=True,
        updated_by="pytest",
    )

    assert settings.mcp_mode == "registry"
    assert settings.mcp_global_execution_enabled is True
    assert load_mcp_registry_status().global_execution_enabled is True
    assert type(get_mcp_connector()).__name__ == "SplunkMcpConnector"


def test_splunk_check_fields_persist_when_connection_is_resaved(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token="splunk-token",
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=False,
        updated_by="pytest",
    )
    record_splunk_check(
        status="Not connected",
        failure_reason="Bearer token is required for this MCP connection.",
        technical_detail="credentials_missing",
        discovered_tools=["splunk_run_query"],
    )

    save_connection(
        enabled=True,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token=None,
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=False,
        updated_by="pytest",
    )

    connection = effective_connection()
    assert connection["last_check_status"] == "Not connected"
    assert connection["last_error"] == "Bearer token is required for this MCP connection."
    assert connection["last_technical_detail"] == "credentials_missing"


def test_splunk_check_only_document_keeps_runtime_in_mock_mode(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "splunk_mcp_enabled", True)
    record_splunk_check(
        status="Not connected",
        failure_reason="MCP URL is missing or invalid.",
        technical_detail="mcp_url_is_required",
        discovered_tools=[],
    )

    assert effective_connection()["last_check_status"] == "Not connected"
    assert settings.mcp_mode == "mock"
    assert settings.mcp_servers == ""
    assert settings.mcp_default_server == "splunk_soc"
    assert settings.splunk_saia_tools_enabled is True
    assert settings.splunk_ai_assistant_mode == "auto"
    assert os.environ["MCP_MODE"] == "mock"
    assert os.environ["MCP_SERVERS"] == ""


def test_default_server_switches_to_enabled_other_server_when_splunk_disabled(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    save_connection(
        enabled=False,
        deployment_mode="coe",
        discovery_policy="dynamic",
        transport="streamable_http",
        auth_method="bearer",
        url="https://splunk-mcp.example.invalid/mcp",
        bearer_token="splunk-token",
        timeout_seconds=7,
        saia_tools_enabled=False,
        splunk_ai_assistant_mode="auto",
        allow_saved_search=False,
        execution_enabled=False,
        updated_by="pytest",
    )
    save_other_server(
        server_id="asset_inventory",
        display_name="Asset inventory",
        provider_type="asset_inventory",
        url="https://assets.example.invalid/mcp",
        bearer_token=None,
        auth_method="none",
        execution_enabled=False,
        updated_by="pytest",
    )

    assert settings.mcp_servers == "asset_inventory"
    assert settings.mcp_default_server == "asset_inventory"
    assert os.environ["MCP_DEFAULT_SERVER"] == "asset_inventory"


def test_string_discovered_tools_are_returned_with_names(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)
    save_other_server(
        server_id="asset_inventory",
        display_name="Asset inventory",
        provider_type="asset_inventory",
        url="https://assets.example.invalid/mcp",
        bearer_token=None,
        auth_method="none",
        discovered_tools=["asset_lookup"],
        updated_by="pytest",
    )

    listed = list_other_servers()
    assert listed[0]["discovered_tools"] == [
        {
            "name": "asset_lookup",
            "description": "",
            "capability": "unknown",
            "categories": [],
            "blocked": False,
            "blocked_reason": None,
        }
    ]
