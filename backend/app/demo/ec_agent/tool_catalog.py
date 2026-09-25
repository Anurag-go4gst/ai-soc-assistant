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
    EcTool("splunk_mcp", "Splunk MCP", "Governed search: validated SPL, saved searches, detection inventory", "mcp"),
    EcTool("agilus_mcp", "Agilus MCP", "Device config and version reads; approved config changes and patches", "mcp"),
    EcTool("soc_kb", "SOC knowledge base", "SOPs, runbooks, standards and registers (RAG)", "knowledge"),
    EcTool("itsm", "ITSM", "Incidents, changes, team requests and CMDB records", "workflow"),
    EcTool("email", "Email", "Stakeholder notification (sent only after approval)", "notification"),
    EcTool("spl_validator", "SPL validator", "Deterministic SPL normalization and safety checks", "control"),
)

_BY_ID = {tool.tool_id: tool for tool in TOOL_CATALOG}

# Ordered: first match wins. Connectors that are not part of the architecture fold into the one
# that really does the job: device, switch and OT-inventory reads are Agilus; CMDB, IAM, AI-gateway
# and firewall actions are requests or changes raised in ITSM; EDR and gateway logs are Splunk data.
_ALIASES: tuple[tuple[str, str], ...] = (
    (r"agilus|device mcp|cisco|switch|arp|ot inventory|^network", "agilus_mcp"),
    (r"spl validator", "spl_validator"),
    (r"splunk|\bedr\b|ai gateway log", "splunk_mcp"),
    (r"\bemail\b|\bteams\b|\bsmtp\b", "email"),
    (r"cmdb|\biam\b|identity|ai gateway|soar|firewall|\bitsm\b|ticket", "itsm"),
    (r"soc-kb|\brag\b|playbook|runbook|knowledge", "soc_kb"),
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
