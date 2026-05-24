from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BLOCKED_TOOL_TOKENS = (
    "generate_spl",
    "explain_spl",
    "optimize_spl",
    "saia",
    "assistant",
    "outputlookup",
    "collect",
    "delete",
    "sendemail",
    "write",
    "modify",
    "admin",
    "rest",
    "script",
)

SAFE_TOOL_PATTERNS = {
    "spl_search": ("search", "query", "run_spl", "run_query", "splunk_search"),
    "metadata_lookup": ("metadata", "index", "sourcetype", "field"),
    "knowledge_object_discovery": ("savedsearch", "knowledge", "lookup", "dashboard", "object"),
    "ticket_lookup": ("ticket", "case", "incident"),
    "asset_lookup": ("asset", "host", "device"),
}


@dataclass(frozen=True)
class McpToolDescriptor:
    name: str
    description: str = ""
    capability: str = "unknown"
    blocked: bool = False
    blocked_reason: str | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)

    def safe_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": _safe_text(self.description),
            "capability": self.capability,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
        }


def classify_mcp_tool(name: str, description: str = "", server_type: str = "generic") -> McpToolDescriptor:
    safe_name = safe_tool_name(name)
    safe_description = _safe_text(description)
    lowered = f"{safe_name} {safe_description}".lower()
    blocked_token = next((token for token in BLOCKED_TOOL_TOKENS if token in lowered), None)
    if blocked_token:
        return McpToolDescriptor(
            name=safe_name,
            description=safe_description,
            capability="blocked",
            blocked=True,
            blocked_reason=f"blocked_tool_pattern:{blocked_token}",
        )

    capability = "unknown"
    for candidate, patterns in SAFE_TOOL_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            capability = candidate
            break

    if server_type == "splunk" and capability == "unknown" and ("spl" in lowered or "splunk" in lowered):
        capability = "spl_search"

    return McpToolDescriptor(name=safe_name, description=safe_description, capability=capability)


def mock_discovered_tools(server_type: str = "splunk") -> list[McpToolDescriptor]:
    tools = [
        classify_mcp_tool("run_splunk_query", "Run validator-approved bounded SPL search.", server_type),
        classify_mcp_tool("get_splunk_metadata", "Read Splunk index and sourcetype metadata.", server_type),
        classify_mcp_tool("saia_generate_spl", "Generate SPL with Splunk AI Assistant.", server_type),
    ]
    return tools


def safe_tool_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "_", value.strip())[:120]


def _safe_text(value: str) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", value.strip())
    cleaned = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", cleaned)
    cleaned = re.sub(r"(?i)(password|passwd|secret|token|api[_-]?key|credential)=\S+", r"\1=[redacted]", cleaned)
    return cleaned[:240]
