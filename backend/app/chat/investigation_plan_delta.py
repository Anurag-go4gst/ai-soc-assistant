"""P7 deterministic PlanDelta validation and RP-hub state projection."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_plan import InvestigationCapabilityBinding
from app.chat.contracts.plan_delta import (
    PlanDeltaDecision,
    PlanDeltaProposal,
    ValidatedPlanDelta,
)
from app.chat.planned_mcp_call import (
    argument_template_for_tool,
    enrich_capability_bindings,
    playbook_purpose,
)
from app.config import settings
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments
from app.safeguards.spl_validator import validate_spl
from app.spl.rqc_constraint_preservation import apply_rqc_constraint_preservation


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


def _validated_execution_arguments(
    proposal: PlanDeltaProposal,
    *,
    envelope: ApprovedInvestigationEnvelope,
) -> tuple[dict[str, Any] | None, str | None]:
    """Bind a delta to an executable read-only call or fail closed.

    Splunk searches require approved normalized SPL. Catalogue metadata tools
    may bind only their declared argument template (no write/remediation path).
    """
    tool_name = proposal.capability_id.rsplit(":", 1)[-1]
    if tool_name in {"splunk_run_query", "run_splunk_query", "search_splunk"}:
        raw_spl = proposal.tool_arguments.get("normalized_spl") or proposal.tool_arguments.get("query")
        if not isinstance(raw_spl, str) or not raw_spl.strip():
            return None, "plan_delta_spl_missing"

        validation = validate_spl(raw_spl)
        validation = apply_rqc_constraint_preservation(
            validation,
            spl=raw_spl,
            resolved_query_contract={
                "entities": dict(envelope.entities),
                "time_scope": envelope.time_scope,
            },
        )
        if not isinstance(validation, dict) or validation.get("approved") is not True:
            return None, "plan_delta_spl_validation_failed"
        normalized_spl = str(validation.get("normalized_spl") or "").strip()
        if not normalized_spl:
            return None, "plan_delta_spl_validation_failed"

        approved_indexes = set(envelope.source_index_scope.get("indexes") or [])
        referenced_indexes = set(
            re.findall(r"\bindex\s*=\s*[\"']?([^\s|\"']+)", normalized_spl, flags=re.IGNORECASE)
        )
        if approved_indexes and not referenced_indexes.issubset(approved_indexes):
            return None, "plan_delta_spl_outside_approved_index_scope"

        planned = splunk_search_tool_arguments(normalized_spl=normalized_spl)
        return {
            **proposal.tool_arguments,
            **planned,
            "query": normalized_spl,
            "normalized_spl": normalized_spl,
        }, None

    template = argument_template_for_tool(tool_name)
    if template is None:
        return None, "plan_delta_capability_has_no_execution_binding"
    # Metadata / discovery tools: bind only template keys; reject write-shaped keys.
    forbidden = {"action", "command", "write", "delete", "create", "update"}
    if any(str(key).lower() in forbidden for key in proposal.tool_arguments):
        return None, "plan_delta_write_shaped_arguments_rejected"
    bound: dict[str, Any] = {}
    for key in template:
        if key in proposal.tool_arguments and proposal.tool_arguments[key] not in (None, ""):
            bound[key] = proposal.tool_arguments[key]
    # Empty-template tools (get_info / get_indexes) are valid with {}.
    return bound, None


def _append_delta_resource_step(
    state: dict[str, Any],
    *,
    delta: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Append one bounded call to the existing authoritative ResourcePlan."""
    evidence_plan = state.get("evidence_plan")
    if not isinstance(evidence_plan, dict):
        return None, "plan_delta_resource_plan_missing"
    resource_plan = evidence_plan.get("resource_plan")
    if not isinstance(resource_plan, dict) or not isinstance(resource_plan.get("steps"), list):
        return None, "plan_delta_resource_plan_missing"

    revision = int(delta["revision_number"])
    step_id = f"plan_delta_mcp_{revision}"
    if any(
        isinstance(step, dict) and str(step.get("step_id") or "") == step_id
        for step in resource_plan["steps"]
    ):
        return None, "duplicate_plan_delta_resource_step"
    tool_name = str(delta["capability_id"]).rsplit(":", 1)[-1]
    step = {
        "step_id": step_id,
        "resource_id": f"mcp_tool:{tool_name}",
        "purpose": playbook_purpose(tool_name) or "mcp_execution",
        "args_template": dict(delta["tool_arguments"]),
        "policy_checks": [
            "approved_investigation_envelope",
            "validated_plan_delta",
            "approved_normalized_spl_only",
            "exact_call_authorization",
        ],
        "status": "planned",
        "status_reason": None,
    }
    provenance = dict(resource_plan.get("provenance") or {})
    provenance["plan_delta_revision_fingerprints"] = [
        *list(provenance.get("plan_delta_revision_fingerprints") or []),
        str(delta["revision_fingerprint"]),
    ]
    appended_plan = {
        **resource_plan,
        "steps": [*resource_plan["steps"], step],
        "provenance": provenance,
    }
    return {
        **state,
        "evidence_plan": {**evidence_plan, "resource_plan": appended_plan},
        "active_resource_plan_step_id": step_id,
    }, None


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

    execution_arguments, binding_error = _validated_execution_arguments(
        proposal,
        envelope=envelope,
    )
    if execution_arguments is None:
        return PlanDeltaDecision(status="rejected", reason=str(binding_error))

    max_calls = int(envelope.budget.cost_resource_limits.get("max_tool_calls", envelope.budget.hop_limit))
    if len(prior_revisions) >= min(envelope.budget.hop_limit, max_calls):
        return PlanDeltaDecision(status="budget_exhausted", reason="plan_delta_hop_budget_exhausted")
    prior_fp = str(prior_revisions[-1].get("revision_fingerprint") or "") if prior_revisions else ""
    if prior_revisions and proposal.prior_revision_fingerprint != prior_fp:
        return PlanDeltaDecision(status="rejected", reason="prior_revision_fingerprint_mismatch")
    if not prior_revisions and proposal.prior_revision_fingerprint not in {None, ""}:
        return PlanDeltaDecision(status="rejected", reason="unexpected_prior_revision_fingerprint")

    proposal_payload = proposal.model_dump(mode="json")
    proposal_payload["tool_arguments"] = execution_arguments
    effective_payload = {
        key: value
        for key, value in proposal_payload.items()
        if key != "prior_revision_fingerprint"
    }
    effective_fp = _fingerprint(effective_payload)
    prior_effective = {
        str(item.get("effective_fingerprint") or "") for item in prior_revisions if isinstance(item, dict)
    }
    if effective_fp in prior_effective:
        return PlanDeltaDecision(status="no_progress", reason="duplicate_effective_plan_delta")
    revision_fp = _fingerprint({**effective_payload, "prior_revision_fingerprint": prior_fp})
    validated = ValidatedPlanDelta(
        **proposal_payload,
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
    if not settings.ai_soc_plan_delta_enabled:
        return {
            **state,
            "plan_delta_decision": PlanDeltaDecision(
                status="disabled", reason="plan_delta_disabled"
            ).model_dump(mode="json"),
        }

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
    bound_state, binding_error = _append_delta_resource_step(updated, delta=delta)
    if bound_state is None:
        failed = PlanDeltaDecision(status="rejected", reason=str(binding_error))
        return {
            **updated,
            "plan_delta_decision": failed.model_dump(mode="json"),
            "investigation_run_status": {
                **run_status,
                "next_action": "stop",
                "plan_delta_emitted": False,
                "stop_reason": str(binding_error),
            },
        }
    updated = bound_state
    updated["plan_delta_revisions"] = [*revisions, delta]
    # Re-bind planned MCP arguments onto the validated investigation plan when present.
    plan_raw = updated.get("validated_investigation_plan")
    approval = updated.get("investigation_approval") if isinstance(updated.get("investigation_approval"), dict) else {}
    if not isinstance(plan_raw, dict):
        plan_raw = approval.get("validated_plan") if isinstance(approval.get("validated_plan"), dict) else None
    if isinstance(plan_raw, dict) and isinstance(plan_raw.get("capability_bindings"), list):
        bindings = []
        for raw in plan_raw.get("capability_bindings") or []:
            if not isinstance(raw, dict):
                continue
            binding = InvestigationCapabilityBinding.model_validate(raw)
            if binding.capability_id == delta["capability_id"]:
                planned = dict(delta.get("tool_arguments") or {})
                binding = binding.model_copy(
                    update={
                        "planned_arguments": planned,
                        "unresolved_arguments": [],
                        "purpose": binding.purpose
                        or playbook_purpose(binding.capability_id.rsplit(":", 1)[-1]),
                        "authorization_posture": "exact_call_auth0_grant_required",
                    }
                )
            bindings.append(binding)
        enriched = enrich_capability_bindings(
            bindings,
            normalized_spl=str((delta.get("tool_arguments") or {}).get("normalized_spl") or "")
            or None,
        )
        plan_raw = {
            **plan_raw,
            "capability_bindings": [item.model_dump(mode="json") for item in enriched],
        }
        updated["validated_investigation_plan"] = plan_raw
        if approval:
            updated["investigation_approval"] = {
                **approval,
                "validated_plan": plan_raw,
            }
    updated["plan_delta_execution_request"] = {
        "revision_fingerprint": delta["revision_fingerprint"],
        "capability_id": delta["capability_id"],
        "tool_arguments": delta["tool_arguments"],
        "validated_spl": delta["tool_arguments"].get("normalized_spl"),
        "resource_plan_step_id": updated["active_resource_plan_step_id"],
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


def observe_plan_delta_execution(state: dict[str, Any]) -> dict[str, Any]:
    """Accumulate one completed delta call into EvidenceState metadata.

    Raw rows remain on the governed execution/SourceEvidence channels. This
    observer records only that the approved evidence category was checked.
    Failed, blocked, or unavailable calls leave the category missing.
    """
    request = state.get("plan_delta_execution_request")
    execution = state.get("execution")
    if not isinstance(request, dict) or not isinstance(execution, dict):
        return state
    if request.get("observed") is True:
        return state
    status = str(execution.get("status") or "").lower()
    if status not in {
        "executed",
        "executed_mock_evidence",
        "executed_live_evidence",
        "success",
    }:
        return {
            **state,
            "plan_delta_execution_request": {
                **request,
                "observed": True,
                "observation_status": "unavailable_or_blocked",
            },
        }

    evidence_need = str(request.get("evidence_need") or "").strip()
    if not evidence_need:
        return state
    current = state.get("evidence_state")
    evidence_state = dict(current) if isinstance(current, dict) else {}
    obtained = list(dict.fromkeys([*list(evidence_state.get("obtained") or []), evidence_need]))
    missing = [
        str(item)
        for item in evidence_state.get("missing") or []
        if str(item) != evidence_need
    ]
    items = [
        dict(item)
        for item in evidence_state.get("items") or []
        if isinstance(item, dict) and str(item.get("key") or "") != evidence_need
    ]
    items.append(
        {
            "key": evidence_need,
            "status": "obtained",
            "provenance": f"plan_delta:{request.get('revision_fingerprint')}",
            "trust_class": "untrusted_evidence",
            "scope": {"resource_plan_step_id": request.get("resource_plan_step_id")},
            "observed_at": None,
            "freshness": None,
            "applicability": "current_envelope",
        }
    )
    return {
        **state,
        "evidence_state": {
            **evidence_state,
            "obtained": obtained,
            "missing": missing,
            "items": items,
        },
        "plan_delta_execution_request": {
            **request,
            "observed": True,
            "observation_status": "obtained",
        },
    }
