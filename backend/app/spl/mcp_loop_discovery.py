"""Read-only MCP discovery hop for the Stage 4B evidence loop.

Governance: discovery tools only — never ``splunk_run_query``. Requires
``MCP_DISCOVERY_ENABLED`` and RBAC allowlisting. Results are sanitized before
they accumulate in ``mcp_evidence`` / ``source_evidence``.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.mcp_rbac import canonical_mcp_tool_name, is_tool_allowed_for_role
from app.connectors.mcp.mcp_tool_chronology import load_playbook
from app.connectors.telemetry.redaction import mask_secret_substrings
from app.spl.mcp_source_discovery import discovery_execution_allowed

_PREVIEW_ROW_CAP = 5


def execute_loop_discovery_hop(
    tool: str,
    *,
    rbac_role: str | None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Run one governed read-only discovery hop for the evidence loop.

    Returns a dict suitable for ``record_hop`` payload assembly:
    ``outcome``, ``delivered``, ``payload``.
    """
    canonical = canonical_mcp_tool_name(tool)
    if canonical == "splunk_run_query":
        return {
            "outcome": "blocked",
            "delivered": [],
            "payload": {"error": "run_query_not_allowed_in_discovery_hop"},
        }

    declared = _declared_produces(canonical)
    if not discovery_execution_allowed():
        return {
            "outcome": "planned",
            "delivered": declared,
            "payload": {"read_only": True, "reason": "mcp_discovery_disabled"},
        }

    if rbac_role is not None and not is_tool_allowed_for_role(canonical, rbac_role):
        return {
            "outcome": "blocked",
            "delivered": [],
            "payload": {"error": "rbac_denied", "rbac_role": rbac_role},
        }

    connector = get_mcp_connector()
    arguments: dict[str, Any] = {"trace_id": trace_id} if trace_id else {}
    try:
        result = connector.call_tool(canonical, arguments)
    except Exception as exc:  # pragma: no cover - connector-specific
        return {
            "outcome": "failed",
            "delivered": [],
            "payload": {"error": str(exc)[:240]},
        }

    if not isinstance(result, dict):
        return {"outcome": "failed", "delivered": [], "payload": {"error": "invalid_connector_result"}}

    status = str(result.get("status") or "unknown")
    if status == "blocked":
        return {
            "outcome": "blocked",
            "delivered": [],
            "payload": {"error": str(result.get("error") or "blocked"), "read_only": True},
        }
    if status != "ok":
        return {
            "outcome": "failed",
            "delivered": [],
            "payload": {"status": status, "error": str(result.get("error") or status)},
        }

    delivered = _delivered_produces_from_result(canonical, result, declared)
    preview_rows = _sanitize_preview_rows(result.get("rows"))
    return {
        "outcome": "collected",
        "delivered": delivered,
        "payload": {
            "read_only": True,
            "status": status,
            "preview_rows": preview_rows,
            "result_summary": _result_summary(canonical, result),
        },
    }


def _declared_produces(tool: str) -> list[str]:
    tools = load_playbook().get("tools") or {}
    spec = tools.get(tool) or {}
    return [str(item) for item in (spec.get("produces") or [])]


def _delivered_produces_from_result(tool: str, result: dict[str, Any], declared: list[str]) -> list[str]:
    """Map connector rows to playbook ``produces`` keys when the hop succeeded."""
    if not declared:
        return []
    delivered: list[str] = []
    if tool == "splunk_get_indexes" and (_indexes_from_result(result) or result.get("indexes")):
        if "accessible_indexes" in declared:
            delivered.append("accessible_indexes")
    if tool == "splunk_get_metadata" and (_sourcetypes_from_result(result) or result.get("sourcetypes")):
        for key in ("sourcetypes", "hosts", "sources"):
            if key in declared:
                delivered.append(key)
    if tool == "splunk_get_info" and result.get("status") == "ok":
        for key in ("server_version", "server_name", "readiness"):
            if key in declared:
                delivered.append(key)
    if tool == "splunk_get_knowledge_objects" and result.get("objects"):
        for key in ("saved_searches", "macros", "data_models", "eventtypes"):
            if key in declared:
                delivered.append(key)
    if tool == "splunk_get_index_info" and result.get("status") == "ok" and "index_detail" in declared:
        delivered.append("index_detail")
    if not delivered and result.get("status") == "ok":
        return list(declared)
    return list(dict.fromkeys(delivered))


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


def _sanitize_preview_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for row in rows[:_PREVIEW_ROW_CAP]:
        if not isinstance(row, dict):
            continue
        cleaned: dict[str, Any] = {}
        for key, value in row.items():
            text = mask_secret_substrings(str(value)) if value is not None else value
            cleaned[str(key)] = text
        sanitized.append(cleaned)
    return sanitized


def _result_summary(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"tool": tool, "mock": bool(result.get("mock"))}
    if tool == "splunk_get_indexes":
        summary["index_count"] = len(_indexes_from_result(result))
    if tool == "splunk_get_metadata":
        summary["sourcetype_count"] = len(_sourcetypes_from_result(result))
    return summary
