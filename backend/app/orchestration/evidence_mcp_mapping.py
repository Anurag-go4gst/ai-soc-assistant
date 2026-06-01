from __future__ import annotations

from typing import Any

from app.connectors.mcp.discovery import safe_tool_name

SPLUNK_METADATA_DISCOVERY = "splunk_metadata_discovery"
SPLUNK_AUTH_EVIDENCE = "splunk_auth_evidence"
LOCAL_LOOKUP_REGISTRY = "local_lookup_registry"
DETECTION_REGISTRY_BINDING = "detection_registry_binding"
SAIA_GENERATE_SPL = "saia_generate_spl"

_METADATA_DISCOVERY_TOOLS = ("splunk_get_indexes", "splunk_get_metadata")
_AUTH_EVIDENCE_GATED_TOOLS = ("splunk_run_query",)
_SAIA_CANDIDATE_TOOLS = (SAIA_GENERATE_SPL,)
_SAVED_SEARCH_TOOLS = {"splunk_run_saved_search"}
_KNOWN_TOOLS = {
    "splunk_get_indexes",
    "splunk_get_metadata",
    "splunk_run_query",
    "splunk_run_saved_search",
    "saia_generate_spl",
}


def map_evidence_need_to_mcp_tools(
    *,
    evidence_need: str,
    discovered_tools: list[str | dict[str, Any]] | None = None,
    llm_suggested_tool_names: list[str] | None = None,
    allow_saved_searches: bool = False,
) -> dict[str, Any]:
    """Map governed evidence needs to deterministic MCP tool references.

    LLM suggestions are recorded as ignored advisory input and never populate
    selected, gated, or candidate tool outputs.
    """

    warnings: list[str] = []
    available_tools = _available_tool_names(discovered_tools, warnings)
    for tool_name in _safe_tool_names(llm_suggested_tool_names or []):
        warnings.append(f"llm_tool_suggestion_ignored:{tool_name}")
        if tool_name not in _KNOWN_TOOLS:
            warnings.append(f"unknown_tool_ignored:{tool_name}")
        if tool_name in _SAVED_SEARCH_TOOLS and not allow_saved_searches:
            warnings.append(f"saved_search_blocked_by_default:{tool_name}")

    need = safe_tool_name(evidence_need)
    selected_mcp_tools: list[str] = []
    gated_after_validation_tools: list[str] = []
    candidate_only_tools: list[str] = []
    validator_path: list[str] = []
    requires_spl_validation = False
    candidate_only = False

    if need == SPLUNK_METADATA_DISCOVERY:
        selected_mcp_tools = _allowed_tools(
            _METADATA_DISCOVERY_TOOLS,
            available_tools=available_tools,
            warnings=warnings,
            allow_saved_searches=allow_saved_searches,
        )
    elif need == SPLUNK_AUTH_EVIDENCE:
        validator_path = ["splunk_auth_evidence_template", "spl_validator"]
        requires_spl_validation = True
        gated_after_validation_tools = _allowed_tools(
            _AUTH_EVIDENCE_GATED_TOOLS,
            available_tools=available_tools,
            warnings=warnings,
            allow_saved_searches=allow_saved_searches,
        )
    elif need == SAIA_GENERATE_SPL:
        requires_spl_validation = True
        candidate_only = True
        candidate_only_tools = _allowed_tools(
            _SAIA_CANDIDATE_TOOLS,
            available_tools=available_tools,
            warnings=warnings,
            allow_saved_searches=allow_saved_searches,
        )
    elif need == LOCAL_LOOKUP_REGISTRY:
        warnings.append("local_lookup_registry_is_not_mcp_execution")
    elif need == DETECTION_REGISTRY_BINDING:
        warnings.append("detection_registry_binding_is_not_mcp_execution")
    else:
        warnings.append(f"unknown_evidence_need_ignored:{need}")

    return {
        "evidence_need": need,
        "selected_mcp_tools": selected_mcp_tools,
        "gated_after_validation_tools": gated_after_validation_tools,
        "candidate_only_tools": candidate_only_tools,
        "validator_path": validator_path,
        "requires_spl_validation": requires_spl_validation,
        "candidate_only": candidate_only,
        "warnings": warnings,
    }


def _available_tool_names(tools: list[str | dict[str, Any]] | None, warnings: list[str]) -> set[str] | None:
    if tools is None:
        return None

    safe_names: set[str] = set()
    for item in tools:
        raw_name = item.get("name") if isinstance(item, dict) else item
        if not raw_name:
            continue
        name = safe_tool_name(str(raw_name))
        if name not in _KNOWN_TOOLS:
            warnings.append(f"unknown_tool_ignored:{name}")
            continue
        safe_names.add(name)
    return safe_names


def _safe_tool_names(tool_names: list[str]) -> list[str]:
    return [safe_tool_name(str(tool_name)) for tool_name in tool_names if str(tool_name).strip()]


def _allowed_tools(
    tool_names: tuple[str, ...],
    *,
    available_tools: set[str] | None,
    warnings: list[str],
    allow_saved_searches: bool,
) -> list[str]:
    allowed: list[str] = []
    for tool_name in tool_names:
        if tool_name not in _KNOWN_TOOLS:
            warnings.append(f"unknown_tool_ignored:{tool_name}")
            continue
        if tool_name in _SAVED_SEARCH_TOOLS and not allow_saved_searches:
            warnings.append(f"saved_search_blocked_by_default:{tool_name}")
            continue
        if available_tools is not None and tool_name not in available_tools:
            warnings.append(f"mapped_tool_unavailable:{tool_name}")
            continue
        allowed.append(tool_name)
    return allowed
