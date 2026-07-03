from __future__ import annotations

from app.connectors.mcp.mcp_endpoint import normalize_mcp_endpoint_url


def test_normalize_mcp_endpoint_url_appends_mcp() -> None:
    assert normalize_mcp_endpoint_url("https://splunk.example.com") == "https://splunk.example.com/mcp"


def test_normalize_mcp_endpoint_url_idempotent() -> None:
    assert normalize_mcp_endpoint_url("https://splunk.example.com/mcp") == "https://splunk.example.com/mcp"
