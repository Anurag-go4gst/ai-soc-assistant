from app.config import settings
from app.connectors.mcp.base import McpConnector
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector


def get_mcp_connector() -> McpConnector:
    mode = settings.mcp_mode.strip().lower()
    if mode == "splunk_mcp":
        return SplunkMcpConnector()
    return MockMcpConnector()


__all__ = ["McpConnector", "get_mcp_connector"]
