"""Hierarchy contracts for Resource Planner LangGraph specialists.

Specialists propose within disjoint ownership lanes; the composed
``ResourcePlan`` remains the policy authority. ``WorkBundle`` tasks are a
scheduling view over plan steps and cannot relax ``policy_checks`` or
blocked statuses without failing validation.
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.planner.resource_plan import PlanStep, ResourcePlan, StepStatus

SpecialistId = Literal["skill", "mcp", "knowledge", "spl"]
SpecialistAuthority = Literal["advisory", "proposed_validated"]
McpRegistryMode = Literal["mock", "registry", "unavailable"]
McpExecutionPosture = Literal[
    "not_needed",
    "discovery_only",
    "gate_required",
    "blocked_by_plan",
    "unavailable",
]
SplSource = Literal[
    "not_needed",
    "governed_template",
    "review_only_fallback",
    "blocked",
    "unavailable",
]
SplSlotBindingStatus = Literal[
    "not_required",
    "ready",
    "missing_required_slots",
    "unknown",
]
SplCandidateSource = Literal[
    "governed_template",
    "deterministic_fallback",
    "review_only_fallback",
    "lab_draft_preview",
    "llm_review_only",
]

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_FORBIDDEN_PROPOSAL_KEYS = frozenset(
    {
        "candidate_spl",
        "normalized_spl",
        "validator_approved",
        "validation_approved",
        "approved",
        "execution_enabled",
        "execution_eligible",
        "policy_checks",
        "status",
        "status_reason",
        "endpoint",
        "url",
        "auth",
        "auth_mode",
        "credentials",
        "credential",
        "password",
        "secret",
        "token",
        "api_key",
        "query",
        "raw_query",
        "user_query",
        "prompt",
        "raw_prompt",
        "rag",
        "rag_text",
        "rag_chunks",
    }
)
_FORBIDDEN_PROPOSAL_KEY_FRAGMENTS = (
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "endpoint",
    "prompt",
    "raw_query",
    "rag_text",
    "rag_chunk",
)

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
    args_template: dict[str, Any] = Field(default_factory=dict, max_length=16)
    rationale: str = Field(default="", max_length=240)


class SpecialistReport(BaseModel):
    specialist_id: SpecialistId
    delegation_id: str
    proposals: list[SpecialistProposal] = Field(default_factory=list, max_length=16)
    decision_reason: str = Field(max_length=160)
    authority: SpecialistAuthority = "advisory"
    warnings: list[str] = Field(default_factory=list, max_length=16)


class SkillSpecialistReport(SpecialistReport):
    specialist_id: Literal["skill"] = "skill"
    skill_id: str | None = None
    catalogue_tier: str | None = None


class McpSpecialistReport(SpecialistReport):
    specialist_id: Literal["mcp"] = "mcp"
    plan_needs_mcp: bool = False
    plan_mcp_allowed: bool = False
    discovery_allowed: bool = False
    planned_hop_count: int = Field(default=0, ge=0, le=32)
    hop_count: int = Field(default=0, ge=0, le=32)
    registry_mode: McpRegistryMode = "unavailable"
    global_execution_enabled: bool = False
    configured_server_count: int = Field(default=0, ge=0, le=1024)
    available_server_count: int = Field(default=0, ge=0, le=1024)
    candidate_server_ids: list[str] = Field(default_factory=list, max_length=16)
    candidate_tool_names: list[str] = Field(default_factory=list, max_length=16)
    execution_posture: McpExecutionPosture = "not_needed"
    requires_execution_gate: bool = False
    blockers: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("candidate_server_ids", "candidate_tool_names", "blockers")
    @classmethod
    def _bounded_safe_identifiers(cls, values: list[str]) -> list[str]:
        if any(not _SAFE_IDENTIFIER_RE.fullmatch(value) for value in values):
            raise ValueError("MCP report identifiers must be bounded safe identifiers")
        return values

    @model_validator(mode="after")
    def _synchronize_hop_counts(self) -> McpSpecialistReport:
        if self.planned_hop_count and self.hop_count and self.planned_hop_count != self.hop_count:
            raise ValueError("planned_hop_count and compatibility hop_count disagree")
        if self.planned_hop_count == 0 and self.hop_count:
            self.planned_hop_count = self.hop_count
        elif self.hop_count == 0 and self.planned_hop_count:
            self.hop_count = self.planned_hop_count
        if self.available_server_count > self.configured_server_count:
            raise ValueError("available_server_count cannot exceed configured_server_count")
        return self


class KnowledgeSpecialistReport(SpecialistReport):
    specialist_id: Literal["knowledge"] = "knowledge"
    reference_domains: list[str] = Field(default_factory=list)


class SplSpecialistReport(SpecialistReport):
    specialist_id: Literal["spl"] = "spl"
    plan_needs_spl: bool = False
    plan_spl_allowed: bool = False
    planned_resource_id: str | None = Field(default=None, max_length=128)
    template_id: str | None = Field(default=None, max_length=128)
    template_status: Literal[
        "active",
        "sample",
        "planned",
        "missing",
        "unavailable",
        "unknown",
        "sop_only",
    ] | None = None
    template_production_executable: bool | None = None
    fallback_resource_id: str | None = Field(default=None, max_length=128)
    candidate_source_options: list[SplCandidateSource] = Field(default_factory=list, max_length=8)
    spl_source: SplSource = "not_needed"
    slot_binding_status: SplSlotBindingStatus = "not_required"
    missing_required_slots: list[str] = Field(default_factory=list, max_length=16)
    validation_required: bool = False
    execution_eligible: Literal[False] = False
    blockers: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("missing_required_slots", "blockers")
    @classmethod
    def _bounded_safe_identifiers(cls, values: list[str]) -> list[str]:
        if any(not _SAFE_IDENTIFIER_RE.fullmatch(value) for value in values):
            raise ValueError("SPL report identifiers must be bounded safe identifiers")
        return values


SpecialistReportPayload = Annotated[
    SkillSpecialistReport
    | McpSpecialistReport
    | KnowledgeSpecialistReport
    | SplSpecialistReport,
    Field(discriminator="specialist_id"),
]


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
    specialist_reports: list[SpecialistReportPayload] = Field(default_factory=list)


class PlannerIteration(BaseModel):
    iteration: int
    delegations: list[SpecialistDelegation] = Field(default_factory=list)
    reports: list[SpecialistReportPayload] = Field(default_factory=list)
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

    Specialists may fill blank ``args_template`` fields on existing steps they
    own; they cannot add steps, overwrite authority, remove policy checks, or
    relax blocked statuses.
    """
    task_by_step = {task.step_id: task.model_copy(deep=True) for task in bundle.tasks}
    merged_reports = list(bundle.specialist_reports)

    for report in reports:
        owner = report.specialist_id
        for proposal in report.proposals:
            purpose_owner = _specialist_for_purpose(proposal.purpose)
            if purpose_owner != owner:
                raise ValueError(
                    "cross-lane specialist proposal: "
                    f"{owner} cannot propose for {proposal.purpose}"
                )
            forbidden = _forbidden_proposal_fields(proposal.args_template)
            if forbidden:
                raise ValueError(
                    f"forbidden specialist proposal field: {sorted(forbidden)}"
                )
            matching = [
                task
                for task in task_by_step.values()
                if task.purpose == proposal.purpose
                and (proposal.resource_id is None or task.resource_id == proposal.resource_id)
            ]
            if not matching:
                raise ValueError(
                    "no existing specialist proposal target: "
                    f"{proposal.proposal_id}"
                )
            if len(matching) != 1:
                raise ValueError(
                    "ambiguous specialist proposal target: "
                    f"{proposal.proposal_id}"
                )
            task = matching[0]
            enriched_args = dict(task.args_template)
            changed = False
            for key, value in proposal.args_template.items():
                existing = enriched_args.get(key)
                if not _is_blank(existing):
                    if existing != value:
                        raise ValueError(
                            "non-blank specialist proposal target: "
                            f"{task.step_id}.{key}"
                        )
                    continue
                enriched_args[key] = value
                changed = True
            task.args_template = enriched_args
            if changed:
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
    if purpose in {"mcp_execution", "mcp_discovery"}:
        return "mcp"
    if purpose in {
        "evidence_collection",
        "grounding",
        "skill_routing",
        "catalogue_match",
    }:
        return "skill"
    return None


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _forbidden_proposal_fields(payload: dict[str, Any]) -> set[str]:
    forbidden: set[str] = set()
    for key, value in payload.items():
        normalized = str(key).strip().lower()
        if normalized in _FORBIDDEN_PROPOSAL_KEYS or any(
            fragment in normalized for fragment in _FORBIDDEN_PROPOSAL_KEY_FRAGMENTS
        ):
            forbidden.add(normalized)
        if isinstance(value, dict):
            forbidden.update(_forbidden_proposal_fields(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    forbidden.update(_forbidden_proposal_fields(item))
    return forbidden
