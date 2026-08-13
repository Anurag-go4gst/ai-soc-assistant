"""Deterministic lifecycle applicability resolver (Plan 5 C0.1).

`PhaseRegistry` says which lifecycle phases exist. `PhasePolicy` decides which
of them apply to **this** request, from deterministic inputs only:

    (ResolvedQueryContract, committed ResourcePlan, explicit runtime facts)
        -> applicable phases + ordering constraints + a reason per phase

Boundaries, all asserted by tests:

- **Pure.** No settings read, no state read, no I/O, no model call. Anything the
  answer depends on is passed in explicitly (`PhasePolicyInputs`), so the same
  inputs always give the same answer and a caller cannot smuggle in a flag.
- **Mandatory when applicable, never universal.** A knowledge-only turn carries
  no SPL chain; a turn with no reference IDs carries no `reference_finalize`; a
  clarification-only turn carries no evidence lifecycle at all. Applicability is
  a predicate, never a heuristic and never a count.
- **PhasePolicy alone decides.** The ResourcePlan is an *input* to applicability
  — it says what work exists — but no plan content, advisory or specialist
  report can mark an applicable phase inapplicable. Every predicate is
  monotone in the direction of safety: plan evidence can only *add* a phase,
  and a required capability alone is enough to keep one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.planner.phase_registry import (
    PHASE_REGISTRY,
    ordering_constraints,
    phase_spec,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.chat.contracts.resolved_query import ResolvedQueryContract
    from app.planner.resource_plan import ResourcePlan

SCHEMA_VERSION = "phase_policy_v1"

# Step statuses that mean the step will not run.
_INERT_STATUSES = frozenset({"blocked_policy", "not_onboarded", "skipped_unavailable"})

# Answer goals that require the reference taxonomy finalizer.
_REFERENCE_GOALS = frozenset({"reference_lookup", "reference_explanation"})
_MITRE_GOALS = frozenset({"mitre_mapping", "mitre_explanation"})


@dataclass(frozen=True)
class PhasePolicyInputs:
    """Everything outside the contract and the plan the verdict depends on.

    Passed explicitly so the resolver stays pure. `pre_spl_discovery_enabled`
    is the caller's already-read `ai_soc_pipeline_dispatch_v2_enabled`; the
    resolver never reads settings itself.
    """

    has_workflow_plan: bool = False
    pre_spl_discovery_enabled: bool = False


@dataclass(frozen=True)
class PhasePolicyResolution:
    """Which phases apply to this run, and why."""

    applicable: frozenset[str]
    mandatory: frozenset[str]
    ordering: tuple[tuple[str, str], ...]
    reasons: tuple[tuple[str, str], ...]

    def reason_for(self, phase: str) -> str | None:
        for name, reason in self.reasons:
            if name == phase:
                return reason
        return None


def _live_purposes(plan: "ResourcePlan | None") -> frozenset[str]:
    if plan is None:
        return frozenset()
    return frozenset(
        step.purpose for step in plan.steps if step.status not in _INERT_STATUSES
    )


def _blocked_purposes(plan: "ResourcePlan | None") -> frozenset[str]:
    if plan is None:
        return frozenset()
    return frozenset(step.purpose for step in plan.steps if step.status in _INERT_STATUSES)


def resolve_phase_policy(
    contract: "ResolvedQueryContract",
    plan: "ResourcePlan | None" = None,
    inputs: PhasePolicyInputs | None = None,
) -> PhasePolicyResolution:
    """Resolve the applicable lifecycle for one run. Pure and total."""
    inputs = inputs or PhasePolicyInputs()
    live = _live_purposes(plan)
    blocked = _blocked_purposes(plan)
    required = frozenset(contract.required_capabilities)
    prohibited = frozenset(contract.prohibited_capabilities)
    evidence = frozenset(str(item) for item in contract.evidence_requirements)

    reasons: dict[str, str] = {}

    def mark(phase: str, reason: str) -> None:
        # Resolving through the registry keeps the catalog closed: a typo here
        # raises rather than inventing a phase.
        reasons.setdefault(phase_spec(phase).name, reason)

    # A clarification-only turn produces no evidence lifecycle at all.
    if contract.clarification_required or contract.ambiguity_state in {
        "clarification_required",
        "policy_blocked",
    }:
        return PhasePolicyResolution(
            applicable=frozenset(),
            mandatory=frozenset(),
            ordering=(),
            reasons=(("__none__", f"no lifecycle: {contract.ambiguity_state}"),),
        )

    spl_prohibited = "spl" in prohibited
    mcp_prohibited = "mcp" in prohibited

    spl_required = not spl_prohibited and (
        "spl_artifact" in live or "spl" in required or "candidate_spl" in evidence
    )
    spl_blocked = "spl_artifact" in blocked and not spl_required
    knowledge_required = (
        "knowledge_retrieval" in live
        or "evidence_collection" in live
        or "soc_kb_retrieval" in evidence
    )
    mcp_required = not mcp_prohibited and ("mcp_execution" in live or "mcp" in required)

    if spl_required:
        mark("workflow_spl", "spl artifact required")
        # Validation and source resolution are not optional consequences of
        # producing SPL — they are what makes it safe to consume.
        mark("spl_postprocessor", "spl candidate must be deterministically validated")
        mark("spl_source_resolve", "spl candidate carries source slots")

    if knowledge_required:
        mark("rag_early", "knowledge evidence required")
        if not spl_required and not mcp_required:
            mark("prepare_rag_only", "knowledge-only lane")

    if spl_required and inputs.pre_spl_discovery_enabled:
        mark("pre_spl_mcp_discovery", "bounded pre-SPL discovery enabled for this run")

    if spl_blocked and not inputs.has_workflow_plan:
        mark("ensure_workflow_plan", "spl blocked and no workflow plan present")

    if contract.answer_goal in _REFERENCE_GOALS or "reference_resolution" in evidence:
        mark("reference_finalize", "reference identifiers in scope")

    if (
        contract.answer_goal in _MITRE_GOALS
        or "mitre_mapping" in live
        or "mitre_decision" in evidence
    ):
        mark("mitre_finalize", "mitre mapping in scope")

    if "cve_lookup" in live or "cve" in evidence:
        mark("cve_adapter", "cve context required")

    if mcp_required or spl_required or inputs.has_workflow_plan:
        # The execution phase owns the MCP gate, HIL and RBAC. It is applicable
        # whenever there is something for that gate to adjudicate — including a
        # validated-but-never-eligible SPL turn, where the gate is what records
        # `execution_eligible=false`.
        mark("execution", "execution gate must adjudicate this turn")

    applicable = frozenset(reasons)
    mandatory = frozenset(
        name for name in applicable if PHASE_REGISTRY[name].mandatory_when_applicable
    )
    ordering = tuple(
        (earlier, later)
        for earlier, later in ordering_constraints()
        if earlier in applicable and later in applicable
    )
    return PhasePolicyResolution(
        applicable=applicable,
        mandatory=mandatory,
        ordering=ordering,
        reasons=tuple(sorted(reasons.items())),
    )
