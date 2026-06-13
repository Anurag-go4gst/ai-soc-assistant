"""Read-only MCP discovery for source-profile slot fill (splunk_get_indexes / metadata).

Governance: discovery tools only — not splunk_run_query. Runs whenever the MCP
connector is available (mock or registry); does not require search execution flags.
"""
from __future__ import annotations

from typing import Any

from app.connectors.mcp import get_mcp_connector
from app.safeguards.spl_validator import load_spl_policy
from app.spl.source_profile_resolver import _INDEX_STEMS, _SOURCETYPE_RULES, _pick_sourcetype, _stem_matches_index

DISCOVERY_TOOL_NAMES = ("splunk_get_indexes", "splunk_get_metadata")


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
) -> tuple[dict[str, str], dict[str, Any]]:
    connector = get_mcp_connector()
    trace: dict[str, Any] = {"tools_called": [], "errors": []}
    indexes: list[str] = []
    sourcetypes: list[str] = []

    for tool_name in DISCOVERY_TOOL_NAMES:
        try:
            result = connector.call_tool(tool_name, {}, server_name=server_name)
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
    return profile, trace
