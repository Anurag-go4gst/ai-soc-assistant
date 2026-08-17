"""Local deterministic MCP capability vocabulary.

A ResourcePlan step may propose an `mcp_capability` value (via the existing
live `PlanStep.args_template["mcp_capability"]` seam — V1, not
`PlanStepV2.resource_capability`, which stays unactivated). Whatever
proposed it — including `mcp_specialist.py`'s advisory fill-blank pass — is
never trusted as execution authority. Before it can influence tool
selection it must validate against this bounded, closed vocabulary and
resolve through one fixed local tool mapping. Raw LLM-supplied tool names
never reach execution through this path or any other.
"""

from __future__ import annotations

Capability = str

EVENT_SEARCH = "EVENT_SEARCH"
SAVED_SEARCH_EXECUTION = "SAVED_SEARCH_EXECUTION"
SERVER_INFO = "SERVER_INFO"
INDEX_DISCOVERY = "INDEX_DISCOVERY"
INDEX_METADATA = "INDEX_METADATA"
SOURCE_METADATA = "SOURCE_METADATA"
USER_CONTEXT = "USER_CONTEXT"
KNOWLEDGE_OBJECT_DISCOVERY = "KNOWLEDGE_OBJECT_DISCOVERY"

KNOWN_CAPABILITIES: frozenset[str] = frozenset(
    {
        EVENT_SEARCH,
        SAVED_SEARCH_EXECUTION,
        SERVER_INFO,
        INDEX_DISCOVERY,
        INDEX_METADATA,
        SOURCE_METADATA,
        USER_CONTEXT,
        KNOWLEDGE_OBJECT_DISCOVERY,
    }
)

# One fixed local mapping, no collisions today. If a future capability ever
# maps to more than one tool, `mcp_tool_selector.py` applies deterministic
# precedence (registry.default_server's candidate first) or fails closed to
# human review -- it must never ask an LLM to pick by tool name.
CAPABILITY_TO_TOOL: dict[str, str] = {
    EVENT_SEARCH: "splunk_run_query",
    SAVED_SEARCH_EXECUTION: "splunk_run_saved_search",
    SERVER_INFO: "splunk_get_info",
    INDEX_DISCOVERY: "splunk_get_indexes",
    INDEX_METADATA: "splunk_get_index_info",
    SOURCE_METADATA: "splunk_get_metadata",
    USER_CONTEXT: "splunk_get_user_info",
    KNOWLEDGE_OBJECT_DISCOVERY: "splunk_get_knowledge_objects",
}

# Matching execution_intent at the existing gate boundary, for compatibility
# with mcp_execution_gate.py's READ_ONLY_EXECUTION_INTENTS / EXECUTION_ELIGIBLE
# checks. This is a projection, not a second authority object.
CAPABILITY_TO_EXECUTION_INTENT: dict[str, str] = {
    EVENT_SEARCH: "spl_search",
    SAVED_SEARCH_EXECUTION: "saved_search_execution",
    SERVER_INFO: "metadata_discovery",
    INDEX_DISCOVERY: "metadata_discovery",
    INDEX_METADATA: "metadata_discovery",
    SOURCE_METADATA: "metadata_discovery",
    USER_CONTEXT: "identity_lookup",
    KNOWLEDGE_OBJECT_DISCOVERY: "metadata_discovery",
}


def validate_capability(raw: str | None) -> str | None:
    """Return the capability if it is a member of the bounded vocabulary,
    else None. Unknown values (including anything an LLM might propose that
    is not on this list) are always rejected, never guessed or coerced."""
    if raw is None:
        return None
    candidate = str(raw).strip()
    return candidate if candidate in KNOWN_CAPABILITIES else None


def resolve_capability_tool_name(capability: str) -> str | None:
    """Deterministic 1:1 lookup. Returns None only if `capability` was not
    validated first (defensive — callers must validate before calling this)."""
    return CAPABILITY_TO_TOOL.get(capability)
