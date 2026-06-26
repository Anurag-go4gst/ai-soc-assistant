from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest
from app.connectors.mcp.discovery import McpToolDescriptor, mock_discovered_tools

_MOCK_DISCOVERY_TOOLS = frozenset(
    {"splunk_get_info", "splunk_get_indexes", "splunk_get_metadata", "splunk_get_knowledge_objects"}
)
_RUN_QUERY_ALIASES = frozenset({"splunk_run_query", "run_splunk_query"})


class MockMcpConnector:
    mode = "mock"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="mock")

    def list_tools(self, server_name: str | None = None) -> list[McpToolDescriptor]:
        return mock_discovered_tools("splunk")

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        governance = arguments.get("_governance") if isinstance(arguments.get("_governance"), dict) else {}
        discovery_allowed = settings.mcp_discovery_enabled or governance.get("discovery_allowed") is True
        if tool_name in _MOCK_DISCOVERY_TOOLS:
            if not discovery_allowed:
                return {"status": "blocked", "error": "mcp_discovery_disabled", "rows": []}
        elif tool_name in _RUN_QUERY_ALIASES:
            if not settings.mcp_global_execution_enabled or not settings.mcp_server_mock_execution_enabled:
                return {"status": "blocked", "error": "mcp_execution_disabled", "rows": []}
        if tool_name == "splunk_get_info":
            return {
                "status": "ok",
                "mock": True,
                "server_name": "splunk-mock",
                "server_version": "9.1.0",
                "rows": [{"server_name": "splunk-mock", "server_version": "9.1.0"}],
            }
        if tool_name == "splunk_get_indexes":
            return {
                "status": "ok",
                "mock": True,
                "indexes": ["pgcil_soc"],
                "rows": [{"index": "pgcil_soc", "title": "pgcil_soc"}],
            }
        if tool_name == "splunk_get_metadata":
            return {
                "status": "ok",
                "mock": True,
                "sourcetypes": ["pgcil:auth", "pgcil:dns", "pgcil:edr", "aws:cloudtrail"],
                "rows": [
                    {"sourcetype": "pgcil:auth"},
                    {"sourcetype": "pgcil:dns"},
                    {"sourcetype": "pgcil:edr"},
                    {"sourcetype": "aws:cloudtrail"},
                ],
            }
        if tool_name == "splunk_get_knowledge_objects":
            return {
                "status": "ok",
                "mock": True,
                "objects": [{"name": "pgcil_auth_summary", "object_type": "savedsearch"}],
            }
        if tool_name not in _RUN_QUERY_ALIASES:
            return {"status": "blocked", "error": "mock_tool_not_allowlisted", "rows": []}
        query = str(arguments.get("search_query") or arguments.get("query") or "")
        return self.execute_validated_spl(
            server_name=server_name or "mock",
            tool_name=tool_name,
            normalized_spl=query,
            trace_id=str(arguments.get("trace_id") or "mock-trace"),
            policy_context={"max_rows": 100},
        )

    def execute_validated_spl(
        self,
        *,
        server_name: str,
        tool_name: str,
        normalized_spl: str,
        trace_id: str,
        policy_context: dict[str, Any],
    ) -> dict[str, Any]:
        max_rows = int(policy_context.get("max_rows", 100))
        rows = _mock_rows(normalized_spl)[: min(max(max_rows, 0), 5)]
        return {
            "status": "ok",
            "mock": True,
            "spl_hash": _stable_hash(normalized_spl),
            "server_name": server_name,
            "tool_name": tool_name,
            "row_count": len(rows),
            "rows": rows,
        }

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {
            "status": "ok",
            "mock": True,
            "objects": [
                {
                    "name": "pgcil_auth_summary",
                    "object_type": request.object_type or "savedsearch",
                    "approved": True,
                }
            ],
        }


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _mock_rows(spl: str) -> list[dict[str, Any]]:
    spl_hash = _stable_hash(spl)
    lowered = spl.lower()
    if " by src" in lowered:
        return [{"src": "10.1.2.55", "fail_count": 327, "spl_hash": spl_hash}]
    if "timechart" in lowered:
        return [{"_time": "2026-05-24T00:00:00Z", "count": 7, "spl_hash": spl_hash}]
    if "success_count" in lowered or 'action="success"' in lowered or "action=success" in lowered:
        return [
            {
                "user": "svc_grid_ops",
                "host": "APP-01",
                "src": "10.10.4.21",
                "fail_count": 58,
                "success_count": 1,
                "first_failure": "2026-05-24T13:42:10Z",
                "last_event": "2026-05-24T14:37:22Z",
                "risk": "P1 validation - successful login after repeated failures",
                "spl_hash": spl_hash,
            }
        ]
    return [{"user": "svc_app", "fail_count": 184, "spl_hash": spl_hash}]
