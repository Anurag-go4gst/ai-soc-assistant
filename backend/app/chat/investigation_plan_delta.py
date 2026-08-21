"""P7 deterministic PlanDelta validation and RP-hub state projection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.plan_delta import (
    PlanDeltaDecision,
    PlanDeltaProposal,
    ValidatedPlanDelta,
)
from app.config import settings


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scope_is_subset(proposed: dict[str, list[str]], approved: dict[str, list[str]]) -> bool:
    for key, values in proposed.items():
        if not set(values).issubset(set(approved.get(key) or [])):
            return False
    return True


def _available_capabilities(snapshot: dict[str, Any]) -> set[str]:
    return {
        str(row.get("capability_id"))
        for row in snapshot.get("rows") or []
        if isinstance(row, dict) and row.get("availability") == "available"
    }


def validate_plan_delta(
    proposal: PlanDeltaProposal,
    *,
    envelope: ApprovedInvestigationEnvelope,
    capability_snapshot: dict[str, Any],
    missing_evidence: list[str],
    prior_revisions: list[dict[str, Any]],
) -> PlanDeltaDecision:
    """Apply the immutable envelope, capability, budget and no-progress rules."""
    if proposal.access_mode == "write":
        return PlanDeltaDecision(
            status="remediation_recommended",
            reason="writes_are_not_investigation_plan_delta",
            remediation_recommendation="Create a separately approved remediation plan.",
        )
    if proposal.envelope_version != envelope.envelope_version:
        return PlanDeltaDecision(status="rejected", reason="envelope_version_mismatch")
    if proposal.objective.strip() != envelope.objective.strip():
        return PlanDeltaDecision(status="hil_required", reason="material_objective_expansion")
    if proposal.targets and not set(proposal.targets).issubset(set(envelope.targets)):
        return PlanDeltaDecision(status="hil_required", reason="material_target_expansion")
    if proposal.entities and proposal.entities != envelope.entities:
        return PlanDeltaDecision(status="hil_required", reason="material_entity_expansion")
    if proposal.time_scope and proposal.time_scope != envelope.time_scope:
        return PlanDeltaDecision(status="hil_required", reason="material_time_expansion")
    if proposal.source_index_scope and not _scope_is_subset(
        proposal.source_index_scope, envelope.source_index_scope
    ):
        return PlanDeltaDecision(status="hil_required", reason="material_source_scope_expansion")
    if not envelope.plan_delta_policy.automatic_bounded_read_only_delta_allowed:
        return PlanDeltaDecision(status="hil_required", reason="automatic_plan_delta_not_approved")
    if proposal.capability_id not in set(envelope.allowed_read_only_capabilities):
        return PlanDeltaDecision(status="rejected", reason="capability_outside_envelope")
    if proposal.capability_id not in _available_capabilities(capability_snapshot):
        return PlanDeltaDecision(status="rejected", reason="capability_not_available_on_snapshot")
    if proposal.evidence_need not in set(missing_evidence):
        return PlanDeltaDecision(status="rejected", reason="delta_not_targeted_to_current_gap")

    max_calls = int(envelope.budget.cost_resource_limits.get("max_tool_calls", envelope.budget.hop_limit))
    if len(prior_revisions) >= min(envelope.budget.hop_limit, max_calls):
        return PlanDeltaDecision(status="budget_exhausted", reason="plan_delta_hop_budget_exhausted")
    prior_fp = str(prior_revisions[-1].get("revision_fingerprint") or "") if prior_revisions else ""
    if prior_revisions and proposal.prior_revision_fingerprint != prior_fp:
        return PlanDeltaDecision(status="rejected", reason="prior_revision_fingerprint_mismatch")
    if not prior_revisions and proposal.prior_revision_fingerprint not in {None, ""}:
        return PlanDeltaDecision(status="rejected", reason="unexpected_prior_revision_fingerprint")

    effective_payload = proposal.model_dump(mode="json", exclude={"prior_revision_fingerprint"})
    effective_fp = _fingerprint(effective_payload)
    prior_effective = {
        str(item.get("effective_fingerprint") or "") for item in prior_revisions if isinstance(item, dict)
    }
    if effective_fp in prior_effective:
        return PlanDeltaDecision(status="no_progress", reason="duplicate_effective_plan_delta")
    revision_fp = _fingerprint({**effective_payload, "prior_revision_fingerprint": prior_fp})
    validated = ValidatedPlanDelta(
        **proposal.model_dump(mode="json"),
        revision_number=len(prior_revisions) + 1,
        revision_fingerprint=revision_fp,
        effective_fingerprint=effective_fp,
    )
    return PlanDeltaDecision(status="accepted", reason="bounded_read_only_delta_validated", validated_delta=validated)


def attach_plan_delta_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Reason and validate one bounded revision; execution remains with the RP hub."""
    envelope_raw = state.get("approved_investigation_envelope")
    if not isinstance(envelope_raw, dict):
        return state
    if not settings.ai_soc_investigation_planner_enabled:
        return {**state, "plan_delta_decision": PlanDeltaDecision(status="disabled", reason="investigation_reasoning_disabled").model_dump(mode="json")}

    run_status = state.get("investigation_run_status") if isinstance(state.get("investigation_run_status"), dict) else {}
    missing = [str(item) for item in run_status.get("missing_evidence") or []]
    proposal_raw = state.get("plan_delta_proposal")
    reasoning_trace: dict[str, Any]
    if not isinstance(proposal_raw, dict):
        from app.chat.investigation_plan_delta_reasoner import propose_plan_delta

        revisions = [item for item in state.get("plan_delta_revisions") or [] if isinstance(item, dict)]
        result = propose_plan_delta(
            envelope=ApprovedInvestigationEnvelope.model_validate(envelope_raw),
            missing_evidence=missing,
            prior_revision_fingerprint=(
                str(revisions[-1].get("revision_fingerprint") or "") if revisions else None
            ),
            turn_budget=state.get("llm_turn_budget"),
        )
        proposal_raw = result.proposal
        reasoning_trace = result.trace
    else:
        reasoning_trace = {"role": "plan_delta_reasoner", "provider": "test_or_recorded", "authority": "advisory"}
    if not isinstance(proposal_raw, dict):
        decision = PlanDeltaDecision(status="reasoner_unavailable", reason="no_valid_plan_delta_proposal")
        return {**state, "plan_delta_decision": decision.model_dump(mode="json"), "plan_delta_reasoning_trace": reasoning_trace}

    try:
        proposal = PlanDeltaProposal.model_validate(proposal_raw)
    except Exception as exc:
        decision = PlanDeltaDecision(status="rejected", reason=f"proposal_schema_invalid:{type(exc).__name__}")
        return {**state, "plan_delta_decision": decision.model_dump(mode="json"), "plan_delta_reasoning_trace": reasoning_trace}
    revisions = [item for item in state.get("plan_delta_revisions") or [] if isinstance(item, dict)]
    decision = validate_plan_delta(
        proposal,
        envelope=ApprovedInvestigationEnvelope.model_validate(envelope_raw),
        capability_snapshot=state.get("capability_snapshot") if isinstance(state.get("capability_snapshot"), dict) else {},
        missing_evidence=missing,
        prior_revisions=revisions,
    )
    updated = {
        **state,
        "plan_delta_decision": decision.model_dump(mode="json"),
        "plan_delta_reasoning_trace": reasoning_trace,
    }
    if decision.status != "accepted" or decision.validated_delta is None:
        status = dict(run_status)
        status.update({"next_action": "stop", "plan_delta_emitted": False, "stop_reason": decision.reason})
        if decision.status == "remediation_recommended":
            updated["remediation_recommendation"] = decision.remediation_recommendation
        updated["investigation_run_status"] = status
        return updated

    delta = decision.validated_delta.model_dump(mode="json")
    updated["plan_delta_revisions"] = [*revisions, delta]
    updated["plan_delta_execution_request"] = {
        "revision_fingerprint": delta["revision_fingerprint"],
        "capability_id": delta["capability_id"],
        "tool_arguments": delta["tool_arguments"],
        "evidence_need": delta["evidence_need"],
        "exact_call_authorization_required": True,
        "execution_authorized": False,
    }
    updated["plan_delta_proposal"] = None
    updated["execution"] = None
    updated["candidate_spl"] = None
    updated["spl_validation"] = None
    updated["investigation_run_status"] = {
        **run_status,
        "status": "incomplete",
        "stop_reason": None,
        "next_action": "execute_bounded_read_only_step",
        "plan_delta_emitted": True,
    }
    return updated
