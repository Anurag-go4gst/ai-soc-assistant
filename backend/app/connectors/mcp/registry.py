from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from app.connectors.mcp.discovery import McpToolDescriptor, classify_mcp_tool, mock_discovered_tools, safe_tool_name


SUPPORTED_MCP_TYPES = {"splunk", "generic", "asset_inventory", "ticketing", "knowledge"}
SUPPORTED_TRANSPORTS = {"streamable_http", "sse", "stdio"}
SUPPORTED_AUTH_MODES = {"none", "bearer", "basic"}
EXECUTION_TOOL_PATTERNS = (
    "saia",
    "assistant",
    "generate",
    "explain",
    "optimize",
    "outputlookup",
    "collect",
    "delete",
    "sendemail",
    "write",
    "modify",
    "admin",
    "rest",
    "script",
)


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    enabled: bool = False
    server_type: str = "generic"
    transport: str = "streamable_http"
    url: str = ""
    command: str = ""
    args: str = ""
    auth_mode: str = "none"
    bearer_token: str = ""
    username: str = ""
    password: str = ""
    connect_timeout_seconds: int = 10
    tool_allowlist: list[str] = field(default_factory=list)
    execution_enabled: bool = False
    splunk_app_id: str = "7931"
    splunk_platform: str = "unknown"


@dataclass(frozen=True)
class McpServerStatus:
    name: str
    type: str
    enabled: bool
    implemented: bool
    configured: bool
    available: bool
    transport: str
    url_configured: bool
    command_configured: bool
    auth_mode: str
    auth_configured: bool
    execution_enabled: bool
    discovered_tools_count: int
    discovered_tools_safe_names: list[str]
    discovered_tools: list[dict[str, Any]]
    blocked_tools_count: int
    blocked_tools_safe_names: list[str]
    last_error: str | None = None
    splunk_app_id: str | None = None
    splunk_platform: str | None = None
    search_execution_allowed: bool | None = None
    saia_spl_generation_allowed: bool | None = None
    knowledge_object_discovery_allowed: bool | None = None
    list_tools_allowed: bool | None = None


@dataclass(frozen=True)
class McpRegistryStatus:
    mode: str
    default_server: str
    global_execution_enabled: bool
    servers: list[McpServerStatus]

    @property
    def configured(self) -> bool:
        return any(server.configured for server in self.servers)

    @property
    def available(self) -> bool:
        return any(server.available for server in self.servers)

    @property
    def implemented(self) -> bool:
        return all(server.implemented for server in self.servers)


def load_mcp_registry_status() -> McpRegistryStatus:
    mode = _env("MCP_MODE", "mock").lower()
    default_server = _env("MCP_DEFAULT_SERVER", "splunk_soc")
    global_execution_enabled = _bool_env("MCP_GLOBAL_EXECUTION_ENABLED", False)

    if mode == "mock":
        mock_tools = mock_discovered_tools("splunk")
        mock_execution_enabled = bool(global_execution_enabled and _bool_env("MCP_SERVER_MOCK_EXECUTION_ENABLED", False))
        return McpRegistryStatus(
            mode="mock",
            default_server=default_server,
            global_execution_enabled=global_execution_enabled,
            servers=[
                McpServerStatus(
                    name="mock",
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
                    execution_enabled=mock_execution_enabled,
                    discovered_tools_count=len(mock_tools),
                    discovered_tools_safe_names=[tool.name for tool in mock_tools if not tool.blocked],
                    discovered_tools=[tool.safe_payload() for tool in mock_tools],
                    blocked_tools_count=len([tool for tool in mock_tools if tool.blocked]),
                    blocked_tools_safe_names=[tool.name for tool in mock_tools if tool.blocked],
                    last_error=None,
                    splunk_app_id="7931",
                    splunk_platform="mock",
                    search_execution_allowed=mock_execution_enabled,
                    saia_spl_generation_allowed=False,
                    knowledge_object_discovery_allowed=True,
                    list_tools_allowed=True,
                )
            ],
        )

    names = _csv_env("MCP_SERVERS") or ([default_server] if default_server else [])
    servers = [_status_for_server(_load_server_config(name), global_execution_enabled) for name in names]
    return McpRegistryStatus(
        mode="registry" if mode == "registry" else mode,
        default_server=default_server,
        global_execution_enabled=global_execution_enabled,
        servers=servers,
    )


