"""P3 runtime seam: Final RQC + CapabilitySnapshot -> validated plan.

The LLM proposal is optional and advisory. Case data never crosses the P3 model
boundary; deterministic code preserves Final-RQC facts and binds only rows from
CapabilitySnapshot.
"""

from __future__ import annotations

from typing import Any

from app.chat.guided_investigation_plan_llm import propose_investigation_plan_llm
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.config import settings


def maybe_attach_validated_investigation_plan(state: dict[str, Any]) -> dict[str, Any]:
    """Attach P3 planning artifacts on the P0 investigation wait-state."""
    if not settings.ai_soc_investigation_planner_enabled:
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
    llm = propose_investigation_plan_llm(query=query, baseline=baseline)
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
        "case_data_sent_to_model": False,
        "capability_snapshot_present": bool(snapshot),
    }
    return {
        **state,
        "investigation_plan_proposal": dict(llm.proposal or {}),
        "validated_investigation_plan": validated.model_dump(mode="json"),
        "investigation_planning_trace": trace,
    }
