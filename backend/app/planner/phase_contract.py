"""Per-run resolved lifecycle (Plan 5 C0.2).

`PhaseRegistry` (C0) is the catalog; `PhasePolicy` (C0.1) decides applicability;
this module freezes that verdict for one run.

Once resolved, a `PhaseContract` is immutable. Neither the ResourcePlanner, the
four advisory specialists, nor any LLM advisory may add, remove, reorder or
downgrade a phase in it — they hold no method to do so, and the enforcement path
is `validate_schedule`, which fails closed on a missing mandatory phase and on an
ordering violation rather than repairing either silently.

The contract carries **no execution authority**. It states which lifecycle
phases this run owes and in what order; the MCP gate, HIL, RBAC and SPL
validation keep their authority unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.planner.phase_registry import (
    PHASE_REGISTRY,
    phase_for_hook,
    phase_spec,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.chat.contracts.resolved_query import ResolvedQueryContract
    from app.planner.phase_policy import PhasePolicyResolution
    from app.planner.resource_plan import ResourcePlan

SCHEMA_VERSION = "phase_contract_v1"


class PhaseContractViolation(ValueError):
    """Raised when a schedule breaks the resolved lifecycle for this run."""


@dataclass(frozen=True)
class ContractedPhase:
    name: str
    mandatory: bool
    removable: bool
    hook_name: str | None
    after: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class PhaseContract:
    """The immutable lifecycle this run owes."""

    schema_version: str
    phases: tuple[ContractedPhase, ...]
    ordering: tuple[tuple[str, str], ...]
    provenance: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(phase.name for phase in self.phases)

    @property
    def mandatory_names(self) -> frozenset[str]:
        return frozenset(phase.name for phase in self.phases if phase.mandatory)

    @property
    def hook_bound_mandatory(self) -> frozenset[str]:
        """Mandatory phases a hook schedule is actually able to carry."""
        return frozenset(
            phase.name for phase in self.phases if phase.mandatory and phase.hook_name
        )

    @property
    def inline_mandatory(self) -> frozenset[str]:
        """Mandatory phases no hook loop can run — they execute inline.

        Named explicitly so that "the schedule does not contain it" is never
        silently read as "this run does not owe it".
        """
        return frozenset(
            phase.name for phase in self.phases if phase.mandatory and not phase.hook_name
        )

    def requires(self, phase: str) -> bool:
        return phase_spec(phase).name in self.names

    def validate_schedule(self, hooks: list[str] | tuple[str, ...]) -> None:
        """Fail closed when a schedule drops or reorders a contracted phase."""
        scheduled: dict[str, int] = {}
        for index, hook in enumerate(hooks):
            spec = phase_for_hook(hook)
            scheduled.setdefault(spec.name, index)

        missing = sorted(self.hook_bound_mandatory - set(scheduled))
        if missing:
            raise PhaseContractViolation(
                f"schedule omits mandatory lifecycle phase(s) {missing}; "
                f"the planner may propose work, never lifecycle"
            )

        extraneous = sorted(set(scheduled) - self.names)
        if extraneous:
            raise PhaseContractViolation(
                f"schedule contains phase(s) PhasePolicy found inapplicable: {extraneous}"
            )

        for earlier, later in self.ordering:
            if earlier in scheduled and later in scheduled and scheduled[earlier] > scheduled[later]:
                raise PhaseContractViolation(
                    f"{later!r} must not precede {earlier!r} (schedule: {list(hooks)})"
                )

    def trace_payload(self) -> dict[str, Any]:
        """Redacted observability surface. Names and ordering only, no authority."""
        return {
            "schema_version": self.schema_version,
            "phases": [
                {
                    "name": phase.name,
                    "mandatory": phase.mandatory,
                    "removable": phase.removable,
                    "hook": phase.hook_name,
                    "reason": phase.reason,
                }
                for phase in self.phases
            ],
            "ordering": [list(pair) for pair in self.ordering],
            "inline_mandatory": sorted(self.inline_mandatory),
        }


def build_phase_contract(
    resolution: "PhasePolicyResolution",
    *,
    provenance: dict[str, str] | None = None,
) -> PhaseContract:
    """Freeze a PhasePolicy verdict into the per-run contract."""
    reasons = dict(resolution.reasons)
    phases = tuple(
        ContractedPhase(
            name=name,
            mandatory=name in resolution.mandatory,
            removable=PHASE_REGISTRY[name].planner_removable,
            hook_name=PHASE_REGISTRY[name].hook_name,
            after=PHASE_REGISTRY[name].after,
            reason=reasons.get(name, ""),
        )
        # Registry declaration order, so the contract reads the same way twice.
        for name in PHASE_REGISTRY
        if name in resolution.applicable
    )
    return PhaseContract(
        schema_version=SCHEMA_VERSION,
        phases=phases,
        ordering=resolution.ordering,
        provenance=tuple(sorted((provenance or {}).items())),
    )


def resolve_and_freeze(
    contract: "ResolvedQueryContract",
    plan: "ResourcePlan | None" = None,
    inputs: Any = None,
    *,
    provenance: dict[str, str] | None = None,
) -> PhaseContract:
    """Convenience seam: policy → contract, in one deterministic step."""
    from app.planner.phase_policy import resolve_phase_policy

    return build_phase_contract(
        resolve_phase_policy(contract, plan, inputs), provenance=provenance
    )
