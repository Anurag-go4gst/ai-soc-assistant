"""Minimal governed InvestigationOutcome — projection after EVIDENCE sufficiency.

Plan 8 OUT0. Not a competing authority with CanonicalFacts, FinalEvidenceGate,
GovernedSynthesisPackage, CanonicalPlanningOutcome, or DecisionRecord.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.actions.capability_policy import ActionCapability, BLOCKED_EXECUTION_ACTIONS
from app.chat.hypothesis_assessment import public_hypothesis_lists
from app.chat.investigation_shaped import investigation_outcome_applicable
from app.chat.analyst_missing_evidence import (
    analyst_limitations,
    project_missing_evidence,
)


SCHEMA_VERSION = "investigation_outcome_v1"
SCHEMA_VERSION_V2 = "investigation_outcome_v2"

Disposition = Literal["suspicious", "benign", "inconclusive", "blocked"]
SecurityDisposition = Literal["suspicious", "benign", "inconclusive"]
InvestigationStatus = Literal["completed", "incomplete", "blocked", "cancelled"]
_HIGH_SEVERITY = ("P1", "P2")
_ENVIRONMENT_OBTAINED_KEYS = frozenset(
    {
        "mcp",
        "endpoint",
        "process_execution",
        "auth",
        "identity",
        "network_flows",
        "firewall_sessions",
        "dns",
        "egress_flows",
        "executed_evidence",
    }
)


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
    investigation_plan: dict[str, Any] | None = None,
    hypothesis_assessments: dict[str, Any] | None = None,
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
    if "missing" in sufficiency:
        missing = list(sufficiency.get("missing") or [])
    elif "missing" in evidence:
        missing = list(evidence.get("missing") or [])
    else:
        missing = list(structured.get("missing_evidence") or [])
    if isinstance(gate, dict) and "collected_evidence_refs" in gate:
        refs = list(gate.get("collected_evidence_refs") or [])
    else:
        refs = list(structured.get("source_evidence_refs") or [])
    recommended = [str(item) for item in capability.get("allowed_actions") or [] if str(item) not in BLOCKED_EXECUTION_ACTIONS]
    # Analyst-facing projection of the internal missing-evidence set. Internal
    # control keys stay in the internal contracts above; they are not evidence
    # gaps a responder can act on.
    analyst_missing, source_unavailable = project_missing_evidence(
        missing,
        spl_requested=_spl_artifact_requested(resolved_query),
        knowledge_contract_required=_knowledge_contract_required(resolved_query),
    )
    supported_hypotheses, unconfirmed_hypotheses = _classify_hypotheses(
        plan=investigation_plan if isinstance(investigation_plan, dict) else {},
        resolved_query=resolved_query,
        evidence=evidence,
        findings=findings,
        hypothesis_assessments=hypothesis_assessments
        if isinstance(hypothesis_assessments, dict)
        else None,
    )
    common: dict[str, Any] = {
        "disposition": disposition,
        "findings": findings,
        "supported_hypotheses": supported_hypotheses,
        "unconfirmed_hypotheses": unconfirmed_hypotheses,
        "evidence_refs": [str(item) for item in refs],
        "missing_evidence": analyst_missing,
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
    if isinstance(hypothesis_assessments, dict) and hypothesis_assessments.get("items"):
        common["provenance"]["hypothesis_assessment"] = {
            "schema_version": hypothesis_assessments.get("schema_version"),
            "evidence_fingerprint": hypothesis_assessments.get("evidence_fingerprint"),
            "items": hypothesis_assessments.get("items"),
            "history": hypothesis_assessments.get("history") or [],
            "evolution_summary": hypothesis_assessments.get("evolution_summary") or "",
        }
    if outcome_v2_enabled:
        # Final RQC product applicability: InvestigationOutcome V2 (investigation_status,
        # remediation_offer_required, recommended_next_action) applies only to
        # investigation-shaped Final RQCs. SPL authoring / knowledge / MITRE-only
        # products must not inherit blocked/incomplete investigation packaging merely
        # because MCP/evidence is unavailable or T4 ran.
        if not investigation_outcome_applicable(
            resolved_query_contract=resolved_query,
            context_sufficiency=context,
        ):
            if disposition == "blocked":
                common["disposition"] = "inconclusive"
            common["provenance"] = {
                **common["provenance"],
                "investigation_outcome_applicable": False,
                "investigation_outcome_suppressed_reason": "final_rqc_not_investigation_shaped",
            }
            outcome = InvestigationOutcome(**common)
        else:
            common["disposition"] = "inconclusive" if disposition == "blocked" else disposition
            outcome = InvestigationOutcomeV2(
                investigation_status=_investigation_status(
                    sufficiency=sufficiency,
                    context=context,
                    review=review,
                    run_status=run_status,
                    approval=approval,
                ),
                limitations=_limitations(
                    missing=analyst_missing,
                    source_unavailable=source_unavailable,
                    context=context,
                    run_status=run_status,
                ),
                recommended_next_action=_analyst_next_action(
                    missing=analyst_missing,
                    unconfirmed=unconfirmed_hypotheses,
                    source_unavailable=source_unavailable,
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



#: Evidence keys that are internal control state, never environment observation.
#: A hypothesis is not corroborated by the fact that a RAG lookup ran.
_NON_ENVIRONMENT_EVIDENCE_KEYS = frozenset({"rag", "rag:sop", "spl", "mcp", "collected_source_evidence"})


def _classify_hypotheses(
    *,
    plan: dict[str, Any],
    resolved_query: dict[str, Any],
    evidence: dict[str, Any],
    findings: list[str],
    hypothesis_assessments: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Carry the investigation's competing hypotheses into the outcome.

    Hypotheses are analytical state, not environment facts: they are never
    SourceEvidence and never become findings. They come from the approved plan
    (which already merges the T4 competing hypotheses and the planner's), so a
    hypothesis surviving here is continuity, not a new claim.

    Promotion to SUPPORTED requires admitted environment SourceEvidence. A
    hypothesis is never supported because the user asserted it, because T4 or the
    planner proposed it, or because RAG mentioned it — those are the inputs, not
    corroboration. With no admitted environment evidence every hypothesis stays
    UNCONFIRMED, which is the honest answer, not an empty list.

    When a DET-validated hypothesis_assessments package is present, it is the
    classification authority. Weakened remains unconfirmed on this public contract.
    """
    hypotheses: list[str] = []
    for source in (plan.get("hypotheses"), resolved_query.get("competing_hypotheses")):
        for item in source or []:
            text = str(item or "").strip()
            if text and text not in hypotheses:
                hypotheses.append(text)
    if not hypotheses:
        return [], []

    if isinstance(hypothesis_assessments, dict) and hypothesis_assessments.get("items"):
        supported, unconfirmed = public_hypothesis_lists(hypothesis_assessments)
        if supported or unconfirmed:
            return supported, unconfirmed

    obtained = {
        str(key)
        for key in (evidence.get("obtained") or [])
        if str(key) not in _NON_ENVIRONMENT_EVIDENCE_KEYS
    }
    if not obtained or not findings:
        # No admitted environment evidence, or nothing grounded in it: everything
        # the investigation was weighing remains open.
        return [], hypotheses

    # With admitted environment evidence, a hypothesis is supported only when a
    # grounded finding (statement carrying source_refs) actually states it. No
    # fuzzy inference: the finding must contain the hypothesis text.
    grounded = " ".join(findings).lower()
    supported = [item for item in hypotheses if item.lower() in grounded]
    unconfirmed = [item for item in hypotheses if item not in supported]
    return supported, unconfirmed


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
    environment_obtained = bool(set(obtained) & _ENVIRONMENT_OBTAINED_KEYS)
    if not environment_obtained and gate.get("collected_evidence_refs") and gate.get(
        "allow_environment_fact_claims"
    ):
        environment_obtained = True
    sufficiency_complete = str(sufficiency.get("status") or "").upper() == "SUFFICIENT"
    high_severity = any(tag in str(severity_label or "") for tag in _HIGH_SEVERITY)
    live_environment = bool(
        gate.get("allow_environment_fact_claims") or gate.get("allow_live_result_language")
    )
    # Disposition is the security finding. Severity is independent. Presentation
    # language (`allow_live_result_language`) must not be the only way to name
    # obtained environment evidence as suspicious.
    if environment_obtained and (sufficiency_complete or (live_environment and high_severity)):
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



