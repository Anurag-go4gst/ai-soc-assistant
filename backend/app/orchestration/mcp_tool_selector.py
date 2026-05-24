from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.discovery import BLOCKED_TOOL_TOKENS, safe_tool_name
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus, load_mcp_registry_status
from app.orchestration.human_review import human_review

EXECUTION_ELIGIBLE_SKILLS = {"attack_discovery", "spl_generation"}


def select_mcp_tool(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict[str, Any],
    execution_intent: str,
    spl_validation: dict[str, Any] | None,
    user_requested_mcp_server: str | None = None,
    user_requested_mcp_tool: str | None = None,
    llm_tool_recommendation: dict[str, Any] | None = None,
    registry: McpRegistryStatus | None = None,
) -> dict[str, Any]:
    registry = registry or load_mcp_registry_status()
    review = _preflight_review(selected_skill, execution_intent, spl_validation)
    if review:
        return _result(
            trace_id=trace_id,
            execution_intent=execution_intent,
            status="requires_human_review",
            reason=review["reason"],
            human_review=review,
        )

    if settings.llm_tool_recommendation_enabled and llm_tool_recommendation:
        # Advisory only; deterministic checks below still decide.
        _ = llm_tool_recommendation.get("tool_category")

    server = _select_server(registry, user_requested_mcp_server)
    if server is None:
        return _review_result(trace_id, execution_intent, "connector_configuration", "requested_mcp_server_not_found")
    if not server.available:
        return _review_result(trace_id, execution_intent, "connector_configuration", server.last_error or "mcp_server_unavailable")

    tools = list(getattr(server, "discovered_tools", []))
    if not tools:
        return _review_result(trace_id, execution_intent, "connector_configuration", "no_discovered_tools")

    if user_requested_mcp_tool:
        requested_tool = safe_tool_name(user_requested_mcp_tool)
        requested = next((tool for tool in tools if tool.get("name") == requested_tool), None)
        if requested is None:
            return _review_result(trace_id, execution_intent, "tool_selection_review", "requested_tool_not_found")
        if _tool_blocked(requested):
            return _review_result(trace_id, execution_intent, "policy_exception_request", requested.get("blocked_reason") or "requested_tool_blocked")
        if not _tool_matches_intent(requested, execution_intent):
            return _review_result(trace_id, execution_intent, "tool_selection_review", "requested_tool_intent_mismatch")
        return _selected(trace_id, execution_intent, server, requested, "requested_safe_tool_selected_after_policy_check")

    eligible = [
        tool
        for tool in tools
        if not _tool_blocked(tool) and _tool_matches_intent(tool, execution_intent)
    ]
    if not eligible:
        return _review_result(trace_id, execution_intent, "tool_selection_review", "no_allowlisted_tool_found")

    return _selected(trace_id, execution_intent, server, eligible[0], "deterministic_safe_tool_selected")


def _preflight_review(selected_skill: str, execution_intent: str, spl_validation: dict[str, Any] | None) -> dict[str, Any] | None:
    if execution_intent != "spl_search":
        return human_review(
            "tool_selection_review",
            "execution_intent_ambiguous",
            "soc_lead",
            ["choose_different_mcp_tool", "reject_execution"],
            "The execution intent is ambiguous and needs analyst review.",
        )
    if selected_skill not in EXECUTION_ELIGIBLE_SKILLS:
        return human_review(
            "tool_selection_review",
            "skill_not_execution_eligible",
            "soc_lead",
            ["reject_execution"],
            "This routed skill is not eligible for MCP execution.",
        )
    if not spl_validation or not spl_validation.get("approved"):
        return human_review(
            "spl_revision",
            "spl_validation_failed",
            "analyst",
            ["regenerate_spl", "edit_spl", "reject_execution"],
            "SPL validation failed. Revise the SPL before execution can be considered.",
        )
    if spl_validation.get("normalized_spl") is None:
        return human_review(
            "spl_revision",
            "normalized_spl_null",
            "analyst",
            ["regenerate_spl", "edit_spl", "reject_execution"],
            "Validated normalized SPL is missing, so execution is blocked.",
        )
    return None


def _select_server(registry: McpRegistryStatus, requested_name: str | None) -> McpServerStatus | None:
    if requested_name:
        safe_requested = safe_tool_name(requested_name)
        return next((server for server in registry.servers if server.name == safe_requested), None)
    return next((server for server in registry.servers if server.name == registry.default_server), None) or (registry.servers[0] if registry.servers else None)


def _tool_blocked(tool: dict[str, Any]) -> bool:
    name = str(tool.get("name", "")).lower()
    description = str(tool.get("description", "")).lower()
    return bool(tool.get("blocked")) or any(token in f"{name} {description}" for token in BLOCKED_TOOL_TOKENS)


def _tool_matches_intent(tool: dict[str, Any], execution_intent: str) -> bool:
    return execution_intent == "spl_search" and tool.get("capability") == "spl_search"


def _selected(trace_id: str, execution_intent: str, server: McpServerStatus, tool: dict[str, Any], reason: str) -> dict[str, Any]:
    return _result(
        trace_id=trace_id,
        execution_intent=execution_intent,
        status="selected",
        reason=reason,
        selected_mcp_server=server.name,
        selected_mcp_tool=str(tool.get("name")),
        human_review=None,
    )


def _review_result(trace_id: str, execution_intent: str, review_type: str, reason: str) -> dict[str, Any]:
    reviewer_role = "platform_admin" if review_type == "connector_configuration" else "soc_lead"
    actions = ["configure_connector"] if review_type == "connector_configuration" else ["choose_different_mcp_tool", "reject_execution"]
    if review_type == "policy_exception_request":
        actions = ["request_policy_exception", "choose_different_mcp_tool", "reject_execution"]
    review = human_review(
        review_type,
        reason,
        reviewer_role,
        actions,
        "MCP tool selection requires review before execution can proceed.",
    )
    return _result(trace_id=trace_id, execution_intent=execution_intent, status="requires_human_review", reason=reason, human_review=review)


def _result(
    *,
    trace_id: str,
    execution_intent: str,
    status: str,
    reason: str,
    human_review: dict[str, Any] | None,
    selected_mcp_server: str | None = None,
    selected_mcp_tool: str | None = None,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "selected_mcp_server": selected_mcp_server,
        "selected_mcp_tool": selected_mcp_tool,
        "execution_intent": execution_intent,
        "tool_selection_status": status,
        "tool_selection_reason": reason,
        "blocked_reason": reason if status != "selected" else None,
        "human_review": human_review,
    }
