from app.config import settings
from app.connectors.mcp.base import McpConnector
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector


def get_mcp_connector() -> McpConnector:
    mode = settings.mcp_mode.strip().lower()
    if mode == "splunk_mcp":
        return SplunkMcpConnector()
    # Live registry mode routes to the real Splunk connector only when a Splunk
    # MCP endpoint is configured; otherwise registry stays mock (readiness).
    if mode == "registry" and settings.splunk_mcp_enabled and settings.splunk_mcp_base_url.strip():
        return SplunkMcpConnector()
    return MockMcpConnector()


__all__ = ["McpConnector", "get_mcp_connector"]
