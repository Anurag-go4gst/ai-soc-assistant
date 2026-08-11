"""ResourcePlan execution dependency contract (Plan 2, C1-E1) — validation only.

C0 decided `EXECUTION-DRIVEN` with `v1_v2_posture: EXTEND_LIVE_RESOURCE_PLAN`:
the live `ResourcePlan` gains one optional, typed `execution` block per step
(`PlanStep.execution`), and this module owns the rules that block make that
block safe. `ResourcePlanV2` and the fenced recipe scheduler are **not**
imported — only their data vocabulary (`depends_on`, produced/required evidence
keys, `step_id | "terminal" | "hil"` failover targets) is reused, re-declared
here in fresh code so no fenced-recipe authority comes with it.

Boundaries this module keeps:
- Pure. No connector, LLM, registry, settings read, or state mutation. It takes
  a plan and returns a description of it.
- Not an authority. Producing a contract does not schedule, dispatch, or
  authorize anything; wiring is C1-E2 onward behind
  `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false).
- Fails closed by downgrade. Anything absent, invalid, cyclic, or unsupported
  yields no contract plus a reason, and the caller keeps the existing fixed
  deterministic schedule.
- Bounds side effects. Only `mcp_execution` is side-effecting, and a
  side-effecting step may never declare a retry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.planner.resource_plan import PlanStep, ResourcePlan

# A failover edge targets another step_id or a terminal policy.
EXECUTION_FALLBACK_TARGETS = frozenset({"terminal", "hil"})

# Retry ceiling for read-only steps. Side-effecting steps are pinned to 1.
MAX_STEP_ATTEMPTS = 3

SIDE_EFFECTING_PURPOSES = frozenset({"mcp_execution"})

# Statuses that make a step non-executable before any scheduling happens.
_BLOCKED_STATUSES = frozenset({"blocked_policy", "not_onboarded"})

# Purposes the composer can emit. A purpose outside this set downgrades the
# whole plan rather than being guessed at.
SUPPORTED_EXECUTION_PURPOSES = frozenset(
    {
        "knowledge_retrieval",
        "spl_artifact",
        "mcp_execution",
        "mcp_discovery",
        "safe_catalog_query",
        "cve_lookup",
        "mitre_mapping",
        "evidence_collection",
        "context_sufficiency",
        "narration",
    }
)

# Declared evidence keys reuse the A1.1 rule: the root of every key must be a
# real pipeline state channel; a dotted path names a nested field of one.
_DERIVED_EVIDENCE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # purpose: (requires, produces)
    "knowledge_retrieval": ((), ("soc_kb_retrieval",)),
    "spl_artifact": ((), ("candidate_spl", "spl_validation")),
    "mcp_execution": (("spl_validation",), ("execution",)),
    "mcp_discovery": ((), ("mcp_evidence",)),
    "safe_catalog_query": ((), ("mcp_evidence",)),
    "cve_lookup": ((), ("reference_resolution",)),
    "mitre_mapping": ((), ("mitre_decision",)),
    "evidence_collection": ((), ("source_evidence",)),
    "context_sufficiency": (("source_evidence",), ("context_sufficiency",)),
    "narration": ((), ()),
}


class StepExecutionSpec(BaseModel):
    """Optional per-step execution declaration carried on `PlanStep.execution`."""

    depends_on: list[str] = Field(default_factory=list)
    parallel_group: str | None = None
    requires_evidence_keys: list[str] = Field(default_factory=list)
    produces_evidence_keys: list[str] = Field(default_factory=list)
    on_failure: str = "hil"
    max_attempts: int = 1


@dataclass(frozen=True)
class ExecutionContractError:
    code: str
    step_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ExecutionContractValidation:
    valid: bool
    errors: list[ExecutionContractError] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionStep:
    """A plan step plus its resolved, validated execution semantics."""

    step_id: str
    purpose: str
    depends_on: list[str]
    parallel_group: str | None
    requires_evidence_keys: list[str]
    produces_evidence_keys: list[str]
    on_failure: str
    max_attempts: int
    side_effecting: bool
    executable: bool
    skip_reason: str | None


@dataclass(frozen=True)
class ExecutionContract:
    """Validated dependency view of a ResourcePlan. Descriptive, not authoritative."""

    steps: list[ExecutionStep]
    waves: list[list[str]]

    def step_by_id(self, step_id: str) -> ExecutionStep | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


def _state_channels() -> frozenset[str]:
    from app.graph.resource_planner_graph import ResourcePlannerGraphState

    return frozenset(ResourcePlannerGraphState.__annotations__)


def _declared_spec(step: "PlanStep") -> StepExecutionSpec | None:
    spec = getattr(step, "execution", None)
    if spec is None:
        return None
    if isinstance(spec, StepExecutionSpec):
        return spec
    return StepExecutionSpec.model_validate(spec)


def derive_execution_spec(step: "PlanStep") -> StepExecutionSpec:
    """Default semantics for a step that declares none.

    The defaults reproduce the current fixed schedule: SPL is produced before
    the MCP step consumes its validation, everything else is independent, and
    nothing is retried.
    """
    purpose = str(getattr(step, "purpose", "") or "")
    requires, produces = _DERIVED_EVIDENCE.get(purpose, ((), ()))
    return StepExecutionSpec(
        requires_evidence_keys=list(requires),
        produces_evidence_keys=list(produces),
        on_failure="hil",
        max_attempts=1,
    )


def _resolved_spec(step: "PlanStep") -> StepExecutionSpec:
    return _declared_spec(step) or derive_execution_spec(step)


def _derived_dependencies(plan: "ResourcePlan") -> dict[str, list[str]]:
    """Dependencies implied by the fixed schedule when none are declared.

    Only one real handoff exists today: the MCP step consumes the SPL step's
    validated output. It is expressed as a step dependency (not merely an
    evidence key) so the schedule is provable, and it is omitted entirely when
    the plan has no SPL step — no phantom edges.
    """
    spl_ids = [
        str(step.step_id)
        for step in plan.steps
        if str(getattr(step, "purpose", "")) == "spl_artifact"
    ]
    derived: dict[str, list[str]] = {}
    if not spl_ids:
        return derived
    for step in plan.steps:
        if str(getattr(step, "purpose", "")) == "mcp_execution":
            derived[str(step.step_id)] = list(spl_ids)
    return derived


def _dependencies_for(step: "PlanStep", plan: "ResourcePlan") -> list[str]:
    declared = _declared_spec(step)
    if declared is not None:
        return list(declared.depends_on)
    return list(_derived_dependencies(plan).get(str(step.step_id), []))


def _skip_reason_for_status(step: "PlanStep") -> str | None:
    status = str(getattr(step, "status", "") or "")
    if status == "not_onboarded":
        return "resource_not_onboarded"
    if status == "blocked_policy":
        reason = str(getattr(step, "status_reason", "") or "").strip()
        return reason or "blocked_policy"
    return None


def validate_execution_contract(plan: "ResourcePlan") -> ExecutionContractValidation:
    """Reject anything unbounded, cyclic, dangling, or unsafely retried."""
    errors: list[ExecutionContractError] = []
    channels = _state_channels()

    seen: set[str] = set()
    step_ids: list[str] = []
    for step in plan.steps:
        step_id = str(step.step_id)
        if step_id in seen:
            errors.append(ExecutionContractError(code="duplicate_step_id", step_id=step_id))
            continue
        seen.add(step_id)
        step_ids.append(step_id)

    dependencies: dict[str, list[str]] = {}
    groups: dict[str, list[str]] = {}

    for step in plan.steps:
        step_id = str(step.step_id)
        purpose = str(getattr(step, "purpose", "") or "")
        spec = _resolved_spec(step)
        depends_on = _dependencies_for(step, plan)
        dependencies[step_id] = depends_on

        if purpose not in SUPPORTED_EXECUTION_PURPOSES:
            errors.append(
                ExecutionContractError(code="unsupported_purpose", step_id=step_id, detail=purpose)
            )

        for dependency in depends_on:
            if dependency == step_id:
                errors.append(ExecutionContractError(code="self_dependency", step_id=step_id))
            elif dependency not in seen:
                errors.append(
                    ExecutionContractError(
                        code="unknown_dependency", step_id=step_id, detail=dependency
                    )
                )

        for key in [*spec.requires_evidence_keys, *spec.produces_evidence_keys]:
            if str(key).split(".")[0] not in channels:
                errors.append(
                    ExecutionContractError(
                        code="unknown_evidence_key", step_id=step_id, detail=str(key)
                    )
                )

        if spec.on_failure == step_id:
            errors.append(ExecutionContractError(code="self_fallback_target", step_id=step_id))
        elif spec.on_failure not in EXECUTION_FALLBACK_TARGETS and spec.on_failure not in seen:
            errors.append(
                ExecutionContractError(
                    code="invalid_fallback_target", step_id=step_id, detail=spec.on_failure
                )
            )

        if purpose in SIDE_EFFECTING_PURPOSES and spec.max_attempts != 1:
            errors.append(
                ExecutionContractError(code="unsafe_retry_side_effecting", step_id=step_id)
            )
        elif not 1 <= spec.max_attempts <= MAX_STEP_ATTEMPTS:
            errors.append(ExecutionContractError(code="attempts_out_of_bounds", step_id=step_id))

        if spec.parallel_group:
            groups.setdefault(spec.parallel_group, []).append(step_id)
            if purpose in SIDE_EFFECTING_PURPOSES:
                errors.append(
                    ExecutionContractError(
                        code="parallel_group_side_effecting",
                        step_id=step_id,
                        detail=spec.parallel_group,
                    )
                )

    for group_name, members in groups.items():
        member_set = set(members)
        for member in members:
            if member_set & set(dependencies.get(member, [])):
                errors.append(
                    ExecutionContractError(
                        code="parallel_group_internal_dependency",
                        step_id=member,
                        detail=group_name,
                    )
                )

    if _has_cycle(step_ids, dependencies):
        errors.append(ExecutionContractError(code="dependency_cycle"))

    return ExecutionContractValidation(valid=not errors, errors=errors)


def _has_cycle(step_ids: list[str], dependencies: dict[str, list[str]]) -> bool:
    known = set(step_ids)
    unresolved = set(step_ids)
    while unresolved:
        ready = {
            step_id
            for step_id in unresolved
            if not (set(dependencies.get(step_id, [])) & known & unresolved) - {step_id}
            and step_id not in dependencies.get(step_id, [])
        }
        if not ready:
            return True
        unresolved -= ready
    return False


def _waves(steps: list[ExecutionStep]) -> list[list[str]]:
    """Deterministic dependency waves; composed order breaks ties inside a wave."""
    order = [step.step_id for step in steps]
    dependencies = {step.step_id: set(step.depends_on) for step in steps}
    placed: set[str] = set()
    waves: list[list[str]] = []
    remaining = list(order)
    while remaining:
        wave = [step_id for step_id in remaining if dependencies[step_id] <= placed]
        if not wave:  # unreachable for a validated contract
            break
        waves.append(wave)
        placed.update(wave)
        remaining = [step_id for step_id in remaining if step_id not in placed]
    return waves


def build_execution_contract(plan: "ResourcePlan") -> ExecutionContract | None:
    """Resolve a validated plan into executable steps and dependency waves."""
    if not validate_execution_contract(plan).valid:
        return None

    resolved: list[ExecutionStep] = []
    for step in plan.steps:
        spec = _resolved_spec(step)
        purpose = str(getattr(step, "purpose", "") or "")
        skip_reason = _skip_reason_for_status(step)
        resolved.append(
            ExecutionStep(
                step_id=str(step.step_id),
                purpose=purpose,
                depends_on=_dependencies_for(step, plan),
                parallel_group=spec.parallel_group,
                requires_evidence_keys=list(spec.requires_evidence_keys),
                produces_evidence_keys=list(spec.produces_evidence_keys),
                on_failure=spec.on_failure,
                max_attempts=1 if purpose in SIDE_EFFECTING_PURPOSES else spec.max_attempts,
                side_effecting=purpose in SIDE_EFFECTING_PURPOSES,
                executable=skip_reason is None,
                skip_reason=skip_reason,
            )
        )

    resolved = _propagate_blocked(resolved)
    return ExecutionContract(steps=resolved, waves=_waves(resolved))


def _propagate_blocked(steps: list[ExecutionStep]) -> list[ExecutionStep]:
    """A step whose dependency cannot run cannot run either."""
    by_id = {step.step_id: step for step in steps}
    changed = True
    while changed:
        changed = False
        for index, step in enumerate(steps):
            if not step.executable:
                continue
            for dependency in step.depends_on:
                upstream = by_id.get(dependency)
                if upstream is not None and not upstream.executable:
                    blocked = ExecutionStep(
                        **{
                            **step.__dict__,
                            "executable": False,
                            "skip_reason": f"dependency_blocked:{dependency}",
                        }
                    )
                    steps[index] = blocked
                    by_id[step.step_id] = blocked
                    changed = True
                    break
    return steps


def execution_contract_or_downgrade(
    plan: "ResourcePlan | None",
) -> tuple[ExecutionContract | None, str | None]:
    """Contract, or `None` plus the reason the fixed schedule must be kept."""
    if plan is None:
        return None, "no_resource_plan"
    if not plan.steps:
        return None, "empty_resource_plan"

    validation = validate_execution_contract(plan)
    if not validation.valid:
        first = validation.errors[0]
        if first.code == "unsupported_purpose":
            return None, f"unsupported_purpose:{first.detail}"
        return None, f"contract_invalid:{first.code}"

    return build_execution_contract(plan), None