def _spl_artifact_requested(resolved_query: dict[str, Any]) -> bool:
    """True when the analyst's requested DELIVERABLE is an SPL artifact.

    Keyed on the answer goal only. A required SPL *capability* means the
    investigation may need a search internally, which is a tool need and not
    something the analyst asked us to hand them -- reporting "a validated SPL
    artifact" as a missing evidence item on an investigation is misleading.
    """
    return str(resolved_query.get("answer_goal") or "").lower() == "spl_artifact"


def _knowledge_contract_required(resolved_query: dict[str, Any]) -> bool:
    """True when the governed contract makes knowledge/SOP guidance the answer."""
    family = str(resolved_query.get("intent_family") or "").lower()
    goal = str(resolved_query.get("answer_goal") or "").lower()
    return "knowledge" in family or "knowledge" in goal or "sop" in goal



def _limitations(
    *,
    missing: list[Any],
    source_unavailable: bool,
    context: dict[str, Any],
    run_status: dict[str, Any],
) -> list[str]:
    values = analyst_limitations(
        [str(item) for item in missing if str(item).strip()],
        source_unavailable=source_unavailable,
    )
    # Sufficiency reasons are a mix of analyst-readable prose ("MCP execution
    # disabled") and internal control codes ("no_collected_evidence",
    # "evidence_origin:stub_rag"). Keep the prose -- it explains the limitation --
    # and drop the codes, which only repeat in machine words a gap already stated
    # above in analyst language.
    for reason in context.get("reasons") or []:
        text = str(reason).strip()
        if text and not _is_internal_code(text):
            values.append(text)
    stop_reason = str(run_status.get("stop_reason") or "").strip()
    if stop_reason:
        if _is_internal_code(stop_reason):
            values.append(
                "The investigation stopped before reaching a conclusion; the "
                "evidence above is still required."
            )
        else:
            values.append(f"Investigation stopped: {stop_reason}")
    return list(dict.fromkeys(values))


