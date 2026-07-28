"""Planned/collected evidence hops for guided hybrid dispatch (REV4 batch 2 P12)."""

from __future__ import annotations

from typing import Any, Callable

from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    apply_execution_uncertainty_to_state,
    apply_idempotent_hop_to_state,
    operation_contract_for_step,
    plan_step_operation_identity,
    provenance_from_state,
    run_idempotent_execution_step,
)
from app.chat.evidence_loop import record_hop
from app.chat.hook_replay_contract import (
    HOOK_REPLAY_CONTRACT_VERSION,
    HookReplayEnvelope,
    build_safe_catalog_fingerprint,
    build_stored_hook_payload,
)
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


def _run_mcp_discovery_step(
    state: dict[str, Any],
    *,
    step: PlanStep,
    rbac_role: str,
    trace_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    tool = _tool_name_from_resource_id(str(step.resource_id or ""))
    if tool == "splunk_run_query":
        return state, {}, 0
    hop = execute_loop_discovery_hop(
        tool,
        rbac_role=rbac_role,
        trace_id=trace_id,
    )
    patch = record_hop(
        state,
        tool=tool,
        delivered=list(hop.get("delivered") or []),
        outcome=str(hop.get("outcome") or "planned"),
        payload=hop.get("payload") if isinstance(hop.get("payload"), dict) else {},
    )
    collected = 1 if str(hop.get("outcome")) == "collected" else 0
    return {**state, **patch}, patch, collected


def _run_safe_catalog_step(
    state: dict[str, Any],
    *,
    step: PlanStep,
    execute_safe_catalog_spl: SafeCatalogExecutionFn | None,
) -> tuple[dict[str, Any], dict[str, Any], int]:
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
        state,
        tool="guided_safe_catalog",
        delivered=delivered,
        outcome=outcome,
        payload=payload,
    )
    collected = 1 if outcome == "collected" else 0
    return {**state, **patch}, patch, collected


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
    resource_plan_id, handoff_version, handoff_id = provenance_from_state(updated)
    plan_provenance = dict(validated_resource.provenance or {})
    plan_id = resource_plan_id or str(plan_provenance.get("resource_plan_id") or "")
    handoff_id = handoff_id or (str(plan_provenance.get("handoff_id")) if plan_provenance.get("handoff_id") else None)
    if handoff_version is None and plan_provenance.get("handoff_version") is not None:
        handoff_version = int(plan_provenance["handoff_version"])

    for step in validated_resource.steps:
        purpose = str(step.purpose or "")
        if purpose not in {"mcp_discovery", "safe_catalog_query"}:
            continue
        step_id = str(step.step_id or "")
        operation = plan_step_operation_identity(step.model_dump())

        def _execute_step() -> dict[str, Any]:
            nonlocal updated, collected_count
            if purpose == "mcp_discovery":
                next_state, patch, delta = _run_mcp_discovery_step(
                    updated,
                    step=step,
                    rbac_role=rbac_role,
                    trace_id=str(trace_id) if trace_id else None,
                )
            else:
                next_state, patch, delta = _run_safe_catalog_step(
                    updated,
                    step=step,
                    execute_safe_catalog_spl=execute_safe_catalog_spl,
                )
            updated = next_state
            collected_count += delta
            if purpose == "safe_catalog_query":
                template_id = _template_id_from_step(step)
                normalized_spl = None
                if isinstance(patch.get("payload"), dict):
                    normalized_spl = patch["payload"].get("normalized_spl")
                envelope = HookReplayEnvelope(
                    contract_version=HOOK_REPLAY_CONTRACT_VERSION,
                    hook_name="guided_safe_catalog_execute",
                    resource_plan_id=plan_id,
                    handoff_id=handoff_id,
                    handoff_version=handoff_version,
                    step_id=step_id,
                    operation_identity="guided_safe_catalog_execute",
                    input_fingerprint=build_safe_catalog_fingerprint(
                        template_id=template_id,
                        normalized_spl=str(normalized_spl) if normalized_spl else None,
                        selected_mcp_tool="guided_safe_catalog",
                    ),
                )
                return build_stored_hook_payload(
                    envelope,
                    hop_patch=patch,
                    connector_invoked=delta > 0,
                ) | {"collected_delta": delta}
            return {"hop_patch": patch, "collected_delta": delta}

        if not plan_id or not step_id:
            _execute_step()
            continue

        contract = operation_contract_for_step(step.model_dump())
        outcome, stored = run_idempotent_execution_step(
            resource_plan_id=plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            side_effecting=contract != "read_only_retryable",
            operation_contract=contract,
            lease_owner=str(updated.get("trace_id") or ""),
            execute=_execute_step,
            telemetry_state=updated,
        )
        if outcome == AcquireOutcome.REPLAY:
            updated = apply_idempotent_hop_to_state(updated, stored)
            collected_count += int(stored.get("collected_delta") or 0)
        elif outcome == AcquireOutcome.REQUIRES_RECONCILIATION:
            updated = apply_execution_uncertainty_to_state(updated, stored)

    return updated, collected_count
