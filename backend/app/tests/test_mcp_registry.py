import json

from app.connectors.mcp.registry import load_mcp_registry_status


def test_default_mock_mode_still_available(monkeypatch) -> None:
    monkeypatch.delenv("MCP_MODE", raising=False)
    status = load_mcp_registry_status()
    assert status.mode == "mock"
    assert status.global_execution_enabled is False
    assert status.servers[0].available is True
    assert status.servers[0].execution_enabled is False
    assert "splunk_run_query" in status.servers[0].discovered_tools_safe_names
    # user_info (self identity, read-only) is enabled/RBAC-gated, not blocked.
    assert "splunk_get_user_info" in status.servers[0].discovered_tools_safe_names
    # SAIA generative tools are conditional + blocked.
    assert "saia_generate_spl" in status.servers[0].blocked_tools_safe_names


def test_registry_mode_parses_multiple_servers(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc,asset_inventory,ticketing")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "super-secret-token")
    monkeypatch.setenv(
        "MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST",
        "splunk_run_query,splunk_get_indexes,splunk_get_metadata,splunk_get_knowledge_objects",
    )
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_TYPE", "asset_inventory")
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_TRANSPORT", "sse")
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_URL", "https://assets.example.invalid/sse")
    monkeypatch.setenv("MCP_SERVER_TICKETING_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_TICKETING_TYPE", "ticketing")
    monkeypatch.setenv("MCP_SERVER_TICKETING_TRANSPORT", "stdio")
    monkeypatch.setenv("MCP_SERVER_TICKETING_COMMAND", "/opt/mcp/ticketing")

    status = load_mcp_registry_status()

    assert [server.name for server in status.servers] == ["splunk_soc", "asset_inventory", "ticketing"]
    assert status.global_execution_enabled is False
    assert all(server.execution_enabled is False for server in status.servers)
    splunk = status.servers[0]
    assert splunk.type == "splunk"
    assert splunk.splunk_app_id == "7931"
    assert splunk.search_execution_allowed is False
    assert splunk.saia_spl_generation_allowed is False
    assert splunk.knowledge_object_discovery_allowed is True
    assert splunk.list_tools_allowed is True
    assert "splunk_run_query" in splunk.discovered_tools_safe_names
    assert "splunk_get_knowledge_objects" in splunk.discovered_tools_safe_names

    text = json.dumps(status, default=lambda obj: getattr(obj, "__dict__", str(obj))).lower()
    assert "super-secret-token" not in text


def test_registry_classifies_risky_tools_as_blocked(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "none")
    monkeypatch.setenv(
        "MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST",
        "run_splunk_query,generate_spl,saia_assistant,outputlookup,collect,delete,sendemail,write_admin,rest_script",
    )

    server = load_mcp_registry_status().servers[0]

    assert "run_splunk_query" in server.discovered_tools_safe_names
    for blocked in ("outputlookup", "collect", "delete", "sendemail", "write_admin", "rest_script", "generate_spl", "saia_assistant"):
        assert blocked in server.blocked_tools_safe_names


def test_missing_credentials_mark_only_one_server_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc,asset_inventory")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.delenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_TYPE", "asset_inventory")
    monkeypatch.setenv("MCP_SERVER_ASSET_INVENTORY_URL", "https://assets.example.invalid/mcp")

    status = load_mcp_registry_status()

    by_name = {server.name: server for server in status.servers}
    assert by_name["splunk_soc"].available is False
    assert by_name["splunk_soc"].last_error == "missing_auth_configuration"
    assert by_name["asset_inventory"].available is True


def test_unknown_server_type_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "unknown")
    monkeypatch.setenv("MCP_SERVER_UNKNOWN_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_UNKNOWN_TYPE", "not_real")
    monkeypatch.setenv("MCP_SERVER_UNKNOWN_URL", "https://unknown.example.invalid/mcp")

    server = load_mcp_registry_status().servers[0]

    assert server.implemented is False
    assert server.available is False
    assert server.last_error == "unsupported_mcp_server_type"