def _load_server_config(name: str) -> McpServerConfig:
    prefix = f"MCP_SERVER_{_env_key(name)}_"
    return McpServerConfig(
        name=name,
        enabled=_bool_env(prefix + "ENABLED", False),
        server_type=_env(prefix + "TYPE", "generic").lower(),
        transport=_env(prefix + "TRANSPORT", "streamable_http").lower(),
        url=_env(prefix + "URL"),
        command=_env(prefix + "COMMAND"),
        args=_env(prefix + "ARGS"),
        auth_mode=_env(prefix + "AUTH_MODE", "none").lower(),
        bearer_token=_env(prefix + "BEARER_TOKEN"),
        username=_env(prefix + "USERNAME"),
        password=_env(prefix + "PASSWORD"),
        connect_timeout_seconds=_int_env(prefix + "CONNECT_TIMEOUT_SECONDS", 10),
        tool_allowlist=_csv_env(prefix + "TOOL_ALLOWLIST"),
        execution_enabled=_bool_env(prefix + "EXECUTION_ENABLED", False),
        splunk_app_id=_env(prefix + "SPLUNK_APP_ID", "7931"),
        splunk_platform=_env(prefix + "SPLUNK_PLATFORM", "unknown").lower(),
    )


def _status_for_server(config: McpServerConfig, global_execution_enabled: bool) -> McpServerStatus:
    last_error: str | None = None
    implemented = True
    auth_valid = config.auth_mode in SUPPORTED_AUTH_MODES
    transport_valid = config.transport in SUPPORTED_TRANSPORTS
    type_valid = config.server_type in SUPPORTED_MCP_TYPES

    if not type_valid:
        implemented = False
        last_error = "unsupported_mcp_server_type"
    elif not transport_valid:
        implemented = False
        last_error = "unsupported_mcp_transport"
    elif not auth_valid:
        implemented = False
        last_error = "unsupported_mcp_auth_mode"

    endpoint_configured = bool(config.url.strip()) if config.transport in {"streamable_http", "sse"} else bool(config.command.strip())
    auth_configured = _auth_configured(config)
    configured = bool(config.enabled and endpoint_configured and auth_configured and implemented)
    available = configured
    if config.enabled and not endpoint_configured and last_error is None:
        last_error = "missing_endpoint_configuration"
    if config.enabled and endpoint_configured and not auth_configured and last_error is None:
        last_error = "missing_auth_configuration"

    discovered_tools = _discovered_tools_for_config(config)
    safe_tools = [tool.name for tool in discovered_tools if not tool.blocked]
    blocked_tools = [tool.name for tool in discovered_tools if tool.blocked]
    execution_enabled = bool(config.execution_enabled and global_execution_enabled)

    kwargs = {}
    if config.server_type == "splunk":
        kwargs = {
            "splunk_app_id": config.splunk_app_id or "7931",
            "splunk_platform": config.splunk_platform if config.splunk_platform in {"enterprise", "cloud", "unknown"} else "unknown",
            "search_execution_allowed": execution_enabled and any(tool.capability == "spl_search" and not tool.blocked for tool in discovered_tools),
            "saia_spl_generation_allowed": False,
            "knowledge_object_discovery_allowed": True,
            "list_tools_allowed": True,
        }

    return McpServerStatus(
        name=config.name,
        type=config.server_type,
        enabled=config.enabled,
        implemented=implemented,
        configured=configured,
        available=available,
        transport=config.transport,
        url_configured=bool(config.url.strip()),
        command_configured=bool(config.command.strip()),
        auth_mode=config.auth_mode if auth_valid else "unsupported",
        auth_configured=auth_configured,
        execution_enabled=execution_enabled,
        discovered_tools_count=len(discovered_tools),
        discovered_tools_safe_names=safe_tools,
        discovered_tools=[tool.safe_payload() for tool in discovered_tools],
        blocked_tools_count=len(blocked_tools),
        blocked_tools_safe_names=blocked_tools,
        last_error=last_error,
        **kwargs,
    )


def _is_blocked_tool(tool_name: str, server_type: str) -> bool:
    lowered = tool_name.lower()
    return any(token in lowered for token in EXECUTION_TOOL_PATTERNS)


def _discovered_tools_for_config(config: McpServerConfig) -> list[McpToolDescriptor]:
    return [
        classify_mcp_tool(safe_tool_name(tool), server_type=config.server_type)
        for tool in config.tool_allowlist
        if safe_tool_name(tool)
    ]


def _auth_configured(config: McpServerConfig) -> bool:
    if config.auth_mode == "none":
        return True
    if config.auth_mode == "bearer":
        return bool(config.bearer_token.strip())
    if config.auth_mode == "basic":
        return bool(config.username.strip() and config.password.strip())
    return False


def _safe_tool_name(value: str) -> str:
    return safe_tool_name(value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
