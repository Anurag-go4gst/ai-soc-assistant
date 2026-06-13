from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.base import ConnectorStatus, KnowledgeObjectRequest
from app.connectors.mcp.discovery import McpToolDescriptor
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.splunk_mcp_readiness import (
    ALLOWED_READ_TOOL,
    SPLUNK_DISCOVERY_TOOLS,
    is_allowed_read_tool,
    is_disallowed_tool,
    plan_splunk_search_call,
)


class SplunkMcpConnector:
    mode = "splunk_mcp"

    def health(self) -> ConnectorStatus:
        configured = bool(settings.splunk_mcp_enabled and settings.splunk_mcp_base_url.strip())
        registry = load_mcp_registry_status()
        if not registry.global_execution_enabled:
            return ConnectorStatus(
                mode=self.mode,
                configured=configured,
                available=False,
                detail="execution_disabled",
                implemented=True,
                fallback="mock",
            )
        return ConnectorStatus(
            mode=self.mode,
            configured=configured,
            available=False,
            detail="real_adapter_schema_unverified",
            implemented=True,
            fallback="mock",
        )

    def list_tools(self, server_name: str | None = None) -> list[McpToolDescriptor]:
        return []

    def plan_search(
        self,
        *,
        trace_id: str,
        spl_validation: dict[str, Any] | None,
        evidence_plan: dict[str, Any] | None = None,
        path_type: str | None = None,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Readiness-only planning surface — no network I/O."""
        record = plan_splunk_search_call(
            trace_id=trace_id,
            spl_validation=spl_validation,
            evidence_plan=evidence_plan,
            path_type=path_type,
            signals=signals,
        )
        return {
            "kind": record.kind,
            "server": record.server,
            "tool_name": record.tool_name,
            "arguments": dict(record.arguments),
            "block_reason": record.block_reason,
            "failure_mode": record.failure_mode,
            "policy_checks": list(record.policy_checks),
        }

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        if is_disallowed_tool(tool_name):
            return {"status": "blocked", "error": "tool_not_allowlisted", "tool_name": tool_name}
        is_discovery = tool_name in SPLUNK_DISCOVERY_TOOLS
        if not is_discovery and not is_allowed_read_tool(tool_name):
            return {"status": "blocked", "error": "tool_not_allowlisted", "tool_name": tool_name}
        if is_discovery:
            governance = arguments.get("_governance") if isinstance(arguments.get("_governance"), dict) else {}
            if not settings.mcp_discovery_enabled and governance.get("discovery_allowed") is not True:
                return {"status": "blocked", "error": "mcp_discovery_disabled", "tool_name": tool_name}
            raise NotImplementedError("Splunk MCP live discovery remains blocked until COE S5 sign-off.")
        registry = load_mcp_registry_status()
        if not registry.global_execution_enabled:
            return {
                "status": "blocked",
                "error": "mcp_global_execution_disabled",
                "tool_name": tool_name or ALLOWED_READ_TOOL,
            }
        raise NotImplementedError("Splunk MCP live call_tool remains blocked until COE S5 sign-off.")

    def execute_validated_spl(
        self,
        *,
        server_name: str,
        tool_name: str,
        normalized_spl: str,
        trace_id: str,
        policy_context: dict[str, Any],
    ) -> dict[str, Any]:
        plan = self.plan_search(
            trace_id=trace_id,
            spl_validation={"approved": True, "normalized_spl": normalized_spl},
            evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        )
        if plan.get("kind") != "planned_tool_call" or plan.get("failure_mode") == "execution_disabled":
            return {
                "status": "blocked",
                "error": plan.get("block_reason") or "mcp_execution_disabled",
                "planned_tool": plan,
            }
        raise NotImplementedError("Splunk MCP live execution remains blocked until COE S5 sign-off.")

    def discover_knowledge_objects(self, request: KnowledgeObjectRequest) -> dict[str, Any]:
        return {"status": "not_implemented", "objects": []}
