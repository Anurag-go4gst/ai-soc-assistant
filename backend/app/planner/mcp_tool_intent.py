"""WS4d — Map catalogue / resource plan to deterministic Splunk MCP tool intent."""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.splunk_mcp_readiness import (
    ALLOWED_READ_TOOL,
    McpToolCallRecord,
    plan_splunk_search_call,
)
from app.planner.resource_plan import ResourcePlan

_USE_CASE_MCP_HINTS: dict[str, str] = {
    "auth_failed_login_spike": "splunk.search",
    "vpn_login_anomaly": "splunk.search",
    "edr_powershell_suspicious_command": "splunk.search",
}

_PATHS_WITHOUT_MCP = frozenset(
    {
        "unsafe_blocked",
        "rag_only",
        "generic_soc_guidance",
        "mitre_context_required",
        "clarification_required",
        "guided_investigation",
    }
)


def resolve_mcp_tool_intent(
    *,
    trace_id: str,
    evidence_plan: dict[str, Any] | None,
    resource_plan: ResourcePlan | None = None,
    path_type: str | None = None,
    intent_family: str | None = None,
    use_case_id: str | None = None,
    signals: dict[str, Any] | None = None,
    spl_validation: dict[str, Any] | None = None,
    source_profile_missing: bool = False,
    llm_tool_recommendation: dict[str, Any] | None = None,
) -> McpToolCallRecord:
    """Deterministic MCP intent from evidence/resource plan — LLM cannot authorize."""
    plan = dict(evidence_plan or {})
    if path_type in _PATHS_WITHOUT_MCP:
        plan.setdefault("needs_mcp", False)
        plan.setdefault("mcp_allowed", False)

    if resource_plan is not None:
        mcp_steps = [step for step in resource_plan.steps if step.purpose == "mcp_execution"]
        if not mcp_steps:
            plan["needs_mcp"] = False
            plan["mcp_allowed"] = False
        elif use_case_id and use_case_id in _USE_CASE_MCP_HINTS:
            plan.setdefault("needs_mcp", True)

    return plan_splunk_search_call(
        trace_id=trace_id,
        spl_validation=spl_validation,
        evidence_plan=plan,
        path_type=path_type,
        intent_family=intent_family,
        use_case_id=use_case_id,
        signals=signals,
        source_profile_missing=source_profile_missing,
        llm_tool_recommendation=llm_tool_recommendation,
    )


def mcp_intent_summary(record: McpToolCallRecord) -> dict[str, Any]:
    return {
        "server": record.server,
        "tool_name": record.tool_name,
        "kind": record.kind,
        "block_reason": record.block_reason,
        "failure_mode": record.failure_mode,
        "policy_checks": list(record.policy_checks),
        "allowed_read_tool": ALLOWED_READ_TOOL,
    }
