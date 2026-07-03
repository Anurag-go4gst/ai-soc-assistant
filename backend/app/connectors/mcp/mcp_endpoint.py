"""Normalize Splunk MCP streamable HTTP endpoint URLs."""

from __future__ import annotations


def normalize_mcp_endpoint_url(url: str) -> str:
    """Return the JSON-RPC MCP endpoint URL without duplicating ``/mcp``.

    Settings verification and live search transport must use the same normalized
    URL. Paste the exact value from the Splunk MCP Server app (often already
    ending in ``/mcp``).
    """
    cleaned = str(url or "").strip().rstrip("/")
    if not cleaned:
        return ""
    if cleaned.endswith("/mcp"):
        return cleaned
    return f"{cleaned}/mcp"
