"""Closed catalog of lifecycle phases (Plan 5 C0).

Before this module there were three surfaces and no two agreed: the
``PipelineStage`` enum (``chat/contracts/pipeline_dispatch.py``), the executor's
``_HOOK_BY_NAME`` table (``planner/executor.py``), and the fallback ``hook_nodes``
literal (``chat/pipeline.py``). The same phase was ``mcp_execution`` in one and
``execution`` in the others; ``mitre_finalize``/``cve_adapter`` were scheduled by
a surface that cannot run them while executing inline in
``graph_node_context_finalize``; the compiler omitted ``spl_postprocessor`` and
``reference_finalize`` entirely. Measured table:
``docs/evals/plan5/c0_phase_surface_disagreement.md``.

Boundaries:

- **Catalog only.** This module decides nothing about a given run. Applicability
  is C0.1 (``phase_policy``); the per-run resolved lifecycle is C0.2
  (``PhaseContract``). Nothing here reads state, settings, an LLM or the network.
- **Closed.** A phase name outside the catalog raises rather than being guessed
  at, mirroring the canonical planning-telemetry catalog.
- **Ordering is declarative.** ``after`` expresses the constraint the SPL chain
  used to carry only by hand-written list order in
  ``pipeline_dispatch_builder._SPL_CHAIN``. ``validate_schedule_order`` checks it
  at runtime, so "SPL validation precedes the MCP execution gate" is an asserted
  property rather than a coincidence of three separate schedules.
- **Non-removability is data.** ``planner_removable`` is False for every governed
  phase; PhasePolicy owns the decision, the planner and every advisory are
  forbidden to touch it. The registry records the rule; C0.2 enforces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.chat.contracts.pipeline_dispatch import PipelineStage

SCHEMA_VERSION = "phase_registry_v1"

PhaseOwner = Literal[
    "executor_hook",  # runs as a hook in _HOOK_BY_NAME / fallback hook_nodes
    "pipeline_inline",  # runs inline inside a pipeline node, orderable by nothing
    "dispatch_v2_inline",  # runs inline under dispatch-v2 only
]


class UnknownPhaseError(KeyError):
    """Raised when a name outside the closed catalog is used as a phase."""


class PhaseOrderViolation(ValueError):
    """Raised when a schedule violates a registry ordering constraint."""


@dataclass(frozen=True)
class PhaseSpec:
    """Identity, ownership, ordering and authority of one lifecycle phase."""

    name: str
    owner: PhaseOwner
    hook_name: str | None
    stage: PipelineStage | None
    executed_by: tuple[str, ...]
    # Name of the deterministic applicability predicate C0.1 must implement.
    # The registry names the input; it does not evaluate it.
    applicability_input: str
    mandatory_when_applicable: bool
    planner_removable: bool
    terminal: bool
    after: tuple[str, ...]
    authority: str


_SPECS: tuple[PhaseSpec, ...] = (
    PhaseSpec(
        name="prepare_rag_only",
        owner="executor_hook",
        hook_name="prepare_rag_only",
        stage=None,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="rag_only_lane",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="none — prepares the knowledge-only lane",
    ),
    PhaseSpec(
        name="rag_early",
        owner="executor_hook",
        hook_name="rag_early",
        stage=PipelineStage.rag_early,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="knowledge_evidence_required",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=("prepare_rag_only",),
        authority="governed SOC-KB retrieval into SourceEvidence; never a direct RAG→LLM path",
    ),
    PhaseSpec(
        name="pre_spl_mcp_discovery",
        owner="dispatch_v2_inline",
        hook_name=None,
        stage=PipelineStage.pre_spl_mcp_discovery,
        executed_by=("chat/pipeline.py:graph_node_workflow_spl (dispatch-v2 only)",),
        applicability_input="pre_spl_discovery_enabled",
        # Bounded read-only enrichment: applicable does not imply mandatory.
        mandatory_when_applicable=False,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="read-only bounded MCP discovery; no execution authority",
    ),
    PhaseSpec(
        name="workflow_spl",
        owner="executor_hook",
        hook_name="workflow_spl",
        stage=PipelineStage.workflow_spl,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="spl_artifact_required",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=("pre_spl_mcp_discovery",),
        authority="produces candidate SPL only; candidate SPL is never executable",
    ),
    PhaseSpec(
        name="spl_postprocessor",
        owner="executor_hook",
        hook_name="spl_postprocessor",
        stage=PipelineStage.spl_postprocessor,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="spl_candidate_present",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=("workflow_spl",),
        authority="owns deterministic validate_spl; MUST precede execution",
    ),
    PhaseSpec(
        name="spl_source_resolve",
        owner="executor_hook",
        hook_name="spl_source_resolve",
        stage=PipelineStage.spl_source_resolve,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="spl_source_slots_present",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=("workflow_spl",),
        authority="unresolved slots route to HIL clarification, never a lab-draft fallback",
    ),
    PhaseSpec(
        name="ensure_workflow_plan",
        owner="executor_hook",
        hook_name="ensure_workflow_plan",
        stage=None,
        executed_by=("planner/executor.py:_HOOK_BY_NAME",),
        applicability_input="spl_blocked_without_workflow_plan",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="none — supplies the workflow-plan stub the execution gate reads",
    ),
    PhaseSpec(
        name="reference_finalize",
        owner="executor_hook",
        hook_name="reference_finalize",
        stage=PipelineStage.reference_finalize,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="reference_ids_present",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="claim-restricted reference taxonomy; no hallucinated IDs",
    ),
    PhaseSpec(
        name="mitre_finalize",
        owner="pipeline_inline",
        hook_name=None,
        stage=PipelineStage.mitre_finalize,
        # The C0 ownership gap, recorded rather than papered over: scheduled by
        # pipeline_dispatch_builder, dropped by the projection, executed inline.
        executed_by=("chat/pipeline.py:graph_node_context_finalize -> run_mitre_evidence_branch",),
        applicability_input="mitre_mapping_required",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="governed MITRE visibility policy; suppression must not be widened",
    ),
    PhaseSpec(
        name="cve_adapter",
        owner="pipeline_inline",
        hook_name=None,
        stage=PipelineStage.cve_adapter,
        executed_by=(
            "chat/pipeline.py:graph_node_context_finalize -> _resolve_vulnerability_source_status",
        ),
        applicability_input="cve_context_required",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=False,
        after=(),
        authority="operator-vendored CVE snapshot with honest provenance",
    ),
    PhaseSpec(
        name="execution",
        owner="executor_hook",
        hook_name="execution",
        stage=PipelineStage.mcp_execution,
        executed_by=("planner/executor.py:_HOOK_BY_NAME", "chat/pipeline.py:hook_nodes"),
        applicability_input="mcp_execution_planned",
        mandatory_when_applicable=True,
        planner_removable=False,
        terminal=True,
        after=("spl_postprocessor", "spl_source_resolve", "ensure_workflow_plan"),
        authority="sole owner of the MCP execution gate, HIL and RBAC",
    ),
)

PHASE_REGISTRY: dict[str, PhaseSpec] = {spec.name: spec for spec in _SPECS}
PHASE_NAMES: frozenset[str] = frozenset(PHASE_REGISTRY)

_BY_HOOK: dict[str, str] = {
    spec.hook_name: spec.name for spec in _SPECS if spec.hook_name is not None
}
_BY_STAGE: dict[PipelineStage, str] = {
    spec.stage: spec.name for spec in _SPECS if spec.stage is not None
}


def phase_spec(name: str) -> PhaseSpec:
    """Resolve a canonical phase name. Closed catalog: unknown names raise."""
    try:
        return PHASE_REGISTRY[name]
    except KeyError as exc:
        raise UnknownPhaseError(
            f"unknown lifecycle phase {name!r}; the catalog is closed — add a PhaseSpec "
            f"deliberately rather than introducing an unclassified phase"
        ) from exc


def phase_for_hook(hook_name: str) -> PhaseSpec:
    """Resolve an executor/fallback hook name to its phase."""
    try:
        return PHASE_REGISTRY[_BY_HOOK[hook_name]]
    except KeyError as exc:
        raise UnknownPhaseError(f"no lifecycle phase binds hook {hook_name!r}") from exc


def phase_for_stage(stage: PipelineStage) -> PhaseSpec:
    """Resolve a dispatch stage to its phase (``mcp_execution`` → ``execution``)."""
    try:
        return PHASE_REGISTRY[_BY_STAGE[stage]]
    except KeyError as exc:
        raise UnknownPhaseError(f"no lifecycle phase binds stage {stage!r}") from exc


def ordering_constraints() -> tuple[tuple[str, str], ...]:
    """Every ``(earlier, later)`` pair the registry declares."""
    pairs: list[tuple[str, str]] = []
    for spec in _SPECS:
        for earlier in spec.after:
            pairs.append((earlier, spec.name))
    return tuple(pairs)


def validate_schedule_order(hooks: list[str] | tuple[str, ...]) -> None:
    """Raise if a hook schedule violates a declared ordering constraint.

    Only phases actually present are checked — a schedule legitimately omits
    phases that PhasePolicy found non-applicable. This is the runtime assertion
    of what ``_SPL_CHAIN`` previously expressed only as literal list order.
    """
    positions: dict[str, int] = {}
    for index, hook in enumerate(hooks):
        spec = phase_for_hook(hook)
        positions.setdefault(spec.name, index)

    for earlier, later in ordering_constraints():
        if earlier in positions and later in positions and positions[earlier] > positions[later]:
            raise PhaseOrderViolation(
                f"{later!r} must not precede {earlier!r} (schedule: {list(hooks)})"
            )


def mandatory_phases() -> frozenset[str]:
    """Phases that are mandatory once PhasePolicy finds them applicable."""
    return frozenset(spec.name for spec in _SPECS if spec.mandatory_when_applicable)


def phases_without_hook_owner() -> frozenset[str]:
    """Phases no hook loop can run — the measured C0 ownership gap.

    Kept as a named query rather than a comment so a future change that gives
    one of them a hook (or adds a new orphan) is visible in a test, not folded
    silently into a schedule.
    """
    return frozenset(spec.name for spec in _SPECS if spec.hook_name is None)
