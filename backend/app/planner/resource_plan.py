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

PlanSource = Literal["deterministic", "llm_proposed_validated"]

StepStatus = Literal[
    "planned",
    "executed",
    "fallback_taken",
    "skipped_unavailable",
    "blocked_policy",
    "not_run",
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