def _is_internal_code(text: str) -> bool:
    """An identifier-shaped token (snake_case / colon-delimited), not analyst prose."""
    return " " not in text.strip()



def _analyst_next_action(
    *,
    missing: list[str],
    unconfirmed: list[str],
    source_unavailable: bool,
    sufficiency: dict[str, Any],
    run_status: dict[str, Any],
) -> str | None:
    """The next investigative step for the analyst, not the internal control verdict.

    Internal control still decides STOP / BLOCK / DEGRADE and keeps that decision on
    ``investigation_run_status.next_action``. "stop" is a correct execution decision
    and useless SOC advice, so the analyst-facing line is derived from canonical
    state instead: the material evidence gap, the hypotheses it would separate, and
    the decision that would unlock.

    Composed only from evidence the investigation already declared missing, so it
    can neither claim a finding nor imply anything was collected. It recommends
    reading, never writing.
    """
    # Only analyst-readable concepts may appear here. An identifier-shaped residue
    # ("mcp_rows") is internal plumbing and must never become "Collect mcp_rows".
    readable = [item for item in missing if " " in str(item).strip()]
    if not readable:
        return _recommended_next_action(sufficiency=sufficiency, run_status=run_status)

    primary = readable[0]
    supporting = readable[1:3]
    what = f"Collect {primary}"
    if supporting:
        what += " together with " + " and ".join(supporting)
    what += "."

    if len(unconfirmed) >= 2:
        why = (
            f" This is the highest-value next step because it is the evidence that "
            f"separates \u201c{_trim(unconfirmed[0])}\u201d from \u201c{_trim(unconfirmed[1])}\u201d, "
            "which no currently held evidence can distinguish."
        )
    elif unconfirmed:
        why = (
            f" This is the highest-value next step because \u201c{_trim(unconfirmed[0])}\u201d "
            "remains unconfirmed and nothing currently held can corroborate it."
        )
    else:
        why = " This is the highest-value next step because no environment evidence has been collected yet."

    decision = (
        " Establishing it would determine whether the reported events form one "
        "activity chain, and therefore whether containment should be considered. "
        "No remediation has been executed."
    )
    if source_unavailable:
        decision += (
            " The governed read source is currently unavailable, so this may need to "
            "be obtained from the owning team or platform."
        )
    return what + why + decision


def _trim(text: str, limit: int = 90) -> str:
    value = str(text or "").strip().rstrip(".")
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


def _recommended_next_action(
    *,
    sufficiency: dict[str, Any],
    run_status: dict[str, Any],
) -> str | None:
    value = run_status.get("next_action") or sufficiency.get("next_action")
    if value is None or not str(value).strip():
        return None
    return _analyst_process_next_action(str(value).strip())


_WORKFLOW_CONTROL_NEXT_ACTIONS = frozenset({"BLOCK", "BLOCKED", "DEGRADE", "CLARIFY", "CONTINUE", "CALL_T4"})


def _analyst_process_next_action(raw: str) -> str:
    """Map workflow control vocabulary to analyst process language.

    Workflow BLOCK/BLOCKED is not a security containment recommendation.
    Governed remediation actions surface separately via remediation_offer.
    """
    token = raw.strip().upper()
    if token in {"BLOCK", "BLOCKED"}:
        return "Unable to proceed — additional evidence required"
    if token == "DEGRADE":
        return "Continue with available evidence"
    if token == "CLARIFY":
        return "Clarification required"
    if token == "CONTINUE":
        return "Continue investigation"
    if token == "CALL_T4":
        return "Semantic understanding required"
    if token in {"STOP", "HALT", "ABORT"}:
        return "Unable to proceed — additional evidence required"
    if token == "CONTINUE_TO_OUTCOME":
        return "Continue investigation"
    if token in _WORKFLOW_CONTROL_NEXT_ACTIONS:
        return "Unable to proceed"
    return raw


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
