"""Plan execution loop (T0.4) — dispatch stages from the composed plan and
record per-step outcomes with degrade-chain provenance.

Design constraints (plan rev 3):
- No stage logic moves. The executor calls the same pipeline node functions
  the legacy if/else dispatch called, selected by the same predicates, so
  behavior is parity-identical. Node callables and predicates are injected
  by the pipeline (`DispatchHooks`) — this module never imports the pipeline.
- MCP-purpose steps always flow through the execution-stage node, which owns
  `evaluate_mcp_execution` and the HIL gate; the executor never calls a
  connector and cannot bypass a gate.
- A step bound to a `blocked` registry resource is never dispatched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.config import settings
from app.planner.resource_registry import load_resource_registry

State = dict[str, Any]
Node = Callable[[State], State]


@dataclass
class DispatchHooks:
    uses_rag_only_path: Callable[[State], bool]
    uses_pre_mcp_rag: Callable[[State], bool]
    prepare_rag_only: Node
    rag_early: Node
    spl_source_resolve: Node
    workflow_spl: Node
    ensure_workflow_plan: Node
    execution: Node


def _resource_plan(state: State) -> dict[str, Any] | None:
    plan = state.get("evidence_plan")
    if isinstance(plan, Mapping):
        resource_plan = plan.get("resource_plan")
        if isinstance(resource_plan, Mapping) and resource_plan.get("steps"):
            return dict(resource_plan)
    return None


def has_composed_plan(state: State) -> bool:
    return _resource_plan(state) is not None


def _blocked_step_ids(state: State) -> set[str]:
    """Steps bound to blocked registry resources are refused before dispatch."""
    plan = _resource_plan(state) or {}
    registry = load_resource_registry()
    blocked: set[str] = set()
    for step in plan.get("steps", []):
        descriptor = registry.by_id(str(step.get("resource_id") or ""))
        if descriptor is not None and descriptor.availability == "blocked":
            blocked.add(str(step.get("step_id")))
    return blocked


def _preblocked_policy_step_ids(state: State) -> set[str]:
    """Steps already marked blocked_policy by composition (skill contract / plan)."""
    plan = _resource_plan(state) or {}
    blocked: set[str] = set()
    for step in plan.get("steps", []):
        step_id = str(step.get("step_id") or "")
        if str(step.get("status") or "") == "blocked_policy":
            blocked.add(step_id)
            continue
        checks = step.get("policy_checks") or []
        if any("blocked_by_skill_contract" in str(check) for check in checks):
            blocked.add(step_id)
    return blocked


def _dispatch_blocked_step_ids(state: State) -> set[str]:
    return _blocked_step_ids(state) | _preblocked_policy_step_ids(state)


def execute_plan_dispatch(state: State, hooks: DispatchHooks) -> State:
    """Walk the composed plan with the same control flow as the legacy
    dispatch block in `_build_live_chat_response_inner`."""
    blocked_steps = _dispatch_blocked_step_ids(state)
    if hooks.uses_rag_only_path(state):
        state = hooks.prepare_rag_only(state)
        if "rag" not in blocked_steps:
            state = hooks.rag_early(state)
    else:
        if "spl" not in blocked_steps:
            state = hooks.workflow_spl(state)
        if hooks.uses_pre_mcp_rag(state) and "rag" not in blocked_steps:
            state = hooks.rag_early(state)
        if "spl" not in blocked_steps:
            state = hooks.spl_source_resolve(state)
        # The execution stage always runs on this branch: it owns the MCP
        # gate, block reasons, and HIL even when no MCP step exists.
        if "spl" in blocked_steps and not state.get("workflow_plan"):
            state = hooks.ensure_workflow_plan(state)
        state = hooks.execution(state)
    return _annotate_blocked(state, blocked_steps)


def _annotate_blocked(state: State, blocked_steps: set[str]) -> State:
    if not blocked_steps:
        return state
    return annotate_step_statuses(state, only_steps=blocked_steps, force_status="blocked_policy")


def annotate_step_statuses(
    state: State,
    *,
    only_steps: set[str] | None = None,
    force_status: str | None = None,
) -> State:
    """Resolve each plan step's outcome from stage results already in state.

    Mutation is copy-on-write: a new evidence_plan dict is placed in state so
    downstream consumers (response assembly, lineage) see final statuses.
    """
    plan = _resource_plan(state)
    if plan is None:
        return state

    steps = [dict(step) for step in plan.get("steps", [])]
    for step in steps:
        step_id = str(step.get("step_id"))
        if only_steps is not None and step_id not in only_steps:
            continue
        if force_status is not None:
            step["status"] = force_status
            step["status_reason"] = "registry_resource_blocked"
            continue
        status, reason = _resolve_status(step, state)
        step["status"] = status
        if reason:
            step["status_reason"] = reason
        if str(step.get("purpose") or "") == "mcp_execution":
            step["mcp_step_metadata"] = _mcp_step_metadata(step, state)

    evidence_plan = dict(state.get("evidence_plan") or {})
    evidence_plan["resource_plan"] = {**plan, "steps": steps}
    return {**state, "evidence_plan": evidence_plan}


def _resolve_status(step: Mapping[str, Any], state: State) -> tuple[str, str | None]:
    purpose = str(step.get("purpose") or "")
    if purpose == "knowledge_retrieval":
        retrieval = state.get("soc_kb_retrieval")
        if isinstance(retrieval, Mapping):
            status = str(retrieval.get("retrieval_status") or "")
            if status in {"ok", "retrieved", "partial"}:
                return "executed", None
            return "skipped_unavailable", f"retrieval_status={status or 'unknown'}"
        return "not_run", None

    if purpose == "spl_artifact":
        validation = state.get("spl_validation")
        if not isinstance(validation, Mapping):
            return "not_run", None
        provider_reason = str(validation.get("candidate_provider_reason") or "")
        if provider_reason == "spl_template_missing" and step.get("on_unavailable"):
            return "fallback_taken", f"spl_template_missing -> {step.get('on_unavailable')}"
        if provider_reason == "spl_template_missing":
            return "fallback_taken", "spl_template_missing -> lab_draft_preview"
        return "executed", None

    if purpose == "mcp_execution":
        execution = state.get("execution")
        if not isinstance(execution, Mapping):
            return "not_run", None
        status = str(execution.get("status") or "")
        if status == "executed":
            return "executed", None
        if status in {"blocked", "requires_human_review"}:
            return "blocked_policy", str(execution.get("block_reason") or status)
        return "skipped_unavailable", f"execution_status={status or 'unknown'}"

    if purpose == "mitre_mapping":
        decision = state.get("mitre_decision")
        if isinstance(decision, Mapping):
            return "executed", None
        return "not_run", None

    return "planned", None


def _mcp_step_metadata(step: Mapping[str, Any], state: State) -> dict[str, Any]:
    """Structured MCP posture for debug/RunContract projection (no execution)."""
    execution = state.get("execution") if isinstance(state.get("execution"), dict) else {}
    spl_validation = state.get("spl_validation") if isinstance(state.get("spl_validation"), dict) else {}
    evidence_plan = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}

    secondary: list[str] = []
    if not settings.mcp_global_execution_enabled:
        secondary.append("mcp_global_execution_disabled")
    if str(step.get("status") or "") == "blocked_policy":
        secondary.append(str(step.get("status_reason") or "blocked_policy"))
    if evidence_plan.get("mcp_allowed") is not True:
        secondary.append("mcp_not_allowed_by_evidence_plan")
    if spl_validation and not spl_validation.get("approved"):
        secondary.append("spl_not_approved")
    if execution.get("requires_human_review"):
        secondary.append("hil_required")

    exec_status = str(execution.get("status") or step.get("status") or "planned")
    primary = str(
        execution.get("block_reason")
        or step.get("status_reason")
        or exec_status
    )
    return {
        "status": exec_status if exec_status in {"planned", "blocked_policy", "skipped", "executed", "failed"} else (
            "blocked_policy" if exec_status in {"blocked", "requires_human_review"} else exec_status
        ),
        "primary_reason": primary,
        "secondary_reasons": secondary,
        "selected_tool": execution.get("selected_mcp_tool"),
        "execution_authorized": exec_status == "executed",
    }
