from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest, ValidatedSplRequest


class SplunkMcpConnector:
    mode = "splunk_mcp"

    def health(self) -> ConnectorStatus:
        configured = bool(settings.splunk_mcp_enabled and settings.splunk_mcp_base_url.strip())
        return ConnectorStatus(
            mode=self.mode,
            configured=configured,
            available=False,
            detail="placeholder_not_implemented",
        )

    def execute_validated_spl(self, request: ValidatedSplRequest) -> dict[str, Any]:
        raise NotImplementedError("Splunk MCP execution connector is not implemented yet.")

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {"status": "not_implemented", "objects": []}
