"""P3: read-only live Splunk MCP readiness gate."""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.registry import McpRegistryStatus, load_mcp_registry_status

_SAFE_SEARCH_TOOLS = {"splunk_run_query", "run_splunk_query"}
_SAFE_METADATA_TOOLS = {"splunk_get_indexes", "splunk_get_metadata", "get_splunk_metadata"}


def evaluate_splunk_mcp_live_readiness(
    *,
    registry: McpRegistryStatus | None = None,
    coe_contract_approved: bool = False,
) -> dict[str, Any]:
    """Return a non-secret readiness report for real Splunk MCP execution.

    This function never calls MCP. It only inspects registry/discovery state and
    documents which explicit gates still block live execution.
    """
    status = registry or load_mcp_registry_status()
    server = _select_splunk_server(status)
    blockers: list[str] = []
    warnings: list[str] = []

    if status.mode != "registry":
        blockers.append("mcp_mode_must_be_registry")
    if not status.global_execution_enabled:
        blockers.append("mcp_global_execution_enabled_required")
    if not coe_contract_approved:
        blockers.append("coe_contract_approval_required")

    safe_tools: set[str] = set()
    if server is None:
        blockers.append("splunk_mcp_server_required")
    else:
        safe_tools = set(server.discovered_tools_safe_names)
        if not server.enabled:
            blockers.append("splunk_mcp_server_enabled_required")
        if not server.implemented:
            blockers.append("splunk_mcp_server_type_or_transport_unsupported")
        if not server.configured:
            blockers.append(server.last_error or "splunk_mcp_server_configuration_incomplete")
        if not server.available:
            blockers.append(server.last_error or "splunk_mcp_server_unavailable")
        if not server.auth_configured:
            blockers.append("splunk_mcp_auth_required")
        if not server.execution_enabled:
            blockers.append("splunk_mcp_server_execution_enabled_required")
        if not _SAFE_SEARCH_TOOLS.intersection(safe_tools):
            blockers.append("safe_splunk_search_tool_required")
        if not _SAFE_METADATA_TOOLS.intersection(safe_tools):
            blockers.append("safe_splunk_metadata_tool_required")
        if server.blocked_tools_safe_names:
            warnings.append("blocked_tools_present_and_must_remain_blocked")

    unique_blockers = sorted(set(blockers))
    return {
        "schema_version": "p3_splunk_mcp_live_readiness_v1",
        "ready_for_live_splunk_mcp": not unique_blockers,
        "authority": "readiness_report_only",
        "mcp_called": False,
        "execution_authorized": False,
        "coe_contract_approved": coe_contract_approved,
        "mode": status.mode,
        "global_execution_enabled": status.global_execution_enabled,
        "server": _server_payload(server),
        "required_safe_tool_families": {
            "search": sorted(_SAFE_SEARCH_TOOLS),
            "metadata": sorted(_SAFE_METADATA_TOOLS),
        },
        "safe_tools_observed": sorted(safe_tools),
        "blockers": unique_blockers,
        "warnings": sorted(set(warnings)),
        "go_live_steps": _go_live_steps(),
    }


def _select_splunk_server(status: McpRegistryStatus) -> Any | None:
    for server in status.servers:
        if server.name == status.default_server and server.type == "splunk":
            return server
    for server in status.servers:
        if server.type == "splunk":
            return server
    return None


def _server_payload(server: Any | None) -> dict[str, Any] | None:
    if server is None:
        return None
    return {
        "name": server.name,
        "type": server.type,
        "enabled": server.enabled,
        "implemented": server.implemented,
        "configured": server.configured,
        "available": server.available,
        "transport": server.transport,
        "auth_mode": server.auth_mode,
        "auth_configured": server.auth_configured,
        "execution_enabled": server.execution_enabled,
        "search_execution_allowed": server.search_execution_allowed,
        "last_error": server.last_error,
    }


def _go_live_steps() -> list[str]:
    return [
        "COE provides and approves MCP endpoint, transport, auth owner, safe tool names, argument schema, result schema, policy, telemetry, and rollback owner.",
        "Configure MCP_MODE=registry, MCP_SERVERS=splunk_soc, MCP_DEFAULT_SERVER=splunk_soc.",
        "Configure MCP_SERVER_SPLUNK_SOC_ENABLED=true, TYPE=splunk, TRANSPORT, URL or COMMAND, AUTH_MODE, and non-committed credentials.",
        "Allowlist only safe read tools: metadata tools plus validator-approved search tool.",
        "Validate /settings/mcp/validate, /settings/mcp/test, and /settings/mcp/discover without persisting secrets.",
        "Run P3 readiness report and confirm ready_for_live_splunk_mcp=true.",
        "Enable MCP_GLOBAL_EXECUTION_ENABLED=true and MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED=true only in the approved environment.",
        "Run canonical governance regression plus a bounded mock/live read smoke test with HIL/rollback owner present.",
    ]
