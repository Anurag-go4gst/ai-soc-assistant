"""P3 runtime seam: Final RQC + CapabilitySnapshot -> validated plan.

The LLM proposal is optional and advisory. Case data never crosses the P3 model
boundary; deterministic code preserves Final-RQC facts and binds only rows from
CapabilitySnapshot.
"""

from __future__ import annotations

from typing import Any

from app.chat.guided_investigation_plan_llm import (
    INVESTIGATION_PLAN_ROLE,
    propose_investigation_plan_llm,
)
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.config import settings


def _read_capability_ids(snapshot: dict[str, Any]) -> list[str]:
    """Read-only capability ids the planner may reference, from the snapshot only.

    Availability is deliberately not filtered: architecture 2.10 keeps need and
    availability independent, so an unavailable-but-relevant read capability must
    still be nameable as a manual/alternate step rather than silently omitted.
    """
    ids: list[str] = []
    for row in snapshot.get("rows") or []:
        if not isinstance(row, dict):
            continue
        capability_id = str(row.get("capability_id") or "")
        if capability_id.startswith("mcp:") and capability_id not in ids:
            ids.append(capability_id)
    return ids


def maybe_attach_validated_investigation_plan(state: dict[str, Any]) -> dict[str, Any]:
    """Attach P3 planning artifacts on the P0 investigation wait-state."""
    p4_deterministic_plan = settings.ai_soc_investigation_plan_before_resource_plan_enabled
    if not settings.ai_soc_investigation_planner_enabled and not p4_deterministic_plan:
        return state

    rqc = (
        dict(state.get("resolved_query_contract") or {})
        if isinstance(state.get("resolved_query_contract"), dict)
        else {}
    )
    snapshot = (
        dict(state.get("capability_snapshot") or {})
        if isinstance(state.get("capability_snapshot"), dict)
        else {}
    )
    request = state.get("request")
    query = str(rqc.get("normalized_goal") or getattr(request, "message", "") or "").strip()
    baseline = build_deterministic_investigation_plan(
        query=query,
        entities=rqc.get("entities") if isinstance(rqc.get("entities"), dict) else None,
        resolved_query_contract=rqc,
        capability_snapshot=snapshot,
    )
    turn_budget = state.get("llm_turn_budget")
    if settings.ai_soc_investigation_planner_enabled:
        llm = propose_investigation_plan_llm(
            query=query,
            baseline=baseline,
            turn_budget=turn_budget,
            capability_ids=_read_capability_ids(snapshot),
        )
        # The planner materially shapes the analyst-visible plan, so it must
        # appear in the turn's LLM accounting. Without this the trace reported
        # zero sidecar calls for a turn a reasoning model actually contributed to.
        if llm.attempted and turn_budget is not None:
            turn_budget.record_sidecar(
                role=INVESTIGATION_PLAN_ROLE,
                provider_label=llm.provider_label,
                outcome="completed" if llm.proposal is not None else "dropped",
                latency_ms=llm.latency_ms or None,
                counts_against_quota=False,
            )
    else:
        from app.chat.guided_investigation_plan_llm import InvestigationPlanLlmResult

        llm = InvestigationPlanLlmResult(
            raw_llm=None,
            proposal=None,
            attempted=False,
            timed_out=False,
            provider_label=None,
            dropped_reasons=["live_reasoning_deferred_deterministic_baseline"],
            circuit_state=None,
        )
    validated = validate_investigation_plan(
        baseline,
        llm.proposal,
        llm_attempted=llm.attempted,
        capability_snapshot=snapshot,
    )
    trace = {
        "role": "investigation_planner",
        "authority": "advisory",
        "deterministic_validator": "accepted",
        "llm_attempted": llm.attempted,
        "llm_proposal_accepted": validated.plan_source == "llm_proposed_validated",
        "provider_label": llm.provider_label,
        "latency_ms": llm.latency_ms,
        "timed_out": llm.timed_out,
        "failure_kind": llm.failure_kind,
        "circuit_state": llm.circuit_state,
        "human_action_required": llm.human_action_required,
        "dropped_reasons": list(llm.dropped_reasons),
        # The planner is grounded on the Final RQC + deterministic baseline inside
        # the labelled trust boundary; no evidence rows, credentials or raw SPL.
        "case_data_sent_to_model": True,
        "capability_snapshot_present": bool(snapshot),
    }
    planned = {
        **state,
        "investigation_plan_proposal": dict(llm.proposal or {}),
        "validated_investigation_plan": validated.model_dump(mode="json"),
        "investigation_planning_trace": trace,
    }
    from app.chat.investigation_envelope_runtime import maybe_attach_investigation_approval

    return maybe_attach_investigation_approval(planned)
