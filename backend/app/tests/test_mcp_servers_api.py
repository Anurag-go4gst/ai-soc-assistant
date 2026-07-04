import json
import os
from urllib.error import URLError

from app.api import routes_settings
from app.api.routes_settings import (
    McpConnectionSaveRequest,
    McpServerSaveRequest,
    delete_mcp_server,
    discover_mcp_server,
    get_mcp_connection,
    list_mcp_servers,
    save_mcp_connection,
    save_mcp_server,
    test_mcp_connection as run_mcp_connection_test,
)
from app.config import settings


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _fake_user() -> dict[str, str]:
    return {"username": "pytest", "role": "platform_admin"}


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


def _setup(monkeypatch, tmp_path) -> None:
    _use_temp_store(monkeypatch, tmp_path)


def test_splunk_connection_save_accepts_execution_enabled(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path)

    payload = save_mcp_connection(
        McpConnectionSaveRequest(
            enabled=True,
            deployment_mode="coe",
            discovery_policy="dynamic",
            transport="streamable_http",
            auth_method="bearer",
            url="https://splunk-mcp.example.invalid/mcp",
            bearer_token="splunk-secret-token",
            timeout_seconds=10,
            execution_enabled=True,
        ),
        user=_fake_user(),
    )

    assert payload["saved"] is True
    assert payload["connection"]["execution_enabled"] is True
    assert payload["connection"]["bearer_token_configured"] is True
    assert "splunk-secret-token" not in json.dumps(payload)
    assert settings.mcp_mode == "registry"
    assert settings.mcp_global_execution_enabled is True


def test_other_server_crud_rejects_splunk_and_redacts_secrets(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path)

    rejected = save_mcp_server(
        McpServerSaveRequest(
            server_id="splunk_soc",
            provider_type="splunk",
            url="https://splunk-mcp.example.invalid/mcp",
            auth_method="none",
        ),
        user=_fake_user(),
    )
    saved = save_mcp_server(
        McpServerSaveRequest(
            server_id="asset_inventory",
            display_name="Asset inventory",
            provider_type="asset_inventory",
            enabled=True,
            transport="streamable_http",
            url="https://assets.example.invalid/mcp",
            auth_method="bearer",
            bearer_token="asset-secret-token",
        ),
        user=_fake_user(),
    )
    listed = list_mcp_servers(_user=_fake_user())
    deleted = delete_mcp_server("asset_inventory", _user=_fake_user())

    assert rejected["saved"] is False
    assert "splunk_server_managed_on_providers_tab" in rejected["validation_errors"]
    assert saved["saved"] is True
    assert saved["server"]["bearer_token_configured"] is True
    assert saved["server"]["execution_enabled"] is False
    assert "asset-secret-token" not in json.dumps(saved)
    assert "asset-secret-token" not in json.dumps(listed)
    assert listed["servers"][0]["server_id"] == "asset_inventory"
    assert deleted == {"deleted": True}


def test_other_server_discover_stores_status_tools_and_errors(monkeypatch, tmp_path) -> None:
    methods: list[str] = []

    def fake_urlopen(request: object, **_kwargs: object) -> _Response:
        body = getattr(request, "data", b"") or b"{}"
        method = json.loads(body.decode("utf-8")).get("method")
        methods.append(method)
        if method == "initialize":
            return _Response({"jsonrpc": "2.0", "id": "init", "result": {"serverInfo": {"name": "assets"}}})
        return _Response(
            {
                "jsonrpc": "2.0",
                "id": "tools",
                "result": {"tools": [{"name": "asset_lookup"}, {"name": "asset_write_admin"}]},
            }
        )

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)
    _setup(monkeypatch, tmp_path)
    saved = save_mcp_server(
        McpServerSaveRequest(
            server_id="asset_inventory",
            display_name="Asset inventory",
            provider_type="asset_inventory",
            enabled=True,
            transport="streamable_http",
            url="https://assets.example.invalid/mcp",
            auth_method="none",
        ),
        user=_fake_user(),
    )
    discovered = discover_mcp_server("asset_inventory", _user=_fake_user())
    listed = list_mcp_servers(_user=_fake_user())

    assert saved["saved"] is True
    assert methods == ["initialize", "tools/list"]
    assert discovered["result"]["status"] == "Connected"
    server = discovered["server"]
    assert server["last_check_status"] == "Connected"
    assert server["last_error"] == "Connection is valid, but execution tools remain gated by policy."
    assert server["last_technical_detail"] == "safe_discovery_only"
    assert [tool["name"] for tool in server["discovered_tools"]] == ["asset_lookup", "asset_write_admin"]
    assert listed["servers"][0]["last_check_status"] == "Connected"


def test_splunk_test_persists_failure_status(monkeypatch, tmp_path) -> None:
    def fake_urlopen(_request: object, **_kwargs: object) -> _Response:
        raise URLError("connection refused")

    monkeypatch.setattr(routes_settings, "urlopen", fake_urlopen)
    _setup(monkeypatch, tmp_path)
    saved = save_mcp_connection(
        McpConnectionSaveRequest(
            enabled=True,
            deployment_mode="coe",
            discovery_policy="dynamic",
            transport="streamable_http",
            auth_method="bearer",
            url="https://splunk-mcp.example.invalid/mcp",
            bearer_token="splunk-secret-token",
            timeout_seconds=10,
        ),
        user=_fake_user(),
    )
    result = run_mcp_connection_test(payload=None)
    connection = get_mcp_connection(_user=_fake_user())["connection"]

    assert saved["saved"] is True
    assert result["status"] == "Not connected"
    assert connection["last_check_status"] == "Not connected"
    assert connection["last_error"] == result["failure_reason"]
    assert connection["last_technical_detail"] == result["technical_error_detail"]


def test_other_server_blank_url_edit_preserves_existing_url(monkeypatch, tmp_path) -> None:
    _setup(monkeypatch, tmp_path)
    saved = save_mcp_server(
        McpServerSaveRequest(
            server_id="asset_inventory",
            display_name="Asset inventory",
            provider_type="asset_inventory",
            enabled=True,
            transport="streamable_http",
            url="https://assets.example.invalid/mcp",
            auth_method="none",
        ),
        user=_fake_user(),
    )
    edited = save_mcp_server(
        McpServerSaveRequest(
            server_id="asset_inventory",
            display_name="Renamed assets",
            provider_type="asset_inventory",
            enabled=True,
            transport="streamable_http",
            url="",
            auth_method="none",
        ),
        user=_fake_user(),
    )
    listed = list_mcp_servers(_user=_fake_user())["servers"]

    assert saved["saved"] is True
    assert edited["saved"] is True
    assert edited["server"]["display_name"] == "Renamed assets"
    assert edited["server"]["url_configured"] is True
    assert listed[0]["url_configured"] is True
