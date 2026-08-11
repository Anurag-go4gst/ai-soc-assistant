"""Typed step output→input handoffs and bounded gap re-planning (Plan 2, C1-E3).

Execution order is only meaningful if each downstream stage's inputs are
declared, typed, and validated. This module names the five real handoffs in the
current pipeline, decides what happens when one is missing or empty, and
answers the C0-carried refinement question: *may another bounded guided round
run?*

Boundaries:
- Declared keys only. `read_handoff_value` refuses any key that is not in the
  handoff table, so no stage can interpolate an arbitrary state key.
- Nothing sensitive travels. A handoff carries evidence-shaped state, never a
  prompt, completion, credential, or raw model output (pinned by test).
- The MCP gate handoff resolves *only* on approved, non-null
  `spl_validation.normalized_spl`. Candidate SPL can never satisfy it.
- Refinement needs round-varying input. A second round is authorized only when
  newly collected evidence actually changed the produced-key set **and** a
  reachable gap remains. No count heuristic, and no retired planning-model rail.
- Pure and unwired. No settings, connector, LLM, or state mutation; C1-E4 owns
  wiring, behind `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` (default false).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from app.planner.resource_plan_execution import ExecutionContract


class HandoffOutcome(str, Enum):
    SATISFIED = "satisfied"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FALLBACK = "fallback"


class UndeclaredHandoffKey(KeyError):
    """Raised when a caller asks for a state key no handoff declares."""


@dataclass(frozen=True)
class HandoffSpec:
    name: str
    state_key: str
    producer_stage: str
    consumer_stage: str
    required: bool
    #: outcome when the value is absent, empty, or unusable
    on_missing: HandoffOutcome
    value_type: type | tuple[type, ...]


@dataclass(frozen=True)
class HandoffResult:
    name: str
    outcome: HandoffOutcome
    reason: str | None = None
    value: Any = None


@dataclass(frozen=True)
class RefinementDecision:
    refine: bool
    reason: str
    unresolved_gaps: list[str] = field(default_factory=list)


HANDOFFS: tuple[HandoffSpec, ...] = (
    HandoffSpec(
        name="rag_to_spl_slot_fill",
        state_key="soc_kb_retrieval",
        producer_stage="rag_early",
        consumer_stage="spl_source_resolve",
        required=False,
        on_missing=HandoffOutcome.SKIPPED,
        value_type=dict,
    ),
    HandoffSpec(
        # Live dispatch-v2 pre-SPL discovery. Distinct from the retired legacy
        # discovery loop: it is produced by the `pre_spl_mcp_discovery` stage
        # and read from the dispatch runtime context, never from the fenced
        # evidence loop.
        name="pre_spl_discovery_to_spl",
        state_key="pipeline_dispatch.runtime_context.mcp_discovery_context",
        producer_stage="pre_spl_mcp_discovery",
        consumer_stage="workflow_spl",
        required=False,
        on_missing=HandoffOutcome.SKIPPED,
        value_type=dict,
    ),
    HandoffSpec(
        name="spl_candidate_to_source_resolve",
        state_key="candidate_spl",
        producer_stage="workflow_spl",
        consumer_stage="spl_source_resolve",
        required=False,
        on_missing=HandoffOutcome.FALLBACK,
        value_type=dict,
    ),
    HandoffSpec(
        name="source_resolve_to_validation",
        state_key="spl_validation",
        producer_stage="spl_source_resolve",
        consumer_stage="spl_validate",
        required=True,
        on_missing=HandoffOutcome.BLOCKED,
        value_type=dict,
    ),
    HandoffSpec(
        name="approved_spl_to_mcp_gate",
        state_key="spl_validation.normalized_spl",
        producer_stage="spl_validate",
        consumer_stage="mcp_execution_gate",
        required=True,
        on_missing=HandoffOutcome.BLOCKED,
        value_type=str,
    ),
    HandoffSpec(
        name="evidence_to_finalization",
        state_key="source_evidence",
        producer_stage="execution",
        consumer_stage="finalize",
        required=False,
        on_missing=HandoffOutcome.SKIPPED,
        value_type=(list, dict),
    ),
)

_DECLARED_KEYS = {spec.state_key for spec in HANDOFFS}


def handoff_by_name(name: str) -> HandoffSpec:
    for spec in HANDOFFS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def read_handoff_value(state: Mapping[str, Any], key: str) -> Any:
    """Read a declared handoff key. Undeclared keys are refused, not guessed."""
    if key not in _DECLARED_KEYS:
        raise UndeclaredHandoffKey(key)
    value: Any = state
    for part in key.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
        if value is None:
            return None
    return value


def _missing(spec: HandoffSpec, reason: str) -> HandoffResult:
    return HandoffResult(name=spec.name, outcome=spec.on_missing, reason=reason)


def _evaluate(spec: HandoffSpec, state: Mapping[str, Any]) -> HandoffResult:
    root = spec.state_key.split(".")[0]
    raw_root = state.get(root)
    if raw_root is not None and not isinstance(raw_root, (Mapping, list)):
        return HandoffResult(
            name=spec.name, outcome=HandoffOutcome.BLOCKED, reason=f"wrong_type_{root}"
        )

    value = read_handoff_value(state, spec.state_key)
    if spec.name == "approved_spl_to_mcp_gate" and value is None:
        # One reason for every unusable gate input: absent, unapproved, or empty.
        return HandoffResult(
            name=spec.name,
            outcome=HandoffOutcome.BLOCKED,
            reason="missing_approved_normalized_spl",
        )
    if value is None:
        return _missing(spec, f"missing_{root}")
    if not isinstance(value, spec.value_type):
        return HandoffResult(
            name=spec.name, outcome=HandoffOutcome.BLOCKED, reason=f"wrong_type_{root}"
        )

    if spec.name == "approved_spl_to_mcp_gate":
        # Approval is the authority, not the presence of SPL text. Candidate SPL
        # and unapproved validation both fail closed here.
        validation = state.get("spl_validation")
        approved = bool(validation.get("approved")) if isinstance(validation, Mapping) else False
        if not approved or not str(value).strip():
            return HandoffResult(
                name=spec.name,
                outcome=HandoffOutcome.BLOCKED,
                reason="missing_approved_normalized_spl",
            )
        return HandoffResult(name=spec.name, outcome=HandoffOutcome.SATISFIED, value=value)

    if _is_empty(value):
        return _missing(spec, f"empty_{root}")
    return HandoffResult(name=spec.name, outcome=HandoffOutcome.SATISFIED, value=value)


def _is_empty(value: Any) -> bool:
    if isinstance(value, Mapping):
        return not value or all(_is_empty(item) for item in value.values())
    if isinstance(value, (list, tuple, set, str)):
        return not value
    return False


def evaluate_handoffs(state: Mapping[str, Any]) -> dict[str, HandoffResult]:
    """Resolve every declared handoff against a state view."""
    return {spec.name: _evaluate(spec, state) for spec in HANDOFFS}


def evaluate_unresolved_gaps(
    contract: ExecutionContract | None,
    *,
    produced_keys: set[str],
) -> list[str]:
    """Evidence keys the plan can still reach that nothing has produced yet.

    A blocked step's outputs are not gaps: nothing in this plan can produce
    them, so counting them would manufacture endless refinement.
    """
    if contract is None:
        return []
    gaps: list[str] = []
    for step in contract.steps:
        if not step.executable:
            continue
        for key in step.produces_evidence_keys:
            if key not in produced_keys and key not in gaps:
                gaps.append(key)
    return gaps


def refinement_decision(
    contract: ExecutionContract | None,
    *,
    previous_produced_keys: set[str],
    current_produced_keys: set[str],
    rounds_used: int,
    max_rounds: int,
) -> RefinementDecision:
    """Authorize one more bounded round only on genuinely round-varying input.

    The B2-R2 finding was that deterministic guided planning had no input that
    could change between rounds, so a second round was an idempotent no-op. The
    round-varying input is the evidence actually collected: refinement is
    allowed only when the produced-key set grew *and* a reachable gap remains,
    within the hard round bound.
    """
    gaps = evaluate_unresolved_gaps(contract, produced_keys=current_produced_keys)
    if rounds_used >= max_rounds:
        return RefinementDecision(False, "round_bound_reached", gaps)
    if not current_produced_keys - previous_produced_keys:
        return RefinementDecision(False, "no_new_evidence", gaps)
    if not gaps:
        return RefinementDecision(False, "evidence_satisfied", gaps)
    return RefinementDecision(True, "new_evidence_with_open_gap", gaps)
