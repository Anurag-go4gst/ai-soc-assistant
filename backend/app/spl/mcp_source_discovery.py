"""Read-only MCP discovery for source-profile slot fill (splunk_get_indexes / metadata).

Governance: discovery tools only — not splunk_run_query. Requires
``MCP_DISCOVERY_ENABLED=true`` (or explicit ``discovery_allowed=True`` from
Settings discover-from-mcp). Does not use search execution flags.
"""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp import get_mcp_connector
from app.safeguards.spl_validator import load_spl_policy
from app.spl.source_profile_resolver import _INDEX_STEMS, _SOURCETYPE_RULES, _pick_sourcetype, _stem_matches_index
from app.spl.saved_search_preference import saved_searches_from_knowledge_result

DISCOVERY_TOOL_NAMES = ("splunk_get_indexes", "splunk_get_metadata")
KNOWLEDGE_OBJECT_TOOL = "splunk_get_knowledge_objects"


def discovery_execution_allowed(*, discovery_allowed: bool | None = None) -> bool:
    if discovery_allowed is not None:
        return discovery_allowed
    return settings.mcp_discovery_enabled


def _indexes_from_result(result: dict[str, Any]) -> list[str]:
    indexes: list[str] = []
    for key in ("indexes", "index_list"):
        raw = result.get(key)
        if isinstance(raw, list):
            indexes.extend(str(item) for item in raw if item)
    rows = result.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                for field in ("index", "name", "title"):
                    value = row.get(field)
                    if value:
                        indexes.append(str(value))
    return list(dict.fromkeys(indexes))


def _sourcetypes_from_result(result: dict[str, Any]) -> list[str]:
    sourcetypes: list[str] = []
    for key in ("sourcetypes", "sourcetype_list"):
        raw = result.get(key)
        if isinstance(raw, list):
            sourcetypes.extend(str(item) for item in raw if item)
    rows = result.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                for field in ("sourcetype", "name"):
                    value = row.get(field)
                    if value:
                        sourcetypes.append(str(value))
    return list(dict.fromkeys(sourcetypes))


def map_discovery_to_profile(
    *,
    indexes: list[str],
    sourcetypes: list[str],
    required_slots: list[str] | None = None,
) -> dict[str, str]:
    profile: dict[str, str] = {}
    policy = load_spl_policy()
    allowed_indexes = set(policy.allowed_indexes)
    allowed_sourcetypes = set(policy.allowed_sourcetypes)

    filtered_indexes = [idx for idx in indexes if not allowed_indexes or idx in allowed_indexes] or indexes
    filtered_sourcetypes = [
        st for st in sourcetypes if not allowed_sourcetypes or st in allowed_sourcetypes
    ] or sourcetypes

    if len(filtered_indexes) == 1:
        for stem in _INDEX_STEMS:
            profile[stem] = filtered_indexes[0]
    else:
        for stem in _INDEX_STEMS:
            for index_name in filtered_indexes:
                if _stem_matches_index(stem, index_name):
                    profile[stem] = index_name
                    break

    for stem, keywords in _SOURCETYPE_RULES:
        picked = _pick_sourcetype(filtered_sourcetypes, keywords)
        if picked:
            profile.setdefault(stem, picked)

    if required_slots:
        return {slot: profile[slot] for slot in required_slots if slot in profile}
    return profile


def run_mcp_source_discovery(
    *,
    required_slots: list[str] | None = None,
    server_name: str | None = None,
    discovery_allowed: bool | None = None,
    include_knowledge_objects: bool = False,
) -> tuple[dict[str, str], dict[str, Any]]:
    if not discovery_execution_allowed(discovery_allowed=discovery_allowed):
        return {}, {"tools_called": [], "errors": ["mcp_discovery_disabled"], "skipped": True}

    connector = get_mcp_connector()
    trace: dict[str, Any] = {"tools_called": [], "errors": []}
    indexes: list[str] = []
    sourcetypes: list[str] = []
    tool_arguments: dict[str, Any] = {}
    if discovery_allowed is True:
        tool_arguments["_governance"] = {"discovery_allowed": True}

    for tool_name in DISCOVERY_TOOL_NAMES:
        try:
            result = connector.call_tool(tool_name, tool_arguments, server_name=server_name)
            trace["tools_called"].append(tool_name)
            if not isinstance(result, dict):
                continue
            if result.get("status") == "blocked":
                trace["errors"].append(f"{tool_name}:{result.get('error')}")
                continue
            indexes.extend(_indexes_from_result(result))
            sourcetypes.extend(_sourcetypes_from_result(result))
            trace[tool_name] = {
                "status": result.get("status", "ok"),
                "index_count": len(_indexes_from_result(result)),
                "sourcetype_count": len(_sourcetypes_from_result(result)),
            }
        except Exception as exc:  # pragma: no cover - connector-specific
            trace["errors"].append(f"{tool_name}:{exc}")

    profile = map_discovery_to_profile(
        indexes=list(dict.fromkeys(indexes)),
        sourcetypes=list(dict.fromkeys(sourcetypes)),
        required_slots=required_slots,
    )
    trace["mapped_slots"] = list(profile.keys())
    if include_knowledge_objects:
        try:
            ko_result = connector.call_tool(KNOWLEDGE_OBJECT_TOOL, tool_arguments, server_name=server_name)
            trace["tools_called"].append(KNOWLEDGE_OBJECT_TOOL)
            if isinstance(ko_result, dict):
                harvested = saved_searches_from_knowledge_result(ko_result)
                trace["saved_searches"] = [item.to_dict() for item in harvested]
                trace[KNOWLEDGE_OBJECT_TOOL] = {
                    "status": ko_result.get("status", "ok"),
                    "saved_search_count": len(harvested),
                }
                if ko_result.get("status") == "blocked":
                    trace["errors"].append(f"{KNOWLEDGE_OBJECT_TOOL}:{ko_result.get('error')}")
        except Exception as exc:  # pragma: no cover - connector-specific
            trace["errors"].append(f"{KNOWLEDGE_OBJECT_TOOL}:{exc}")
    return profile, trace
