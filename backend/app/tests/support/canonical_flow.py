"""Canonical flow test helper — production planning seam without bypassing contracts.

Flow (no shortcuts):
  resolve_session_context → graph_node_init_routing → run_canonical_planning
    → CanonicalPlanningInput + CanonicalPlanningOutcome
    → committed ResourcePlan (planned) or typed non-executable outcome
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from app.chat.canonical_planning_orchestrator import run_canonical_planning
from app.chat.contracts.canonical_planning_outcome import CanonicalPlanningOutcome, outcome_from_state
from app.chat.pipeline import ChatPipelineState, graph_node_init_routing
from app.chat.session_context import resolve_session_context
from app.schemas.requests import ChatRequest


@dataclass(frozen=True)
class CanonicalFlowResult:
    """Structured result from ``run_canonical_flow``."""

    state: ChatPipelineState
    outcome: CanonicalPlanningOutcome | None
    canonical_planning_input: dict[str, Any] | None
    evidence_plan: dict[str, Any] | None
    resource_plan: dict[str, Any] | None
    committed: bool

    @classmethod
    def from_state(cls, state: ChatPipelineState) -> CanonicalFlowResult:
        outcome = outcome_from_state(state)
        cpi = state.get("canonical_planning_input")
        ep = state.get("evidence_plan")
        rp: dict[str, Any] | None = None
        committed = False
        if isinstance(ep, dict):
            rp_raw = ep.get("resource_plan")
            if isinstance(rp_raw, dict):
                rp = rp_raw
                prov = rp_raw.get("provenance") or {}
                committed = bool(prov.get("committed"))
        return cls(
            state=state,
            outcome=outcome,
            canonical_planning_input=cpi if isinstance(cpi, dict) else None,
            evidence_plan=ep if isinstance(ep, dict) else None,
            resource_plan=rp,
            committed=committed,
        )


def run_canonical_flow(
    query: str,
    *,
    handoff_resume: dict[str, Any] | None = None,
    session_id: str | None = None,
    trace_id: str = "canonical-flow-test",
    use_case_id: str | None = None,
    extra_state: dict[str, Any] | None = None,
) -> CanonicalFlowResult:
    """Run the production canonical planning seam for tests.

    Does not bypass runtime contracts — uses the same entry nodes as live ``/chat``
    through ``run_canonical_planning``.
    """
    request = ChatRequest(message=query, session_id=session_id)
    session_resolution = resolve_session_context(request)
    state: ChatPipelineState = {
        "request": request,
        "session_id": session_resolution.session_id,
        "session_pins": session_resolution.pins,
        "session_context_resolution": session_resolution,
        "effective_query": session_resolution.effective_query,
        "handoff_resume": handoff_resume if handoff_resume is not None else session_resolution.handoff_resume,
        "trace_id": trace_id,
    }
    if use_case_id:
        state["selected_use_case"] = SimpleNamespace(use_case_id=use_case_id)
    if extra_state:
        state = {**state, **extra_state}
    state = graph_node_init_routing(state)
    state = run_canonical_planning(state)
    return CanonicalFlowResult.from_state(state)
