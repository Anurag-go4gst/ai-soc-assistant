"""Deterministic Knowledge specialist — plan vs intent vs required evidence audit.

No LLM involved (item 9 re-scope, LLM-primary deferred at item 8). The
specialist compares the knowledge domains the intent classification and the
EvidencePlan demand against the knowledge-owned steps the composed
``ResourcePlan`` actually carries, then reports:

- ``reference_domains``: the expected knowledge domains (lane vocabulary),
- ``warnings``: coverage gaps and surplus knowledge steps,
- ``proposals``: fill-blank ``reference_domains`` args on steps the knowledge
  lane already owns and that have not set them.

Authority stays with the Resource Planner merge: proposals cannot add steps,
touch policy checks, or override existing args (fill-blank only — the merge
would overwrite, so this module never proposes onto a step that already has
``reference_domains``).
"""

from __future__ import annotations

from typing import Any

from app.planner.planner_hierarchy import (
    KnowledgeSpecialistReport,
    SpecialistProposal,
)

# Intent-family → knowledge domains demanded (lane vocabulary:
# atlas, cve, mitre, rag, reference_lookup).
_INTENT_FAMILY_DOMAINS: dict[str, frozenset[str]] = {
    "mitre_mapping": frozenset({"mitre"}),
    "mitre_explanation": frozenset({"mitre"}),
    "hybrid_alert_review": frozenset({"mitre"}),
    "cve_investigation": frozenset({"cve"}),
    "reference_knowledge": frozenset({"reference_lookup"}),
    "policy_knowledge": frozenset({"rag"}),
    "knowledge_only": frozenset({"rag"}),
    "sop_or_playbook": frozenset({"rag"}),
    "hybrid_investigation_plus_policy": frozenset({"rag"}),
}

_ANSWER_GOAL_DOMAINS: dict[str, frozenset[str]] = {
    "mitre_mapping": frozenset({"mitre"}),
    "mitre_explanation": frozenset({"mitre"}),
    "policy_citation": frozenset({"rag"}),
    "reference_lookup": frozenset({"reference_lookup"}),
}

# EvidencePlan boolean → domain (required-evidence cross-check).
_EVIDENCE_BOOLEAN_DOMAINS: dict[str, str] = {
    "needs_rag": "rag",
    "needs_mitre": "mitre",
}

# Knowledge-owned plan-step purpose → domains that step covers.
_STEP_PURPOSE_DOMAINS: dict[str, frozenset[str]] = {
    "knowledge_retrieval": frozenset({"rag", "reference_lookup", "atlas"}),
    "cve_lookup": frozenset({"cve"}),
    "mitre_mapping": frozenset({"mitre"}),
}

KNOWLEDGE_ALIGNED = "knowledge_domains_aligned"
KNOWLEDGE_GAP = "knowledge_gap_detected"
KNOWLEDGE_IDLE = "knowledge_lane_idle"


def expected_knowledge_domains(
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
) -> set[str]:
    """Domains the intent and the EvidencePlan booleans demand."""
    expected: set[str] = set()
    if isinstance(intent_classification, dict):
        family = str(intent_classification.get("intent_family") or "")
        expected |= _INTENT_FAMILY_DOMAINS.get(family, frozenset())
        for goal in intent_classification.get("answer_goal") or []:
            expected |= _ANSWER_GOAL_DOMAINS.get(str(goal), frozenset())
    if isinstance(evidence_plan, dict):
        for boolean, domain in _EVIDENCE_BOOLEAN_DOMAINS.items():
            if evidence_plan.get(boolean) is True:
                expected.add(domain)
    return expected


def _knowledge_steps(evidence_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(evidence_plan, dict):
        return []
    plan = evidence_plan.get("resource_plan")
    steps = plan.get("steps") if isinstance(plan, dict) else None
    return [
        step
        for step in steps or []
        if isinstance(step, dict) and str(step.get("purpose") or "") in _STEP_PURPOSE_DOMAINS
    ]


def build_knowledge_audit_report(
    *,
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    delegation_id: str = "del:knowledge",
) -> KnowledgeSpecialistReport:
    """Audit the composed plan against intent-demanded knowledge domains."""
    expected = expected_knowledge_domains(intent_classification, evidence_plan)
    steps = _knowledge_steps(evidence_plan)

    covered: set[str] = set()
    proposals: list[SpecialistProposal] = []
    warnings: list[str] = []

    for step in steps:
        purpose = str(step.get("purpose") or "")
        step_domains = _STEP_PURPOSE_DOMAINS[purpose]
        covered |= step_domains
        overlap = sorted(step_domains & expected)
        args = step.get("args_template")
        existing = args.get("reference_domains") if isinstance(args, dict) else None
        if overlap and not existing:
            proposals.append(
                SpecialistProposal(
                    proposal_id=f"kp:{purpose}",
                    purpose=purpose,
                    args_template={"reference_domains": overlap},
                    rationale=f"intent demands {overlap}; step args left blank",
                )
            )

    for domain in sorted(expected - covered):
        warnings.append(f"knowledge_gap:{domain}:no_plan_step")
    if not expected:
        for step in steps:
            warnings.append(
                f"knowledge_step_without_intent_domain:{step.get('purpose')}"
            )

    if expected - covered:
        decision_reason = KNOWLEDGE_GAP
    elif expected:
        decision_reason = KNOWLEDGE_ALIGNED
    else:
        decision_reason = KNOWLEDGE_IDLE

    return KnowledgeSpecialistReport(
        delegation_id=delegation_id,
        decision_reason=decision_reason,
        reference_domains=sorted(expected),
        proposals=proposals,
        warnings=warnings,
    )
