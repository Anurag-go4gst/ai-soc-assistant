"""Pre-execution Splunk server alignment via native MCP discovery tools.

Before a catalogue template that targets a concrete index (e.g. ``scada_perf`` /
``cisco_asa``) or a Wave-3 lookup CSV is executed with ``splunk_run_query``, the
backend confirms those dependencies actually exist on the live search head using
lightweight discovery tools — never a heavy search:

  * ``splunk_get_indexes``            -> index existence
  * ``splunk_get_knowledge_objects``  (type="lookups") -> lookup CSV existence

Mapped (all present)  -> caller proceeds to execution.
Unmapped / unreachable -> caller drops back to token-SPL + COE-HIL so the analyst
                          binds alternatives. Verification is read-only and
                          best-effort; any error fails closed to "not verified".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.connectors.mcp import get_mcp_connector
from app.spl.mcp_source_discovery import _indexes_from_result, discovery_execution_allowed

_LOOKUP_RE = re.compile(r"\blookup\s+([A-Za-z0-9_.-]+\.csv)\b", re.IGNORECASE)


@dataclass
class DependencyVerification:
    verified: bool = False
    checked: bool = False  # False = discovery unavailable / could not confirm
    missing_indexes: list[str] = field(default_factory=list)
    missing_lookups: list[str] = field(default_factory=list)
    reason: str | None = None
    tools_called: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)


def required_lookups_for_template(spl_text: str) -> list[str]:
    """Lookup CSVs a template depends on at runtime — those referenced in its SPL."""
    return sorted({m for m in _LOOKUP_RE.findall(spl_text or "")})


def _lookup_names_from_result(result: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("lookups", "knowledge_objects", "objects", "rows"):
        raw = result.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    for field_name in ("name", "title", "filename", "lookup"):
                        value = item.get(field_name)
                        if value:
                            names.append(str(value))
    return [n.lower() for n in names]


def verify_template_dependencies(
    *,
    required_indexes: list[str],
    required_lookups: list[str],
    server_name: str | None = None,
    discovery_allowed: bool | None = None,
) -> DependencyVerification:
    """Confirm indexes + lookup CSVs exist live via read-only MCP discovery tools."""
    if not (required_indexes or required_lookups):
        return DependencyVerification(verified=True, checked=True, reason="no_dependencies")
    if not discovery_execution_allowed(discovery_allowed=discovery_allowed):
        return DependencyVerification(checked=False, reason="mcp_discovery_unavailable")

    connector = get_mcp_connector()
    result = DependencyVerification(checked=True)
    tool_args: dict[str, Any] = {}
    if discovery_allowed is True:
        tool_args["_governance"] = {"discovery_allowed": True}

    # 1) Index existence.
    if required_indexes:
        try:
            idx_result = connector.call_tool("splunk_get_indexes", dict(tool_args), server_name=server_name)
            result.tools_called.append("splunk_get_indexes")
            if not isinstance(idx_result, dict) or idx_result.get("status") == "blocked":
                return DependencyVerification(
                    checked=False, reason="splunk_get_indexes_blocked", tools_called=result.tools_called
                )
            live = {x.lower() for x in _indexes_from_result(idx_result)}
            result.missing_indexes = [i for i in required_indexes if i.lower() not in live]
        except Exception:  # noqa: BLE001 - verification is best-effort, fail closed
            return DependencyVerification(
                checked=False, reason="splunk_get_indexes_error", tools_called=result.tools_called
            )

    # 2) Lookup CSV existence.
    if required_lookups:
        try:
            ko_args = {**tool_args, "type": "lookups"}
            ko_result = connector.call_tool("splunk_get_knowledge_objects", ko_args, server_name=server_name)
            result.tools_called.append("splunk_get_knowledge_objects")
            if not isinstance(ko_result, dict) or ko_result.get("status") == "blocked":
                return DependencyVerification(
                    checked=False, reason="splunk_get_knowledge_objects_blocked", tools_called=result.tools_called
                )
            live_lookups = set(_lookup_names_from_result(ko_result))
            result.missing_lookups = [lk for lk in required_lookups if lk.lower() not in live_lookups]
        except Exception:  # noqa: BLE001 - best-effort, fail closed
            return DependencyVerification(
                checked=False, reason="splunk_get_knowledge_objects_error", tools_called=result.tools_called
            )

    result.verified = not result.missing_indexes and not result.missing_lookups
    if not result.verified:
        result.reason = "missing_dependencies"
    result.trace = {
        "missing_indexes": result.missing_indexes,
        "missing_lookups": result.missing_lookups,
        "tools_called": result.tools_called,
    }
    return result
