from __future__ import annotations

from time import perf_counter
from typing import Any

from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.human_review import human_review, no_human_review
from app.orchestration.mcp_tool_selector import EXECUTION_ELIGIBLE_SKILLS, select_mcp_tool

RESULT_PREVIEW_CAP = 5


def evaluate_mcp_execution(
    *,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict[str, Any],
    spl_validation: dict[str, Any] | None,
    requested_mcp_server: str | None = None,
    requested_mcp_tool: str | None = None,
    llm_tool_recommendation: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    telemetry = get_telemetry_connector()
    registry = load_mcp_registry_status()
    _record_discovery(telemetry, trace_id, registry)

    selection = select_mcp_tool(
        trace_id=trace_id,
        selected_skill=selected_skill,
        workflow_plan=workflow_plan,
        execution_intent="spl_search",
        spl_validation=spl_validation,
        user_requested_mcp_server=requested_mcp_server,
        user_requested_mcp_tool=requested_mcp_tool,
        llm_tool_recommendation=llm_tool_recommendation,
        registry=registry,
    )
    telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_selection", **_selection_event(selection))

    if selection["tool_selection_status"] != "selected":
        review = selection.get("human_review") or _review("tool_selection_review", selection["tool_selection_reason"])
        execution = _blocked_execution(selection, "requires_human_review", selection["tool_selection_reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_blocked", reason=selection["tool_selection_reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=selection["tool_selection_reason"])
        return execution, review

    review = _gate_review(
        selected_skill=selected_skill,
        spl_validation=spl_validation,
        selected_mcp_server=str(selection["selected_mcp_server"]),
        selected_mcp_tool=str(selection["selected_mcp_tool"]),
        registry=registry,
    )
    if review["required"]:
        execution = _blocked_execution(selection, "requires_human_review", review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_blocked", reason=review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_requires_human_review", reason=review["reason"])
        return execution, review

    normalized_spl = str(spl_validation["normalized_spl"])
    started = perf_counter()
    telemetry.record_mcp_execution(
        trace_id,
        event_type="mcp_execution_started",
        selected_mcp_server=selection["selected_mcp_server"],
        selected_mcp_tool=selection["selected_mcp_tool"],
    )
    try:
        result = get_mcp_connector().call_tool(
            str(selection["selected_mcp_tool"]),
            {"query": normalized_spl},
            server_name=str(selection["selected_mcp_server"]),
        )
    except NotImplementedError:
        review = _review("admin_action_required", "real_mcp_adapter_not_implemented", "platform_admin", ["configure_connector", "reject_execution"])
        execution = _blocked_execution(selection, "requires_human_review", review["reason"])
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_failed", reason=review["reason"])
        return execution, review
    except Exception as exc:  # noqa: BLE001 - execution gate must fail closed.
        review = _review("admin_action_required", "mcp_execution_failed", "platform_admin", ["configure_connector", "reject_execution"])
        execution = _blocked_execution(selection, "failed", f"mcp_execution_failed:{type(exc).__name__}")
        telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_failed", reason=type(exc).__name__)
        return execution, review

    rows = _safe_rows(result.get("rows", []))
    duration_ms = int((perf_counter() - started) * 1000)
    execution = {
        "status": "executed",
        "execution_intent": "spl_search",
        "selected_mcp_server": selection["selected_mcp_server"],
        "selected_mcp_tool": selection["selected_mcp_tool"],
        "tool_selection_status": selection["tool_selection_status"],
        "tool_selection_reason": selection["tool_selection_reason"],
        "executed_spl": normalized_spl,
        "result_count": min(int(result.get("row_count", len(rows)) or 0), RESULT_PREVIEW_CAP),
        "results_preview": rows[:RESULT_PREVIEW_CAP],
        "block_reason": None,
        "duration_ms": duration_ms,
    }
    telemetry.record_mcp_execution(trace_id, event_type="mcp_execution_completed", result_count=execution["result_count"], duration_ms=duration_ms)
    return execution, no_human_review()


def _record_discovery(telemetry: Any, trace_id: str, registry: Any) -> None:
    telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_discovery_started")
    try:
        telemetry.record_mcp_execution(
            trace_id,
            event_type="mcp_tool_discovery_completed",
            server_count=len(registry.servers),
            discovered_tools_count=sum(server.discovered_tools_count for server in registry.servers),
            blocked_tools_count=sum(server.blocked_tools_count for server in registry.servers),
        )
    except Exception as exc:  # noqa: BLE001
        telemetry.record_mcp_execution(trace_id, event_type="mcp_tool_discovery_failed", reason=type(exc).__name__)


def _gate_review(
    *,
    selected_skill: str,
    spl_validation: dict[str, Any] | None,
    selected_mcp_server: str,
    selected_mcp_tool: str,
    registry: Any,
) -> dict[str, Any]:
    if selected_skill not in EXECUTION_ELIGIBLE_SKILLS:
        return _review("tool_selection_review", "skill_not_execution_eligible")
    if not spl_validation or spl_validation.get("approved") is not True:
        return _review("spl_revision", "spl_validation_failed", "analyst", ["regenerate_spl", "edit_spl", "reject_execution"])
    if spl_validation.get("normalized_spl") is None:
        return _review("spl_revision", "normalized_spl_null", "analyst", ["regenerate_spl", "edit_spl", "reject_execution"])
    if not registry.global_execution_enabled:
        return _review("execution_approval", "mcp_global_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    server = next((item for item in registry.servers if item.name == selected_mcp_server), None)
    if server is None:
        return _review("connector_configuration", "mcp_server_unavailable", "platform_admin", ["configure_connector", "reject_execution"])
    if not server.execution_enabled:
        return _review("execution_approval", "mcp_server_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    if not server.available:
        return _review("connector_configuration", "mcp_server_unavailable", "platform_admin", ["configure_connector", "reject_execution"])
    tool = next((item for item in server.discovered_tools if item.get("name") == selected_mcp_tool), None)
    if tool is None:
        return _review("tool_selection_review", "selected_tool_not_found")
    if tool.get("blocked"):
        return _review("policy_exception_request", tool.get("blocked_reason") or "selected_tool_blocked", "security_admin", ["request_policy_exception", "reject_execution"])
    if selected_mcp_tool == "splunk_run_saved_search" and not getattr(server, "search_execution_allowed", False):
        return _review("execution_approval", "saved_search_execution_disabled", "soc_lead", ["approve_execution_after_policy_check", "reject_execution"])
    if tool.get("capability") != "spl_search":
        return _review("tool_selection_review", "selected_tool_not_spl_search")
    if registry.mode != "mock":
        return _review("admin_action_required", "real_mcp_adapter_not_implemented", "platform_admin", ["configure_connector", "reject_execution"])
    return no_human_review()


def _blocked_execution(selection: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "execution_intent": selection["execution_intent"],
        "selected_mcp_server": selection.get("selected_mcp_server"),
        "selected_mcp_tool": selection.get("selected_mcp_tool"),
        "tool_selection_status": selection["tool_selection_status"],
        "tool_selection_reason": selection["tool_selection_reason"],
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "block_reason": reason,
        "duration_ms": 0,
    }


def _review(
    review_type: str,
    reason: str,
    reviewer_role: str = "soc_lead",
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    return human_review(
        review_type,
        reason,
        reviewer_role,
        allowed_actions or ["choose_different_mcp_tool", "reject_execution"],
        "Execution cannot safely proceed until this item is reviewed.",
    )


def _selection_event(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_mcp_server": selection.get("selected_mcp_server"),
        "selected_mcp_tool": selection.get("selected_mcp_tool"),
        "execution_intent": selection.get("execution_intent"),
        "tool_selection_status": selection.get("tool_selection_status"),
        "tool_selection_reason": selection.get("tool_selection_reason"),
        "blocked_reason": selection.get("blocked_reason"),
    }


def _safe_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    safe: list[dict[str, Any]] = []
    for row in rows[:RESULT_PREVIEW_CAP]:
        if not isinstance(row, dict):
            continue
        safe.append({str(key)[:80]: _safe_value(value) for key, value in row.items()})
    return safe


def _safe_value(value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:240]
