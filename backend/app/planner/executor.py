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

from app.chat.contracts.pipeline_dispatch import imperative_hook_schedule_from_state
from app.config import settings
from app.planner.resource_registry import load_resource_registry

State = dict[str, Any]

_MCP_POSTURE_STATUSES = frozenset({"planned", "blocked_policy", "skipped", "executed", "failed"})


def normalize_mcp_posture_status(raw_status: str | None) -> str:
    """Map execution/plan statuses to the MCP posture vocabulary."""
    status = str(raw_status or "planned").strip() or "planned"
    if status in _MCP_POSTURE_STATUSES:
        return status
    if status in {"blocked", "requires_human_review"}:
        return "blocked_policy"
    if status in {"skipped_unavailable", "not_run"}:
        return "skipped"
    return "blocked_policy"


def _preserved_block_reason(step: Mapping[str, Any]) -> str:
    existing = str(step.get("status_reason") or "").strip()
    if existing:
        return existing
    checks = [str(item) for item in step.get("policy_checks") or []]
    if any("blocked_by_skill_contract" in check for check in checks):
        return "skill_contract"
    if any("mcp_not_allowed_by_evidence_plan" in check for check in checks):
        return "mcp_not_allowed_by_evidence_plan"
    return "blocked_policy"


def mcp_composed_block_reason(step: Mapping[str, Any]) -> str | None:
    """Composition-time MCP veto; wins over execution-gate block reasons."""
    checks = [str(item) for item in step.get("policy_checks") or []]
    if any("blocked_by_skill_contract" in check for check in checks):
        return _preserved_block_reason(step)
    if str(step.get("status_reason") or "") == "skill_contract":
        return "skill_contract"
    if any("mcp_not_allowed_by_evidence_plan" in check for check in checks):
        return "mcp_not_allowed_by_evidence_plan"
    if str(step.get("status") or "") == "blocked_policy":
        preserved = _preserved_block_reason(step)
        if preserved not in {"", "blocked_policy"}:
            return preserved
    return None


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


_DISPATCHABLE_PURPOSES = frozenset({"knowledge_retrieval", "spl_artifact", "mcp_execution"})


@dataclass(frozen=True)
class PlanStepWalkResult:
  """Ordered ResourcePlan walk: dispatchable steps plus skipped/blocked lineage."""

  step_walk_order: list[str]
  steps_in_order: list[dict[str, Any]]
  dispatchable_step_ids: list[str]
  skipped_step_reasons: dict[str, str]
  blocked_step_ids: set[str]


def walk_plan_steps(state: State) -> PlanStepWalkResult | None:
  """Read composed ResourcePlan order; never classify intent or change route."""
  plan = _resource_plan(state)
  if plan is None:
    return None

  registry_blocked = _blocked_step_ids(state)
  preblocked = _preblocked_policy_step_ids(state)
  blocked = registry_blocked | preblocked

  steps_in_order = [dict(step) for step in plan.get("steps", [])]
  step_walk_order = [str(step.get("step_id") or "") for step in steps_in_order]
  dispatchable: list[str] = []
  skipped: dict[str, str] = {}

  for step in steps_in_order:
    step_id = str(step.get("step_id") or "")
    if step_id in registry_blocked:
      skipped[step_id] = "registry_resource_blocked"
      continue
    if step_id in preblocked:
      skipped[step_id] = _preserved_block_reason(step)
      continue
    purpose = str(step.get("purpose") or "")
    if purpose in _DISPATCHABLE_PURPOSES:
      dispatchable.append(step_id)

  return PlanStepWalkResult(
    step_walk_order=step_walk_order,
    steps_in_order=steps_in_order,
    dispatchable_step_ids=dispatchable,
    skipped_step_reasons=skipped,
    blocked_step_ids=blocked,
  )


