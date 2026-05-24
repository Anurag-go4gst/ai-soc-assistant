from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BLOCKED_TOOL_TOKENS = (
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

SPLUNK_TOOL_CLASSIFICATIONS = {
    "splunk_run_query": ["splunk_core", "execution"],
    "run_splunk_query": ["splunk_core", "execution"],
    "splunk_get_info": ["splunk_core", "discovery_context"],
    "splunk_get_indexes": ["splunk_core", "discovery_context", "index_context"],
    "splunk_get_index_info": ["splunk_core", "discovery_context", "index_context"],
    "splunk_get_metadata": ["splunk_core", "discovery_context", "metadata_context"],
    "get_splunk_metadata": ["splunk_core", "discovery_context", "metadata_context"],
    "splunk_get_user_info": ["splunk_core", "discovery_context", "admin_or_sensitive"],
    "splunk_get_user_list": ["splunk_core", "admin_or_sensitive"],
    "splunk_get_kv_store_collections": ["splunk_core", "discovery_context"],
    "splunk_get_knowledge_objects": ["splunk_core", "discovery_context", "knowledge_object_context"],
    "splunk_run_saved_search": ["splunk_core", "saved_search_execution", "execution"],
    "saia_generate_spl": ["saia", "candidate_generation"],
    "saia_explain_spl": ["saia", "explanation"],
    "saia_optimize_spl": ["saia", "optimization"],
    "saia_ask_splunk_question": ["saia", "splunk_guidance"],
}


@dataclass(frozen=True)
class McpToolDescriptor:
    name: str
    description: str = ""
    capability: str = "unknown"
    blocked: bool = False
    blocked_reason: str | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)

    def safe_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": _safe_text(self.description),
            "capability": self.capability,
            "categories": list(self.categories),
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
        }


def classify_mcp_tool(name: str, description: str = "", server_type: str = "generic") -> McpToolDescriptor:
    safe_name = safe_tool_name(name)
    safe_description = _safe_text(description)
    lowered = f"{safe_name} {safe_description}".lower()
    categories = _splunk_categories(safe_name) if server_type == "splunk" else []
    if categories:
        capability = _capability_from_categories(categories)
        blocked = "admin_or_sensitive" in categories and "execution" not in categories
        return McpToolDescriptor(
            name=safe_name,
            description=safe_description,
            capability=capability,
            blocked=blocked,
            blocked_reason="admin_or_sensitive_tool" if blocked else None,
            categories=categories,
        )
    blocked_token = next((token for token in BLOCKED_TOOL_TOKENS if token in lowered), None)
    if blocked_token:
        return McpToolDescriptor(
            name=safe_name,
            description=safe_description,
            capability="blocked",
            blocked=True,
            blocked_reason=f"blocked_tool_pattern:{blocked_token}",
            categories=["admin_or_sensitive"],
        )

    capability = "unknown"
    for candidate, patterns in SAFE_TOOL_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            capability = candidate
            break

    if server_type == "splunk" and capability == "unknown" and ("spl" in lowered or "splunk" in lowered):
        capability = "spl_search"

    return McpToolDescriptor(name=safe_name, description=safe_description, capability=capability, categories=[capability] if capability != "unknown" else ["unknown"])


def mock_discovered_tools(server_type: str = "splunk") -> list[McpToolDescriptor]:
    tools = [
        classify_mcp_tool("run_splunk_query", "Run validator-approved bounded SPL search.", server_type),
        classify_mcp_tool("splunk_get_indexes", "Read Splunk index list.", server_type),
        classify_mcp_tool("get_splunk_metadata", "Read Splunk index and sourcetype metadata.", server_type),
        classify_mcp_tool("saia_generate_spl", "Generate SPL with Splunk AI Assistant.", server_type),
    ]
    return tools


def _splunk_categories(name: str) -> list[str]:
    return list(SPLUNK_TOOL_CLASSIFICATIONS.get(name, []))


def _capability_from_categories(categories: list[str]) -> str:
    if "candidate_generation" in categories:
        return "candidate_generation"
    if "explanation" in categories:
        return "explanation"
    if "optimization" in categories:
        return "optimization"
    if "splunk_guidance" in categories:
        return "splunk_guidance"
    if "saved_search_execution" in categories:
        return "saved_search_execution"
    if "execution" in categories:
        return "spl_search"
    if "knowledge_object_context" in categories:
        return "knowledge_object_discovery"
    if "metadata_context" in categories or "index_context" in categories or "discovery_context" in categories:
        return "metadata_lookup"
    return "unknown"


def safe_tool_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "_", value.strip())[:120]


def _safe_text(value: str) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", value.strip())
    cleaned = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", cleaned)
    cleaned = re.sub(r"(?i)(password|passwd|secret|token|api[_-]?key|credential)=\S+", r"\1=[redacted]", cleaned)
    return cleaned[:240]
