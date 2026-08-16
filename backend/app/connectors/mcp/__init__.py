from app.config import settings
from app.connectors.mcp.base import McpConnector
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector


def get_mcp_connector() -> McpConnector:
    mode = settings.mcp_mode.strip().lower()
    if mode == "mock":
        return MockMcpConnector()
    # Registry / explicit live mode never falls back to mock. An unconfigured
    # live connector fails closed (blocked / live_transport_unconfigured) and
    # must not present mock rows as live Splunk evidence.
    if mode in {"registry", "splunk_mcp"}:
        return SplunkMcpConnector()
    return MockMcpConnector()


__all__ = ["McpConnector", "get_mcp_connector"]
