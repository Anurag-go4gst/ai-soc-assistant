from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus, load_mcp_registry_status

RUN_QUERY_ALIASES = {"splunk_run_query", "run_splunk_query"}
TOOL_ALIASES = {
    "splunk_run_query": RUN_QUERY_ALIASES,
    "splunk_get_metadata": {"splunk_get_metadata", "get_splunk_metadata"},
}
EXPECTED_CORE_TOOLS = [
    "splunk_run_query",
    "splunk_get_info",
    "splunk_get_indexes",
    "splunk_get_index_info",
    "splunk_get_metadata",
    "splunk_get_user_info",
    "splunk_get_knowledge_objects",
]
EXPECTED_SAIA_TOOLS = ["saia_generate_spl", "saia_explain_spl", "saia_optimize_spl", "saia_ask_splunk_question"]


@dataclass(frozen=True)
class SplunkCapabilityProfile:
    server_id: str
    environment_mode: str
    mcp_available: bool
    discovery_mode: str
    core_splunk_tools_available: bool
    saia_available: bool
    saia_configured_mode: str
    saia_usable: bool
    fallback_required: bool
    available_tools: list[str]
    available_core_tools: list[str]
    available_saia_tools: list[str]
    missing_expected_core_tools: list[str]
    missing_expected_saia_tools: list[str]
    run_query_available: bool
    get_info_available: bool
    get_indexes_available: bool
    get_index_info_available: bool
    get_metadata_available: bool
    get_user_info_available: bool
    get_knowledge_objects_available: bool
    run_saved_search_available: bool
    saia_generate_spl_available: bool
    saia_explain_spl_available: bool
    saia_optimize_spl_available: bool
    saia_ask_splunk_question_available: bool
    metadata_discovery_allowed: bool
    knowledge_object_discovery_allowed: bool
    run_saved_search_allowed: bool
    run_saved_search_requires_hil: bool
    run_query_requires_validation: bool
    authenticated_user_available: bool = False
    discovered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_splunk_capability_profile(
    registry: McpRegistryStatus | None = None,
    *,
    server_id: str | None = None,
    required_saia_tool: str | None = None,
) -> SplunkCapabilityProfile:
    registry = registry or load_mcp_registry_status()
    server_id = server_id or settings.splunk_mcp_server_id or registry.default_server
    server = _find_server(registry, server_id)
    tools = _tool_names(server)
    canonical = {_canonical_tool(tool) for tool in tools}
    available_core = [tool for tool in EXPECTED_CORE_TOOLS if _has_tool(tool, tools)]
    available_saia = [tool for tool in EXPECTED_SAIA_TOOLS if tool in tools]
    saia_mode = _effective_saia_mode()
    saia_available = any(tool.startswith("saia_") for tool in tools)
    saia_usable = bool(saia_available and settings.splunk_saia_tools_enabled and saia_mode != "disabled")
    if settings.splunk_saia_require_discovery and required_saia_tool:
        saia_usable = saia_usable and required_saia_tool in tools
    run_query_available = _has_tool("splunk_run_query", tools) and _allowed_core("splunk_run_query")
    discovery_tool_available = any(_has_tool(tool, tools) for tool in ("splunk_get_indexes", "splunk_get_metadata", "splunk_get_info", "splunk_get_knowledge_objects"))
    missing_saia = [tool for tool in EXPECTED_SAIA_TOOLS if tool not in tools]
    fallback_required = not saia_usable or bool(required_saia_tool and required_saia_tool not in tools)
    warnings: list[str] = []
    if settings.ai_soc_environment_mode == "air_gapped" and settings.splunk_ai_assistant_mode == "auto":
        warnings.append("air_gapped_defaults_to_saia_disabled")
    if not saia_usable:
        warnings.append("splunk_ai_assistant_unavailable_fallback_required")
    return SplunkCapabilityProfile(
        server_id=server_id,
        environment_mode=settings.ai_soc_environment_mode,
        mcp_available=bool(server and server.available and settings.splunk_mcp_enabled),
        discovery_mode=settings.splunk_mcp_discovery_mode,
        core_splunk_tools_available=bool(run_query_available and discovery_tool_available),
        saia_available=saia_available,
        saia_configured_mode=settings.splunk_ai_assistant_mode,
        saia_usable=saia_usable,
        fallback_required=fallback_required,
        available_tools=sorted(canonical),
        available_core_tools=available_core,
        available_saia_tools=available_saia,
        missing_expected_core_tools=[tool for tool in EXPECTED_CORE_TOOLS if not _has_tool(tool, tools)],
        missing_expected_saia_tools=missing_saia,
        run_query_available=run_query_available,
        get_info_available=_has_tool("splunk_get_info", tools),
        get_indexes_available=_has_tool("splunk_get_indexes", tools),
        get_index_info_available=_has_tool("splunk_get_index_info", tools),
        get_metadata_available=_has_tool("splunk_get_metadata", tools),
        get_user_info_available=_has_tool("splunk_get_user_info", tools),
        get_knowledge_objects_available=_has_tool("splunk_get_knowledge_objects", tools),
        run_saved_search_available=_has_tool("splunk_run_saved_search", tools),
        saia_generate_spl_available="saia_generate_spl" in tools,
        saia_explain_spl_available="saia_explain_spl" in tools,
        saia_optimize_spl_available="saia_optimize_spl" in tools,
        saia_ask_splunk_question_available="saia_ask_splunk_question" in tools,
        metadata_discovery_allowed=settings.splunk_metadata_discovery_allowed,
        knowledge_object_discovery_allowed=settings.splunk_knowledge_object_discovery_allowed,
        run_saved_search_allowed=settings.splunk_allow_run_saved_search,
        run_saved_search_requires_hil=settings.splunk_run_saved_search_require_hil,
        run_query_requires_validation=settings.splunk_run_query_require_validation,
        authenticated_user_available=_has_tool("splunk_get_user_info", tools) and bool(server and server.auth_configured),
        warnings=warnings,
    )


def _find_server(registry: McpRegistryStatus, server_id: str) -> McpServerStatus | None:
    return next((server for server in registry.servers if server.name == server_id), None) or next((server for server in registry.servers if server.type == "splunk"), None)


def _tool_names(server: McpServerStatus | None) -> set[str]:
    if not server:
        return set()
    names = {str(tool.get("name")) for tool in server.discovered_tools if not tool.get("blocked")}
    names.update(str(name) for name in server.discovered_tools_safe_names)
    return {name for name in names if name}


def _has_tool(canonical_name: str, tools: set[str]) -> bool:
    return bool((TOOL_ALIASES.get(canonical_name) or {canonical_name}).intersection(tools))


def _canonical_tool(tool: str) -> str:
    if tool in RUN_QUERY_ALIASES:
        return "splunk_run_query"
    if tool == "get_splunk_metadata":
        return "splunk_get_metadata"
    return tool


def _allowed_core(tool: str) -> bool:
    allowed = {item.strip() for item in settings.splunk_allowed_core_tools.split(",") if item.strip()}
    return tool in allowed or bool((TOOL_ALIASES.get(tool) or set()).intersection(allowed))


def _effective_saia_mode() -> str:
    if settings.ai_soc_environment_mode == "air_gapped" and settings.splunk_ai_assistant_mode == "auto":
        return "disabled"
    return settings.splunk_ai_assistant_mode
