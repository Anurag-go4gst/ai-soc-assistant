"""Hierarchy contracts for Resource Planner LangGraph specialists.

Specialists propose within disjoint ownership lanes; the composed
``ResourcePlan`` remains the policy authority. ``WorkBundle`` tasks are a
scheduling view over plan steps and cannot relax ``policy_checks`` or
blocked statuses without failing validation.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.planner.resource_plan import PlanStep, ResourcePlan, StepStatus

SpecialistId = Literal["skill", "mcp", "knowledge", "spl"]
SpecialistAuthority = Literal["advisory", "proposed_validated"]

_SPECIALIST_OWNERSHIP: dict[SpecialistId, frozenset[str]] = {
    "skill": frozenset({"route", "catalogue_tier", "skill_id", "use_case_id"}),
    "mcp": frozenset({"mcp_discovery", "mcp_search_hops", "tool_selection"}),
    "knowledge": frozenset({"atlas", "cve", "mitre", "rag", "reference_lookup"}),
    "spl": frozenset({"spl_compose", "spl_validation_inputs", "candidate_spl"}),
}


class DecisionRecord(BaseModel):
    record_id: str
    node: str
    authority: str
    decision_reason: str
    inputs_ref: list[str] = Field(default_factory=list)
    outputs_ref: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class SpecialistDelegation(BaseModel):
    delegation_id: str
    specialist_id: SpecialistId
    iteration: int = 0
    context_refs: list[str] = Field(default_factory=list)
    ownership_scope: list[str] = Field(default_factory=list)
    decision_reason: str = ""

    @model_validator(mode="after")
    def _ownership_within_lane(self) -> SpecialistDelegation:
        allowed = _SPECIALIST_OWNERSHIP[self.specialist_id]
        unknown = [item for item in self.ownership_scope if item not in allowed]
        if unknown:
            msg = f"specialist {self.specialist_id} cannot own {unknown}"
            raise ValueError(msg)
        return self


class SpecialistProposal(BaseModel):
    proposal_id: str
    purpose: str
    resource_id: str | None = None
    args_template: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SpecialistReport(BaseModel):
    specialist_id: SpecialistId
    delegation_id: str
    proposals: list[SpecialistProposal] = Field(default_factory=list)
    decision_reason: str
    authority: SpecialistAuthority = "advisory"
    warnings: list[str] = Field(default_factory=list)


class SkillSpecialistReport(SpecialistReport):
    specialist_id: Literal["skill"] = "skill"
    skill_id: str | None = None
    catalogue_tier: str | None = None


class McpSpecialistReport(SpecialistReport):
    specialist_id: Literal["mcp"] = "mcp"
    hop_count: int = 0


class KnowledgeSpecialistReport(SpecialistReport):
    specialist_id: Literal["knowledge"] = "knowledge"
    reference_domains: list[str] = Field(default_factory=list)


class SplSpecialistReport(SpecialistReport):
    specialist_id: Literal["spl"] = "spl"
    spl_source: str | None = None


class WorkTask(BaseModel):
    task_id: str
    step_id: str
    purpose: str
    resource_id: str
    args_template: dict[str, Any] = Field(default_factory=dict)
    policy_checks: list[str] = Field(default_factory=list)
    status: StepStatus = "planned"
    status_reason: str | None = None
    source_specialist: SpecialistId | None = None
    on_unavailable: str | None = None


class WorkBundle(BaseModel):
    bundle_id: str
    iteration: int = 0
    tasks: list[WorkTask] = Field(default_factory=list)
    source_plan: ResourcePlan
    merge_decision_reason: str = ""
    specialist_reports: list[SpecialistReport] = Field(default_factory=list)


class PlannerIteration(BaseModel):
    iteration: int
    delegations: list[SpecialistDelegation] = Field(default_factory=list)
    reports: list[SpecialistReport] = Field(default_factory=list)
    bundle: WorkBundle | None = None
    resource_plan: ResourcePlan
    decision_log: list[DecisionRecord] = Field(default_factory=list)


def new_decision_record_id() -> str:
    return f"dr:{uuid.uuid4().hex[:12]}"


def work_bundle_from_resource_plan(
    plan: ResourcePlan,
    *,
    bundle_id: str,
    iteration: int = 0,
) -> WorkBundle:
    """Materialize a WorkBundle with one task per composed ResourcePlan step."""
    tasks = [
        WorkTask(
            task_id=f"task:{step.step_id}",
            step_id=step.step_id,
            purpose=step.purpose,
            resource_id=step.resource_id,
            args_template=dict(step.args_template),
            policy_checks=list(step.policy_checks),
            status=step.status,
            status_reason=step.status_reason,
            on_unavailable=step.on_unavailable,
        )
        for step in plan.steps
    ]
    return WorkBundle(
        bundle_id=bundle_id,
        iteration=iteration,
        tasks=tasks,
        source_plan=plan,
    )


def materialize_resource_plan_from_bundle(bundle: WorkBundle) -> ResourcePlan:
    """Reconstruct a ResourcePlan from a bundle after policy parity validation."""
    violations = validate_bundle_policy_parity(bundle)
    if violations:
        raise ValueError(f"WorkBundle policy violations: {violations}")
    steps = [
        PlanStep(
            step_id=task.step_id,
            resource_id=task.resource_id,
            purpose=task.purpose,
            args_template=dict(task.args_template),
            policy_checks=list(task.policy_checks),
            status=task.status,
            status_reason=task.status_reason,
            on_unavailable=task.on_unavailable,
        )
        for task in bundle.tasks
    ]
    provenance = dict(bundle.source_plan.provenance)
    provenance["work_bundle_id"] = bundle.bundle_id
    return ResourcePlan(
        steps=steps,
        plan_source=bundle.source_plan.plan_source,
        provenance=provenance,
    )


def validate_bundle_policy_parity(bundle: WorkBundle) -> list[str]:
    """Return violations when a bundle bypasses the authoritative ResourcePlan."""
    violations: list[str] = []
    source_by_id = {step.step_id: step for step in bundle.source_plan.steps}
    task_by_id = {task.step_id: task for task in bundle.tasks}

    for step_id, source in source_by_id.items():
        task = task_by_id.get(step_id)
        if task is None:
            violations.append(f"missing_step:{step_id}")
            continue
        missing_checks = set(source.policy_checks) - set(task.policy_checks)
        if missing_checks:
            violations.append(f"policy_checks_removed:{step_id}:{sorted(missing_checks)}")
        if source.status == "blocked_policy" and task.status != "blocked_policy":
            violations.append(f"blocked_status_relaxed:{step_id}")
        if (
            "execution_eligible_false" in source.policy_checks
            and "execution_eligible_false" not in task.policy_checks
        ):
            violations.append(f"execution_eligibility_bypassed:{step_id}")

    for step_id in task_by_id:
        if step_id not in source_by_id:
            violations.append(f"unauthorized_step_added:{step_id}")

    return violations


def apply_specialist_reports(
    bundle: WorkBundle,
    reports: list[SpecialistReport],
) -> WorkBundle:
    """Merge advisory specialist output into an existing bundle.

  Specialists may enrich ``args_template`` on steps they own; they cannot add
  steps, remove policy checks, or relax blocked statuses.
    """
    task_by_step = {task.step_id: task.model_copy(deep=True) for task in bundle.tasks}
    merged_reports = list(bundle.specialist_reports)

    for report in reports:
        owner = report.specialist_id
        for proposal in report.proposals:
            matching = [
                task
                for task in task_by_step.values()
                if task.purpose == proposal.purpose
                and _specialist_for_purpose(task.purpose) == owner
            ]
            if not matching:
                continue
            task = matching[0]
            enriched_args = dict(task.args_template)
            enriched_args.update(proposal.args_template)
            task.args_template = enriched_args
            task.source_specialist = owner
        merged_reports.append(report)

    candidate = bundle.model_copy(
        update={
            "tasks": list(task_by_step.values()),
            "specialist_reports": merged_reports,
            "merge_decision_reason": "specialist_reports_merged",
        }
    )
    violations = validate_bundle_policy_parity(candidate)
    if violations:
        raise ValueError(f"specialist merge would bypass policy: {violations}")
    return candidate


def build_planner_iteration(
    *,
    iteration: int,
    resource_plan: ResourcePlan,
    delegations: list[SpecialistDelegation],
    reports: list[SpecialistReport] | None = None,
    bundle_id: str | None = None,
) -> PlannerIteration:
    """Assemble one RP loop iteration from plan + specialist fan-out/fan-in."""
    reports = list(reports or [])
    bundle = work_bundle_from_resource_plan(
        resource_plan,
        bundle_id=bundle_id or f"bundle:{iteration}",
        iteration=iteration,
    )
    if reports:
        bundle = apply_specialist_reports(bundle, reports)
    return PlannerIteration(
        iteration=iteration,
        delegations=delegations,
        reports=reports,
        bundle=bundle,
        resource_plan=materialize_resource_plan_from_bundle(bundle),
    )


def _specialist_for_purpose(purpose: str) -> SpecialistId | None:
    if purpose in {"knowledge_retrieval", "cve_lookup", "mitre_mapping"}:
        return "knowledge"
    if purpose == "spl_artifact":
        return "spl"
    if purpose == "mcp_execution":
        return "mcp"
    if purpose in {
        "evidence_collection",
        "grounding",
        "skill_routing",
        "catalogue_match",
    }:
        return "skill"
    return None
