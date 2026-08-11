"""ResourcePlan contract (T0.2) — ordered plan steps with degrade chains.

A ResourcePlan is the composed form of an EvidencePlan: instead of booleans
("needs_rag"), an ordered list of steps referencing resource-registry ids,
each with an optional fallback step. The legacy booleans remain the wire
contract for existing consumers; `project_booleans` derives them from a plan
so parity is testable field-by-field.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Runtime import: pydantic resolves `PlanStep.execution` against this model.
# `resource_plan_execution` never imports this module at runtime, so there is
# no cycle.
from app.planner.resource_plan_execution import StepExecutionSpec

PlanSource = Literal["deterministic", "llm_proposed_validated"]

StepStatus = Literal[
    "planned",
    "executed",
    "fallback_taken",
    "skipped_unavailable",
    "blocked_policy",
    "not_run",
    "not_onboarded",
]

# Step purpose → the legacy boolean it projects onto.
_PURPOSE_BOOLEANS: dict[str, str] = {
    "knowledge_retrieval": "needs_rag",
    "spl_artifact": "needs_spl",
    "mcp_execution": "needs_mcp",
    "mitre_mapping": "needs_mitre",
}


class PlanStep(BaseModel):
    step_id: str
    resource_id: str
    purpose: str
    args_template: dict[str, Any] = Field(default_factory=dict)
    on_unavailable: str | None = None
    policy_checks: list[str] = Field(default_factory=list)
    status: StepStatus = "planned"
    status_reason: str | None = None
    # C1-E1: optional execution semantics (dependencies, parallel group,
    # evidence keys, fallback, attempts). `None` means "derive the defaults",
    # which reproduce the current fixed schedule. Rules live in
    # `app.planner.resource_plan_execution`; nothing consumes this for
    # scheduling until the C1-E4 wiring behind its default-false flag.
    execution: "StepExecutionSpec | None" = None


class ResourcePlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    plan_source: PlanSource = "deterministic"
    provenance: dict[str, Any] = Field(default_factory=dict)

    def step_by_id(self, step_id: str) -> PlanStep | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def summary(self) -> dict[str, Any]:
        """Compact trace surface: ids + sources only, no args."""
        return {
            "plan_source": self.plan_source,
            "steps": [
                {
                    "step_id": step.step_id,
                    "resource_id": step.resource_id,
                    "purpose": step.purpose,
                    "status": step.status,
                    "on_unavailable": step.on_unavailable,
                }
                for step in self.steps
            ],
        }


# --- ResourcePlanV2 (O5a contract) --------------------------------------------
# Additive dependency/failover fields for the multi-call scheduler/reconcile
# loop (plan A.6). V1 PlanStep/ResourcePlan remain the live wire contract; V2 is
# not wired into the pipeline until O5b/O5c (behind a default-off flag).

# Each failover edge targets another step_id or a terminal policy.
FailoverTarget = str  # step_id | "terminal" | "hil"


class PlanStepV2(BaseModel):
    step_id: str
    resource_id: str
    purpose: str
    args_template: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    activation_condition: Literal[
        "always", "previous_ok", "previous_empty", "evidence_key_missing"
    ] = "always"
    requires_evidence_keys: list[str] = Field(default_factory=list)
    produces_evidence_keys: list[str] = Field(default_factory=list)
    resource_capability: str | None = None
    resource_alternatives: list[str] = Field(default_factory=list)
    on_unavailable: FailoverTarget = "hil"
    on_empty: FailoverTarget = "terminal"
    on_error: FailoverTarget = "hil"
    on_timeout: FailoverTarget = "hil"
    on_denied: FailoverTarget = "hil"
    policy_checks: list[str] = Field(default_factory=list)
    max_attempts: int = 1
    status: StepStatus = "planned"
    status_reason: str | None = None


class ResourcePlanV2(BaseModel):
    schema_version: str = "2"
    recipe_id: str = "single_search"
    steps: list[PlanStepV2] = Field(default_factory=list)
    plan_source: PlanSource = "deterministic"
    provenance: dict[str, Any] = Field(default_factory=dict)

    def step_by_id(self, step_id: str) -> PlanStepV2 | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


def project_booleans(plan: ResourcePlan) -> dict[str, bool]:
    """Derive the legacy `needs_*` EvidencePlan booleans from a composed plan.

    Only the four needs_* booleans are projected. `spl_allowed`/`mcp_allowed`
    are policy permissions owned by the EvidencePlan branch logic (they can
    legitimately diverge from needs_*, e.g. SPL allowed but not needed) and
    are carried untouched.
    """
    projected = {name: False for name in _PURPOSE_BOOLEANS.values()}
    for step in plan.steps:
        boolean = _PURPOSE_BOOLEANS.get(step.purpose)
        if boolean is not None:
            projected[boolean] = True
    return projected