def derive_dispatch_booleans_from_plan(state: State) -> dict[str, Any]:
  """Derive dispatch predicates from EvidencePlan + ResourcePlan projection."""
  evidence = state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else {}
  planning = state.get("planning_decision") if isinstance(state.get("planning_decision"), dict) else {}
  path_type = planning.get("path_type")

  resource = _resource_plan(state)
  if resource is not None:
    from app.planner.resource_plan import ResourcePlan, project_booleans

    projected = project_booleans(ResourcePlan.model_validate(resource))
  else:
    projected = {
      "needs_rag": bool(evidence.get("needs_rag")),
      "needs_spl": bool(evidence.get("needs_spl")),
      "needs_mcp": bool(evidence.get("needs_mcp")),
      "needs_mitre": bool(evidence.get("needs_mitre")),
    }

  rag_phase = str(evidence.get("rag_phase") or "")
  answer_mode = str(evidence.get("answer_mode") or "")

  uses_pre_mcp_rag = bool(projected.get("needs_rag")) and rag_phase == "pre_mcp"
  uses_rag_only_path = path_type == "guided_investigation" or answer_mode in {
    "rag_only",
    "guided_investigation",
  } or path_type == "generic_soc_guidance"
  if not settings.control_plane_enabled:
    uses_rag_only_path = False
    uses_pre_mcp_rag = False

  return {
    "uses_rag_only_path": uses_rag_only_path,
    "uses_pre_mcp_rag": uses_pre_mcp_rag,
    "projected_needs": projected,
  }


def build_step_walk_dispatch_schedule(
  state: State,
  walk: PlanStepWalkResult,
  hooks: DispatchHooks,
) -> list[str]:
  """Derive the stage-node schedule from a walked plan.

  Composition order (e.g. pre_mcp RAG before SPL in the ResourcePlan) is
  preserved in ``walk.step_walk_order`` for lineage, but dispatch still follows
  the legacy stage pipeline until parity proves a safe reorder.
  """
  return _legacy_predicate_dispatch_schedule(state, hooks, walk.blocked_step_ids)


def _legacy_predicate_dispatch_schedule(
  state: State,
  hooks: DispatchHooks,
  blocked_steps: set[str],
) -> list[str]:
  v2_schedule = imperative_hook_schedule_from_state(state)
  if v2_schedule is not None:
    if "spl" in blocked_steps:
      v2_schedule = [h for h in v2_schedule if h not in {"workflow_spl", "spl_source_resolve"}]
    if "rag" in blocked_steps:
      v2_schedule = [h for h in v2_schedule if h not in {"prepare_rag_only", "rag_early"}]
    if not v2_schedule and "spl" in blocked_steps and not state.get("workflow_plan"):
      return ["ensure_workflow_plan"]
    rag_only = bool(
      v2_schedule
      and "workflow_spl" not in v2_schedule
      and all(h in {"prepare_rag_only", "rag_early"} for h in v2_schedule)
    )
    if not rag_only and "execution" not in v2_schedule:
      v2_schedule = [*v2_schedule, "execution"]
    return v2_schedule

  if hooks.uses_rag_only_path(state):
    schedule = ["prepare_rag_only"]
    if "rag" not in blocked_steps:
      schedule.append("rag_early")
    return schedule

  schedule: list[str] = []
  if "spl" not in blocked_steps:
    schedule.append("workflow_spl")
  if hooks.uses_pre_mcp_rag(state) and "rag" not in blocked_steps:
    schedule.append("rag_early")
  if "spl" not in blocked_steps:
    schedule.append("spl_source_resolve")
  if "spl" in blocked_steps and not state.get("workflow_plan"):
    schedule.append("ensure_workflow_plan")
  schedule.append("execution")
  return schedule


_HOOK_BY_NAME = {
  "prepare_rag_only": lambda hooks: hooks.prepare_rag_only,
  "rag_early": lambda hooks: hooks.rag_early,
  "spl_source_resolve": lambda hooks: hooks.spl_source_resolve,
  "workflow_spl": lambda hooks: hooks.workflow_spl,
  "ensure_workflow_plan": lambda hooks: hooks.ensure_workflow_plan,
  "execution": lambda hooks: hooks.execution,
}


