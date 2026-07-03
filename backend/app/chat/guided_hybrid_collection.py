"""Planned/collected evidence hops for guided hybrid dispatch (REV4 batch 2 P12)."""

from __future__ import annotations

from typing import Any, Callable

from app.chat.evidence_loop import record_hop
from app.connectors.mcp.mcp_rbac import session_role_for_mcp_gate
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.spl.guided_safe_spl_dispatch import build_guided_safe_spl_dispatch_plan
from app.spl.mcp_loop_discovery import execute_loop_discovery_hop

SafeCatalogExecutionFn = Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]


def _tool_name_from_resource_id(resource_id: str) -> str:
    prefix = "mcp_tool:"
    if resource_id.startswith(prefix):
        return resource_id[len(prefix) :]
    return resource_id


def _template_id_from_step(step: PlanStep) -> str | None:
    resource_id = str(step.resource_id or "")
    prefix = "spl_template_family:"
    if resource_id.startswith(prefix):
        return resource_id[len(prefix) :]
    return None


def collect_guided_hybrid_evidence(
    state: dict[str, Any],
    *,
    validated_resource: ResourcePlan,
    execute_safe_catalog_spl: SafeCatalogExecutionFn | None = None,
) -> tuple[dict[str, Any], int]:
    """Run approved guided hybrid evidence steps; never free-form ``splunk_run_query``."""
    updated = dict(state)
    collected_count = 0
    rbac_role = session_role_for_mcp_gate(state.get("session_role"))
    trace_id = state.get("trace_id")

    for step in validated_resource.steps:
        if step.purpose == "mcp_discovery":
            tool = _tool_name_from_resource_id(str(step.resource_id or ""))
            if tool == "splunk_run_query":
                continue
            hop = execute_loop_discovery_hop(
                tool,
                rbac_role=rbac_role,
                trace_id=str(trace_id) if trace_id else None,
            )
            patch = record_hop(
                updated,
                tool=tool,
                delivered=list(hop.get("delivered") or []),
                outcome=str(hop.get("outcome") or "planned"),
                payload=hop.get("payload") if isinstance(hop.get("payload"), dict) else {},
            )
            updated = {**updated, **patch}
            if str(hop.get("outcome")) == "collected":
                collected_count += 1
            continue

        if step.purpose == "safe_catalog_query":
            template_id = _template_id_from_step(step)
            dispatch_plan = build_guided_safe_spl_dispatch_plan(template_id)
            outcome = dispatch_plan.outcome
            payload = dict(dispatch_plan.payload)
            delivered = list(dispatch_plan.delivered)
            if dispatch_plan.ready and execute_safe_catalog_spl is not None:
                execution, review = execute_safe_catalog_spl(dispatch_plan.spl_validation or {})
                outcome = str(execution.get("status") or outcome)
                if outcome == "executed":
                    outcome = "collected"
                    if "query_results" not in delivered:
                        delivered.append("query_results")
                payload.update(
                    {
                        "execution_status": execution.get("status"),
                        "tool_selection_status": execution.get("tool_selection_status"),
                        "tool_selection_reason": execution.get("tool_selection_reason"),
                        "block_reason": execution.get("block_reason"),
                        "human_review_required": bool(review.get("required")),
                        "human_review_reason": review.get("reason"),
                    }
                )
            elif dispatch_plan.ready:
                outcome = "blocked"
                payload["block_reason"] = "guided_safe_execution_callback_unavailable"
            elif dispatch_plan.reason:
                payload["block_reason"] = dispatch_plan.reason
            patch = record_hop(
                updated,
                tool="guided_safe_catalog",
                delivered=delivered,
                outcome=outcome,
                payload=payload,
            )
            updated = {**updated, **patch}
            if outcome == "collected":
                collected_count += 1

    return updated, collected_count
