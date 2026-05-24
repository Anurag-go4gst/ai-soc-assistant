from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest
from app.connectors.mcp.discovery import McpToolDescriptor


class SplunkMcpConnector:
    mode = "splunk_mcp"

    def health(self) -> ConnectorStatus:
        configured = bool(settings.splunk_mcp_enabled and settings.splunk_mcp_base_url.strip())
        return ConnectorStatus(
            mode=self.mode,
            configured=configured,
            available=False,
            detail="placeholder_not_implemented",
            implemented=False,
            fallback="mock",
        )

    def list_tools(self, server_name: str | None = None) -> list[McpToolDescriptor]:
        return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("Splunk MCP call_tool adapter is not implemented yet.")

    def execute_validated_spl(
        self,
        *,
        server_name: str,
        tool_name: str,
        normalized_spl: str,
        trace_id: str,
        policy_context: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Splunk MCP execution connector is not implemented yet.")

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {"status": "not_implemented", "objects": []}