def _run_dispatch_schedule(state: State, hooks: DispatchHooks, schedule: list[str]) -> State:
  for hook_name in schedule:
    node = _HOOK_BY_NAME[hook_name](hooks)
    state = node(state)
  return state


def build_plan_dispatch_trace(
  state: State,
  *,
  walk: PlanStepWalkResult | None,
  schedule: list[str],
  hooks: DispatchHooks,
  dispatch_source: str,
) -> dict[str, Any]:
  derived = derive_dispatch_booleans_from_plan(state)
  trace: dict[str, Any] = {
    "dispatch_source": dispatch_source,
    "dispatch_schedule": schedule,
    "dispatch_parity_projection": derived,
  }
  if walk is not None:
    trace["step_walk_order"] = list(walk.step_walk_order)
    trace["skipped_step_reasons"] = dict(walk.skipped_step_reasons)
    trace["predicate_parity"] = {
      "uses_rag_only_path": hooks.uses_rag_only_path(state) == derived.get("uses_rag_only_path"),
      "uses_pre_mcp_rag": hooks.uses_pre_mcp_rag(state) == derived.get("uses_pre_mcp_rag"),
    }
  return trace


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
    """Dispatch via ResourcePlan step-walk; predicates remain parity-checked."""
    walk = walk_plan_steps(state)
    blocked_steps = walk.blocked_step_ids if walk is not None else _dispatch_blocked_step_ids(state)
    if walk is not None:
        schedule = build_step_walk_dispatch_schedule(state, walk, hooks)
        dispatch_source = "resource_plan_step_walk"
    else:
        schedule = _legacy_predicate_dispatch_schedule(state, hooks, blocked_steps)
        dispatch_source = "legacy_predicate"
    trace = build_plan_dispatch_trace(
        state,
        walk=walk,
        schedule=schedule,
        hooks=hooks,
        dispatch_source=dispatch_source,
    )
    state = {**state, "plan_dispatch_trace": trace}
    state = _run_dispatch_schedule(state, hooks, schedule)
    return _annotate_blocked(state, blocked_steps)


def _annotate_blocked(state: State, blocked_steps: set[str]) -> State:
    if not blocked_steps:
        return state
    registry_blocked = _blocked_step_ids(state)
    return annotate_step_statuses(
        state,
        only_steps=blocked_steps,
        force_status="blocked_policy",
        registry_blocked_steps=registry_blocked,
    )


def annotate_step_statuses(
    state: State,
    *,
    only_steps: set[str] | None = None,
    force_status: str | None = None,
    registry_blocked_steps: set[str] | None = None,
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
            if step_id in (registry_blocked_steps or set()):
                step["status_reason"] = "registry_resource_blocked"
            else:
                step["status_reason"] = _preserved_block_reason(step)
            if str(step.get("purpose") or "") == "mcp_execution":
                step["mcp_step_metadata"] = _mcp_step_metadata(step, state)
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
        composed_reason = mcp_composed_block_reason(step)
        if composed_reason is not None:
            return "blocked_policy", composed_reason
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
    exec_block = str(execution.get("block_reason") or "").strip()
    composed_reason = mcp_composed_block_reason(step)
    if composed_reason is not None:
        primary = composed_reason
        if exec_block and exec_block != composed_reason:
            secondary.append(exec_block)
    else:
        primary = str(exec_block or step.get("status_reason") or exec_status)
    if composed_reason is not None:
        posture_status = str(step.get("status") or "blocked_policy")
        execution_authorized = False
    else:
        posture_status = exec_status
        execution_authorized = exec_status == "executed"
    return {
        "status": normalize_mcp_posture_status(posture_status),
        "primary_reason": primary,
        "secondary_reasons": secondary,
        "selected_tool": execution.get("selected_mcp_tool"),
        "execution_authorized": execution_authorized,
    }
