"""Per-step hook idempotency for P0 MCP and guided safe-catalog execution paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    OperationReplayContract,
    apply_execution_uncertainty_to_state,
    operation_contract_for_mcp_tool,
    provenance_from_state,
    run_idempotent_execution_step,
)
from app.chat.hook_replay_contract import (
    HookReplayEnvelope,
    build_hook_operation_identity,
    build_stored_hook_payload,
    envelope_from_stored_result,
    rehydrate_mcp_execution_pair,
    rehydrate_safe_catalog_hop,
    stored_envelope_matches,
)
from app.orchestration.human_review import human_review, no_human_review


@dataclass(frozen=True)
class HookIdempotencyContext:
    resource_plan_id: str
    handoff_id: str | None
    handoff_version: int | None
    step_id: str
    lease_owner: str
    telemetry_state: dict[str, Any] | None = None


def resolve_hook_idempotency_context(state: dict[str, Any]) -> HookIdempotencyContext | None:
    resource_plan_id, handoff_version, handoff_id = provenance_from_state(state)
    trace_id = str(state.get("trace_id") or "").strip()
    if not resource_plan_id:
        if not trace_id:
            return None
        resource_plan_id = f"trace:{trace_id}"
    step_id = _resolve_mcp_hook_step_id(state)
    return HookIdempotencyContext(
        resource_plan_id=resource_plan_id,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        step_id=step_id,
        lease_owner=trace_id or resource_plan_id,
        telemetry_state=state,
    )


def _resolve_mcp_hook_step_id(state: dict[str, Any]) -> str:
    evidence_plan = state.get("evidence_plan")
    if isinstance(evidence_plan, dict):
        resource_plan = evidence_plan.get("resource_plan")
        if isinstance(resource_plan, dict):
            for step in resource_plan.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                if str(step.get("purpose") or "") == "mcp_execution":
                    step_id = str(step.get("step_id") or "").strip()
                    if step_id:
                        return step_id
    return "hook:mcp_execution"


def operation_contract_for_mcp_hook(tool_name: str) -> OperationReplayContract:
    return operation_contract_for_mcp_tool(tool_name)


def run_idempotent_hook(
    context: HookIdempotencyContext,
    envelope: HookReplayEnvelope,
    *,
    operation_contract: OperationReplayContract,
    side_effecting: bool,
    execute: Callable[[], dict[str, Any]],
) -> tuple[AcquireOutcome, dict[str, Any]]:
    operation = build_hook_operation_identity(envelope)

    def _wrapped_execute() -> dict[str, Any]:
        return execute()

    outcome, stored = run_idempotent_execution_step(
        resource_plan_id=context.resource_plan_id,
        step_id=context.step_id,
        operation=operation,
        handoff_id=context.handoff_id,
        handoff_version=context.handoff_version,
        side_effecting=side_effecting,
        lease_owner=context.lease_owner,
        operation_contract=operation_contract,
        telemetry_state=context.telemetry_state,
        execute=_wrapped_execute,
    )
    if outcome == AcquireOutcome.REPLAY and not stored_envelope_matches(envelope, stored):
        prior = envelope_from_stored_result(stored)
        return AcquireOutcome.REQUIRES_RECONCILIATION, {
            "reason": "hook_replay_fingerprint_mismatch",
            "expected": envelope.model_dump(),
            "stored": prior.model_dump() if prior else None,
        }
    return outcome, stored


def run_idempotent_mcp_execution_hook(
    context: HookIdempotencyContext,
    envelope: HookReplayEnvelope,
    *,
    selection: dict[str, Any],
    operation_contract: OperationReplayContract,
    execute_side_effect: Callable[[], tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[AcquireOutcome, dict[str, Any], dict[str, Any]]:
    """Wrap a side-effecting MCP execution; replay restores sanitized execution/review only."""

    connector_calls = {"count": 0}
    live_pair: dict[str, Any] = {}

    def _execute() -> dict[str, Any]:
        connector_calls["count"] += 1
        execution, review = execute_side_effect()
        live_pair["execution"] = execution
        live_pair["review"] = review
        return build_stored_hook_payload(
            envelope,
            execution=execution,
            human_review=review,
            connector_invoked=True,
        )

    outcome, stored = run_idempotent_hook(
        context,
        envelope,
        operation_contract=operation_contract,
        side_effecting=True,
        execute=_execute,
    )
    stored["_connector_invocation_count"] = connector_calls["count"]
    if outcome == AcquireOutcome.REPLAY:
        execution, review = rehydrate_mcp_execution_pair(stored, selection=selection)
        return outcome, execution, review
    if outcome == AcquireOutcome.REQUIRES_RECONCILIATION:
        execution, review = uncertainty_execution_review(stored)
        return outcome, execution, review
    if outcome == AcquireOutcome.IN_PROGRESS:
        execution, review = in_progress_execution_review(selection)
        return outcome, execution, review
    if outcome == AcquireOutcome.EXECUTE and isinstance(live_pair.get("execution"), dict):
        execution = {**live_pair["execution"], "execution_eligible": False}
        review = live_pair.get("review") if isinstance(live_pair.get("review"), dict) else no_human_review()
        return outcome, execution, review
    execution, review = rehydrate_mcp_execution_pair(stored, selection=selection)
    return outcome, execution, review


def run_idempotent_safe_catalog_hook(
    context: HookIdempotencyContext,
    envelope: HookReplayEnvelope,
    *,
    operation_contract: OperationReplayContract,
    execute_hop: Callable[[], tuple[dict[str, Any], dict[str, Any], int]],
) -> tuple[AcquireOutcome, dict[str, Any], int]:
    connector_calls = {"count": 0}

    def _execute() -> dict[str, Any]:
        connector_calls["count"] += 1
        next_state, patch, collected = execute_hop()
        _ = next_state
        return build_stored_hook_payload(
            envelope,
            hop_patch=patch,
            connector_invoked=connector_calls["count"] > 0,
        ) | {"collected_delta": collected}

    outcome, stored = run_idempotent_hook(
        context,
        envelope,
        operation_contract=operation_contract,
        side_effecting=operation_contract != "read_only_retryable",
        execute=_execute,
    )
    collected = int(stored.get("collected_delta") or 0)
    if outcome == AcquireOutcome.REPLAY:
        return outcome, rehydrate_safe_catalog_hop(stored), collected
    if outcome in {AcquireOutcome.REQUIRES_RECONCILIATION, AcquireOutcome.IN_PROGRESS}:
        return outcome, {"outcome_uncertain": True, "reason": stored.get("reason")}, collected
    return outcome, rehydrate_safe_catalog_hop(stored), collected


def uncertainty_execution_review(stored: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    review = human_review(
        "manual_reconciliation",
        "execution_outcome_uncertain",
        "soc_lead",
        ["reconcile_external_tool_state", "record_manual_outcome", "escalate_to_platform_admin"],
        "Execution outcome is uncertain; manually reconcile before retrying.",
        required=True,
    )
    execution = {
        "status": "requires_human_review",
        "execution_intent": "spl_search",
        "block_reason": "execution_outcome_uncertain",
        "outcome_uncertain": True,
        "tool_selection_status": "blocked_by_idempotency",
        "tool_selection_reason": str(stored.get("reason") or "execution_outcome_uncertain"),
        "selected_mcp_server": None,
        "selected_mcp_tool": None,
        "executed_spl": None,
        "result_count": 0,
        "results_preview": [],
        "duration_ms": 0,
        "evidence_source": "unavailable",
        "execution_status_label": "not_executed",
        "execution_eligible": False,
    }
    return execution, review


def in_progress_execution_review(selection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    review = human_review(
        "execution_in_progress",
        "execution_step_in_progress",
        "analyst",
        ["wait_for_execution", "escalate_to_platform_admin"],
        "Another worker is executing this hook; wait or escalate.",
        required=True,
    )
    execution = {
        **selection,
        "status": "requires_human_review",
        "block_reason": "execution_step_in_progress",
        "execution_eligible": False,
    }
    return execution, review


def apply_hook_uncertainty_to_state(state: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    return apply_execution_uncertainty_to_state(state, stored)
