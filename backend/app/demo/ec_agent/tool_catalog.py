"""One catalog of the tools/MCP servers the Experience Center agent can use.

Every scenario used to spell its tools as free text ("ITSM (simulated)", "Device MCP",
"Email · Network ops"), so the same connector looked different from question to question.
Plan steps now resolve their ``tools`` strings through this catalog so the UI can show one
consistent "connected tools" fabric. All entries are deterministic EC fixtures — the
``demo_fixture`` flag is shown once per page instead of being repeated in step text.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EcTool:
    tool_id: str
    name: str
    role: str
    kind: str  # "mcp" | "knowledge" | "workflow" | "notification" | "control"
    demo_fixture: bool = True


TOOL_CATALOG: tuple[EcTool, ...] = (
    EcTool("splunk_mcp", "Splunk MCP", "SIEM search — governed, validated SPL only", "mcp"),
    EcTool("agilus_mcp", "Agilus MCP", "Vulnerability & patch orchestration", "mcp"),
    EcTool("device_mcp", "Device MCP", "Router, firewall and VPN device version/config reads", "mcp"),
    EcTool("cmdb", "CMDB", "Asset inventory and ownership", "mcp"),
    EcTool("ot_inventory", "OT inventory", "Live OT asset presence by cell", "mcp"),
    EcTool("network_switch", "Network / switch", "ARP/MAC and port state", "mcp"),
    EcTool("iam", "IAM", "Identity, credentials and conditional access", "mcp"),
    EcTool("edr", "EDR", "Endpoint process and session telemetry", "mcp"),
    EcTool("ai_gateway", "AI gateway", "Session controls for the customer AI assistant", "mcp"),
    EcTool("soc_kb", "SOC-KB (RAG)", "Governed retrieval over SOPs, policy and regulation", "knowledge"),
    EcTool("playbook_registry", "Playbook registry", "SOAR playbooks and emergency runbooks", "knowledge"),
    EcTool("spl_validator", "SPL validator", "Deterministic SPL safety and scope checks", "control"),
    EcTool("itsm", "ITSM", "Incidents, change tickets and data-quality tickets", "workflow"),
    EcTool("soar_firewall", "SOAR / firewall", "Firewall change execution through SOAR", "workflow"),
    EcTool("email", "Email", "Allowlisted outbound notifications (send is human-approved)", "notification"),
)

_BY_ID = {tool.tool_id: tool for tool in TOOL_CATALOG}

# Ordered: first match wins, so specific names are listed before generic ones.
_ALIASES: tuple[tuple[str, str], ...] = (
    (r"agilus", "agilus_mcp"),
    (r"spl validator", "spl_validator"),
    (r"splunk", "splunk_mcp"),
    (r"device mcp|cisco", "device_mcp"),
    (r"cmdb", "cmdb"),
    (r"ot inventory", "ot_inventory"),
    (r"network \(|switch|^network$", "network_switch"),
    # Email before IAM: "Email · Identity / IAM" is an escalation email, not an IAM write.
    (r"\bemail\b|\bteams\b|\bsmtp\b", "email"),
    (r"\biam\b|identity", "iam"),
    (r"\bedr\b", "edr"),
    (r"ai gateway", "ai_gateway"),
    (r"soc-kb|\brag\b", "soc_kb"),
    (r"playbook", "playbook_registry"),
    (r"soar|firewall", "soar_firewall"),
    (r"\bitsm\b|ticket", "itsm"),
)


def resolve_tool_id(label: str) -> str | None:
    """Map a free-text step tool label to a catalog id (None when unknown)."""
    text = label.strip().lower()
    if text in _BY_ID:
        return text
    for pattern, tool_id in _ALIASES:
        if re.search(pattern, text):
            return tool_id
    return None


def tool_display_name(tool_id: str) -> str:
    return _BY_ID[tool_id].name


def tool_fabric(used_tool_ids: set[str]) -> list[dict[str, Any]]:
    """Every catalog tool with a ``used`` flag for the current plan (stable catalog order)."""
    return [{**asdict(tool), "used": tool.tool_id in used_tool_ids} for tool in TOOL_CATALOG]
