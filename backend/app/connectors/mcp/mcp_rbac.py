"""Deterministic MCP RBAC — role resolution and tool allowlist enforcement."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.splunk.capabilities import RUN_QUERY_ALIASES, TOOL_ALIASES

_POLICY_PATH = Path(__file__).with_name("mcp_rbac_policy.json")
DEFAULT_SESSION_ROLE_WHEN_UNSCOPED = "demo_analyst"


def canonical_mcp_tool_name(tool: str) -> str:
    """Normalize discovery aliases to the canonical playbook/RBAC tool id."""
    if tool in RUN_QUERY_ALIASES:
        return "splunk_run_query"
    for canonical, aliases in TOOL_ALIASES.items():
        if tool in aliases:
            return canonical
    return tool


@lru_cache(maxsize=1)
def load_rbac_policy() -> dict[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def resolve_mcp_rbac_role(session_role: str | None) -> str:
    """Map app session role to a governed MCP RBAC role."""
    policy = load_rbac_policy()
    if not session_role:
        return str(policy.get("default_role") or "viewer")
    mapped = (policy.get("session_role_map") or {}).get(str(session_role))
    if mapped:
        return str(mapped)
    roles = policy.get("roles") or {}
    if session_role in roles:
        return str(session_role)
    return str(policy.get("default_role") or "viewer")


def session_role_for_mcp_gate(session_role: str | None) -> str:
    """Map missing session roles to the dev/demo analyst default (matches auth-off posture)."""
    return session_role if session_role is not None else DEFAULT_SESSION_ROLE_WHEN_UNSCOPED


def _direct_allowed_tools(role: str) -> set[str]:
    policy = load_rbac_policy()
    roles = policy.get("roles") or {}
    spec = roles.get(role) or {}
    return {str(name) for name in (spec.get("allowed_tools") or []) if name}


def effective_allowed_tools(role: str) -> frozenset[str]:
    """Role allowlist plus inherited roles (viewer ⊆ analyst ⊆ soc_lead)."""
    policy = load_rbac_policy()
    inheritance = policy.get("role_inheritance") or {}
    allowed = set(_direct_allowed_tools(role))
    for inherited in inheritance.get(role) or []:
        allowed.update(_direct_allowed_tools(str(inherited)))
    never = {str(name) for name in (policy.get("never_allowed") or []) if name}
    return frozenset(allowed - never)


def is_tool_allowed_for_role(tool: str, role: str | None) -> bool:
    if not tool:
        return False
    canonical = canonical_mcp_tool_name(tool)
    policy = load_rbac_policy()
    never = {str(name) for name in (policy.get("never_allowed") or []) if name}
    if canonical in never:
        return False
    resolved = resolve_mcp_rbac_role(role)
    return canonical in effective_allowed_tools(resolved)


def rbac_denial_reason(tool: str, role: str | None) -> str | None:
    if is_tool_allowed_for_role(tool, role):
        return None
    resolved = resolve_mcp_rbac_role(role)
    return f"rbac_denied:{resolved}:{tool}"
