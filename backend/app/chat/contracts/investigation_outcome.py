"""Minimal governed InvestigationOutcome — projection after EVIDENCE sufficiency.

Plan 8 OUT0. Not a competing authority with CanonicalFacts, FinalEvidenceGate,
GovernedSynthesisPackage, CanonicalPlanningOutcome, or DecisionRecord.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.actions.capability_policy import ActionCapability, BLOCKED_EXECUTION_ACTIONS

SCHEMA_VERSION = "investigation_outcome_v1"
SCHEMA_VERSION_V2 = "investigation_outcome_v2"

Disposition = Literal["suspicious", "benign", "inconclusive", "blocked"]
SecurityDisposition = Literal["suspicious", "benign", "inconclusive"]
InvestigationStatus = Literal["completed", "incomplete", "blocked", "cancelled"]
_HIGH_SEVERITY = ("P1", "P2")


class InvestigationOutcome(BaseModel):
    schema_version: str = SCHEMA_VERSION
    disposition: Disposition
    findings: list[str] = Field(default_factory=list)
    supported_hypotheses: list[str] = Field(default_factory=list)
    unconfirmed_hypotheses: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    severity_label: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    action_eligibility: dict[str, Any] = Field(default_factory=dict)
    policy_eligibility: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    llm_proposal_accepted: bool = False


class InvestigationOutcomeV2(BaseModel):
    """P8 presentation projection; it carries no planning or action authority."""

    schema_version: str = SCHEMA_VERSION_V2
    investigation_status: InvestigationStatus
    disposition: SecurityDisposition
    findings: list[str] = Field(default_factory=list)
    supported_hypotheses: list[str] = Field(default_factory=list)
    unconfirmed_hypotheses: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    remediation_offer_required: bool = False
    severity_label: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    action_eligibility: dict[str, Any] = Field(default_factory=dict)
    policy_eligibility: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    llm_proposal_accepted: bool = False


def derive_investigation_outcome(
    *,
    trace_id: str | None = None,
    evidence_state: dict[str, Any] | None = None,
    evidence_sufficiency: dict[str, Any] | None = None,
    context_sufficiency: dict[str, Any] | None = None,
    final_evidence_gate: dict[str, Any] | None = None,
    canonical_facts: dict[str, Any] | None = None,
    structured_context: dict[str, Any] | None = None,
    human_review: dict[str, Any] | None = None,
    severity_label: str | None = None,
    action_capability: ActionCapability | dict[str, Any] | None = None,
    llm_proposal: dict[str, Any] | None = None,
    investigation_run_status: dict[str, Any] | None = None,
    investigation_approval: dict[str, Any] | None = None,
    resolved_query_contract: dict[str, Any] | None = None,
    outcome_v2_enabled: bool = False,
) -> InvestigationOutcome | InvestigationOutcomeV2:
    """Deterministic outcome from existing governed packages. LLM proposal is advisory."""
    evidence = evidence_state if isinstance(evidence_state, dict) else {}
    sufficiency = evidence_sufficiency if isinstance(evidence_sufficiency, dict) else {}
    context = context_sufficiency if isinstance(context_sufficiency, dict) else {}
    gate = final_evidence_gate if isinstance(final_evidence_gate, dict) else {}
    facts = canonical_facts if isinstance(canonical_facts, dict) else {}
    structured = structured_context if isinstance(structured_context, dict) else {}
    review = human_review if isinstance(human_review, dict) else {}
    run_status = investigation_run_status if isinstance(investigation_run_status, dict) else {}
    approval = investigation_approval if isinstance(investigation_approval, dict) else {}
    resolved_query = resolved_query_contract if isinstance(resolved_query_contract, dict) else {}
    capability = _capability_payload(action_capability)

    disposition = _disposition(
        sufficiency=sufficiency,
        context=context,
        review=review,
        evidence=evidence,
        facts=facts,
        gate=gate,
        severity_label=severity_label,
    )
    findings = [
        str(fact.get("statement"))
        for fact in structured.get("structured_facts") or []
        if isinstance(fact, dict) and fact.get("statement") and fact.get("source_refs")
    ]
    missing = list(sufficiency.get("missing") or evidence.get("missing") or structured.get("missing_evidence") or [])
    refs = list(gate.get("collected_evidence_refs") or structured.get("source_evidence_refs") or [])
    recommended = [str(item) for item in capability.get("allowed_actions") or [] if str(item) not in BLOCKED_EXECUTION_ACTIONS]
    common: dict[str, Any] = {
        "disposition": disposition,
        "findings": findings,
        "supported_hypotheses": [],
        "unconfirmed_hypotheses": [],
        "evidence_refs": [str(item) for item in refs],
        "missing_evidence": [str(item) for item in missing],
        "severity_label": severity_label,
        "recommended_actions": recommended,
        "action_eligibility": {
            "allowed_actions": list(capability.get("allowed_actions") or []),
            "unavailable_actions": list(capability.get("unavailable_actions") or []),
            "hil_required": bool(capability.get("hil_required")),
            "current_tier": capability.get("current_tier"),
        },
        "policy_eligibility": {
            "synthesis_allowed": False,
            "human_review_required": bool(review.get("required")),
            "evidence_sufficiency": sufficiency.get("status"),
            "next_action": sufficiency.get("next_action"),
        },
        "provenance": {
            "trace_id": trace_id,
            "derived_from": [
                name
                for name, present in (
                    ("evidence_state", bool(evidence)),
                    ("evidence_sufficiency", bool(sufficiency)),
                    ("final_evidence_gate", bool(gate)),
                    ("canonical_facts", bool(facts)),
                    ("action_capability", bool(capability)),
                )
                if present
            ],
            "not_canonical_planning_outcome": True,
            "not_decision_record": True,
        },
    }
    if outcome_v2_enabled:
        common["disposition"] = "inconclusive" if disposition == "blocked" else disposition
        outcome: InvestigationOutcome | InvestigationOutcomeV2 = InvestigationOutcomeV2(
            investigation_status=_investigation_status(
                sufficiency=sufficiency,
                context=context,
                review=review,
                run_status=run_status,
                approval=approval,
            ),
            limitations=_limitations(
                missing=missing,
                context=context,
                run_status=run_status,
            ),
            recommended_next_action=_recommended_next_action(
                sufficiency=sufficiency,
                run_status=run_status,
            ),
            remediation_offer_required=not _rqc_requests_remediation(resolved_query)
            and str(approval.get("status") or "") != "cancelled",
            **common,
        )
    else:
        outcome = InvestigationOutcome(**common)
    return apply_llm_outcome_proposal(outcome, llm_proposal)


def apply_llm_outcome_proposal(
    outcome: InvestigationOutcome | InvestigationOutcomeV2,
    proposal: dict[str, Any] | None,
) -> InvestigationOutcome | InvestigationOutcomeV2:
    """Accept only schema-valid findings that cite existing evidence refs.

    Disposition, severity, policy, and action eligibility stay deterministic.
    """
    if not isinstance(proposal, dict):
        return outcome
    allowed_refs = set(outcome.evidence_refs)
    proposed_findings: list[str] = []
    for item in proposal.get("findings") or []:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("claim") or "").strip()
            refs = [str(ref) for ref in (item.get("evidence_refs") or [])]
            if text and refs and set(refs) <= allowed_refs:
                proposed_findings.append(text)
        elif isinstance(item, str) and item.strip() and allowed_refs:
            continue
    hypotheses: list[str] = []
    for item in proposal.get("hypotheses") or proposal.get("supported_hypotheses") or []:
        text = str(item).strip()
        if text:
            hypotheses.append(text)
    if not proposed_findings and not hypotheses:
        return outcome.model_copy(update={"llm_proposal_accepted": False})
    return outcome.model_copy(
        update={
            "findings": list(outcome.findings) + proposed_findings,
            "unconfirmed_hypotheses": hypotheses,
            "llm_proposal_accepted": True,
            "disposition": outcome.disposition,
            "severity_label": outcome.severity_label,
            "recommended_actions": outcome.recommended_actions,
            "action_eligibility": outcome.action_eligibility,
            "policy_eligibility": outcome.policy_eligibility,
        }
    )


def actions_from_investigation_outcome(
    outcome: InvestigationOutcome | InvestigationOutcomeV2 | dict[str, Any],
) -> list[str]:
    """Action preparation reads governed eligibility, never free-form prose."""
    payload = (
        outcome.model_dump()
        if isinstance(outcome, (InvestigationOutcome, InvestigationOutcomeV2))
        else outcome
    )
    eligibility = payload.get("action_eligibility") if isinstance(payload, dict) else {}
    allowed = [str(item) for item in (eligibility or {}).get("allowed_actions") or []]
    return [item for item in allowed if item not in BLOCKED_EXECUTION_ACTIONS]


def _capability_payload(action_capability: ActionCapability | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(action_capability, ActionCapability):
        return action_capability.model_dump()
    if isinstance(action_capability, dict):
        return action_capability
    return {}


def _disposition(
    *,
    sufficiency: dict[str, Any],
    context: dict[str, Any],
    review: dict[str, Any],
    evidence: dict[str, Any],
    facts: dict[str, Any],
    gate: dict[str, Any],
    severity_label: str | None,
) -> Disposition:
    if sufficiency.get("status") == "BLOCKED" or context.get("status") == "blocked_by_policy":
        return "blocked"
    if bool(review.get("required")) and str(review.get("review_type") or "") in {"policy", "blocked_by_policy"}:
        return "blocked"
    kinds = {
        str(fact.get("kind"))
        for fact in facts.get("facts") or []
        if isinstance(fact, dict)
    }
    obtained = [str(item) for item in evidence.get("obtained") or []]
    if "negative_evidence" in kinds and not obtained:
        return "benign"
    label = str(severity_label or "")
    live = bool(gate.get("allow_live_result_language"))
    if live and obtained and any(tag in label for tag in _HIGH_SEVERITY):
        return "suspicious"
    return "inconclusive"


def _investigation_status(
    *,
    sufficiency: dict[str, Any],
    context: dict[str, Any],
    review: dict[str, Any],
    run_status: dict[str, Any],
    approval: dict[str, Any],
) -> InvestigationStatus:
    approval_status = str(approval.get("status") or "").lower()
    if approval_status == "cancelled":
        return "cancelled"
    run_value = str(run_status.get("status") or "").lower()
    sufficiency_value = str(sufficiency.get("status") or "").upper()
    if (
        run_value == "blocked"
        or sufficiency_value == "BLOCKED"
        or context.get("status") == "blocked_by_policy"
        or (
            bool(review.get("required"))
            and str(review.get("review_type") or "") in {"policy", "blocked_by_policy"}
        )
    ):
        return "blocked"
    if run_value in {"completed", "sufficient"} or sufficiency_value == "SUFFICIENT":
        return "completed"
    return "incomplete"


def _limitations(
    *,
    missing: list[Any],
    context: dict[str, Any],
    run_status: dict[str, Any],
) -> list[str]:
    values = [f"Missing governed evidence: {item}" for item in missing if str(item).strip()]
    stop_reason = str(run_status.get("stop_reason") or "").strip()
    if stop_reason:
        values.append(f"Investigation stopped: {stop_reason}")
    for reason in context.get("reasons") or []:
        if str(reason).strip():
            values.append(str(reason))
    return list(dict.fromkeys(values))


def _recommended_next_action(
    *,
    sufficiency: dict[str, Any],
    run_status: dict[str, Any],
) -> str | None:
    value = run_status.get("next_action") or sufficiency.get("next_action")
    return str(value).strip() if value is not None and str(value).strip() else None


def _rqc_requests_remediation(resolved_query: dict[str, Any]) -> bool:
    """Recognize an explicit/conditional remediation request without granting it."""
    searchable: list[str] = []
    for key in ("normalized_goal", "answer_goal"):
        value = resolved_query.get(key)
        if isinstance(value, (list, tuple, set, frozenset)):
            searchable.extend(str(item) for item in value)
        elif value is not None:
            searchable.append(str(value))
    provenance = resolved_query.get("provenance")
    if isinstance(provenance, dict):
        for key in ("original_query", "requested_outcomes", "remediation_request"):
            value = provenance.get(key)
            if isinstance(value, (list, tuple, set, frozenset)):
                searchable.extend(str(item) for item in value)
            elif value is not None:
                searchable.append(str(value))
    text = " ".join(searchable).lower()
    return any(
        marker in text
        for marker in (
            "remediat",
            "contain",
            "isolate",
            "block the",
            "disable the",
            "patch the",
            "create a ticket",
        )
    )
