"""Runtime MITRE decision contract and deterministic visibility policy."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.threat.mitre_evidence_preconditions import (
    cap_mitre_status_for_evidence_tier,
    evaluate_pilot_mitre_evidence_status,
    precondition_negated,
    resolve_evidence_tier,
)
from app.threat.mitre_registry_schema import MitreRegistryMetadata

_MITRE_VISIBLE_GOALS = frozenset({"mitre_mapping", "mitre_explanation", "severity_assessment"})
_LIVE_INTENT_FAMILIES = frozenset(
    {"live_investigation", "hybrid_investigation_plus_policy", "hybrid_alert_review", "spl_generation_only"}
)
_POLICY_INTENT_FAMILIES = frozenset({"policy_knowledge", "sop_or_playbook", "knowledge_only"})


class MitreDecision(BaseModel):
    """Governed runtime MITRE outcome (visibility + status); not observed evidence."""

    mitre_status: str = "legacy_passthrough"
    techniques: list[dict[str, Any]] = Field(default_factory=list)
    rejected_techniques: list[str] = Field(default_factory=list)
    registry_candidates: list[str] = Field(default_factory=list)
    not_claimed: list[str] = Field(default_factory=list)
    evidence_statuses: dict[str, str] = Field(default_factory=dict)
    evidence_status_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    answer_visible: bool = False
    requires_alert_context: bool = False
    requires_more_context_for_supported_mapping: bool = False
    reason: str = ""
    registry_metadata: MitreRegistryMetadata | None = None


def resolve_mitre_decision(
    *,
    question_ref: str | None = None,
    use_case_id: str | None = None,
    registry_metadata: MitreRegistryMetadata | None = None,
    intent_classification: dict[str, Any] | None = None,
    evidence_plan: dict[str, Any] | None = None,
    source_refs: list[str] | None = None,
    alert_context_present: bool = False,
    negative_evidence: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> MitreDecision:
    """Resolve answer-visible MITRE mappings from registry metadata and intent.

    `negative_evidence` carries the present-evidence keys (see
    `chat.negative_evidence_extractor`); a candidate technique whose required
    evidence precondition is absent is demoted from visible to Not Claimed.
    """
    from app.chat.negative_evidence_extractor import present_evidence_keys
    from app.threat.mitre_registry_enrichment import (
        registry_mitre_metadata,
        registry_mitre_metadata_for_runtime,
    )

    meta = registry_metadata
    if meta is None:
        meta = registry_mitre_metadata_for_runtime(question_ref=question_ref, use_case_id=use_case_id)
        if meta is None and not use_case_id:
            meta = registry_mitre_metadata(question_ref=question_ref, use_case_id=None)

    candidates = meta.all_mapped_technique_ids() if meta is not None else []
    blocked = list(meta.mitre_blocked) if meta is not None else []
    present_evidence = present_evidence_keys(negative_evidence)
    answer_goal = _answer_goal(intent_classification)
    intent_family = str((intent_classification or {}).get("intent_family") or "")
    requires_clarification = bool((intent_classification or {}).get("requires_clarification"))
    answer_mode = str((evidence_plan or {}).get("answer_mode") or "")
    refs = list(source_refs or [])

    if meta is None or not candidates:
        return MitreDecision(
            mitre_status="no_registry_mapping",
            techniques=[],
            rejected_techniques=blocked,
            registry_candidates=candidates,
            not_claimed=[],
            answer_visible=False,
            requires_alert_context=False,
            requires_more_context_for_supported_mapping=False,
            reason="No runtime MITRE registry metadata is available for this route.",
            registry_metadata=meta,
        )

    use_case_review_guidance = bool(_kwargs.get("use_case_review_guidance"))
    if (requires_clarification and not alert_context_present) or (
        meta.mitre_requires_alert_context and not alert_context_present and not use_case_review_guidance
    ):
        return MitreDecision(
            mitre_status="requires_alert_context",
            techniques=[],
            rejected_techniques=blocked,
            registry_candidates=candidates,
            not_claimed=[],
            answer_visible=False,
            requires_alert_context=True,
            requires_more_context_for_supported_mapping=True,
            reason="MITRE mapping requires grounded alert context before analyst-visible mapping.",
            registry_metadata=meta,
        )

    if intent_family in _POLICY_INTENT_FAMILIES or answer_mode == "rag_only":
        return MitreDecision(
            mitre_status="not_answer_visible",
            techniques=[],
            rejected_techniques=blocked,
            registry_candidates=candidates,
            not_claimed=[],
            answer_visible=False,
            requires_alert_context=False,
            requires_more_context_for_supported_mapping=False,
            reason="Policy or knowledge question; MITRE mapping was not requested and is trace-only.",
            registry_metadata=meta,
        )

    explicitly_requested = bool(
        _MITRE_VISIBLE_GOALS.intersection(answer_goal)
        or _kwargs.get("explicit_mitre_request")
    )
    live_supported = intent_family in _LIVE_INTENT_FAMILIES or answer_mode in {"live_investigation", "hybrid"}
    if not explicitly_requested and not live_supported:
        return MitreDecision(
            mitre_status="not_answer_visible",
            techniques=[],
            rejected_techniques=blocked,
            registry_candidates=candidates,
            not_claimed=[],
            answer_visible=False,
            requires_alert_context=False,
            requires_more_context_for_supported_mapping=False,
            reason="Intent does not ask for MITRE and no live investigation evidence path supports display.",
            registry_metadata=meta,
        )

    # General negative-evidence rule: a non-blocked candidate is only visible
    # when its required evidence precondition is present; otherwise it is
    # demoted to Not Claimed. Registry-blocked techniques surface via
    # `rejected_techniques` and are not re-listed here.
    blocked_set = set(blocked)
    non_blocked = [tid for tid in candidates if tid not in blocked_set]
    evidence_tier = resolve_evidence_tier(
        source_evidence=_kwargs.get("source_evidence"),
        execution=_kwargs.get("execution"),
        source_profile_missing=bool(_kwargs.get("source_profile_missing")),
    )
    status_details = {
        tid: _cap_status_detail(
            evaluate_pilot_mitre_evidence_status(
                use_case_id=use_case_id,
                technique_id=tid,
                present_evidence=present_evidence,
            ),
            evidence_tier,
        )
        for tid in non_blocked
    }
    if use_case_review_guidance and not alert_context_present:
        for tid in non_blocked:
            detail = dict(status_details.get(tid) or {})
            current = str(detail.get("status") or "candidate")
            if current == "evidence_supported" and not detail.get("evidence_keys"):
                current = "requires_validation"
            elif current == "not_claimed" or precondition_negated(tid, present_evidence):
                current = "candidate"
                detail["reason"] = (
                    detail.get("reason")
                    or "Registry-permitted MITRE candidate without alert logs; validate against governed evidence requirements."
                )
            detail["status"] = current
            status_details[tid] = detail
    visible_ids = [
        tid
        for tid, detail in status_details.items()
        if detail.get("status") in {"candidate", "evidence_supported", "requires_validation"}
        and (use_case_review_guidance or not precondition_negated(tid, present_evidence))
    ]
    visible_set = set(visible_ids)
    demoted_ids = [
        tid
        for tid, detail in status_details.items()
        if tid not in visible_set
        and (
            detail.get("status") == "not_claimed"
            or (not use_case_review_guidance and precondition_negated(tid, present_evidence))
        )
    ]
    evidence_statuses = {tid: str(detail.get("status") or "candidate") for tid, detail in status_details.items()}
    aggregate_status = "evidence_supported" if "evidence_supported" in set(evidence_statuses.values()) else "candidate"
    return MitreDecision(
        mitre_status=aggregate_status,
        techniques=_technique_payloads(visible_ids, refs, use_case_id=use_case_id, status_details=status_details),
        rejected_techniques=blocked,
        registry_candidates=candidates,
        not_claimed=demoted_ids if explicitly_requested else [],
        evidence_statuses=evidence_statuses,
        evidence_status_details=status_details,
        answer_visible=False,
        requires_alert_context=False,
        requires_more_context_for_supported_mapping=False,
        reason="Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
        registry_metadata=meta,
    ).model_copy(update={"answer_visible": bool(visible_ids)})


def _cap_status_detail(detail: dict[str, Any], evidence_tier: str) -> dict[str, Any]:
    capped = dict(detail)
    current = str(capped.get("status") or "candidate")
    capped_status = cap_mitre_status_for_evidence_tier(current, evidence_tier)
    if capped_status != current:
        capped["status"] = capped_status
        if capped_status in {"candidate", "requires_validation"}:
            capped["reason"] = (
                f"{capped.get('reason') or ''} "
                "Signal-only or unvalidated context cannot support evidence-supported MITRE; "
                "validate against source logs before upgrading."
            ).strip()
        if capped_status != "evidence_supported":
            capped["evidence_keys"] = []
    return capped


def _answer_goal(intent_classification: dict[str, Any] | None) -> set[str]:
    value = (intent_classification or {}).get("answer_goal")
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item}


def _technique_payloads(
    technique_ids: list[str],
    source_refs: list[str],
    *,
    use_case_id: str | None = None,
    status_details: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    from app.threat.mitre_kb import load_mitre_techniques

    by_id = {item.technique_id.upper(): item for item in load_mitre_techniques()}
    payloads: list[dict[str, Any]] = []
    for technique_id in technique_ids:
        technique = by_id.get(technique_id.upper())
        if technique is None:
            continue
        detail = (status_details or {}).get(technique_id) or {}
        evidence_status = str(detail.get("status") or "candidate")
        why = str(detail.get("reason") or "Registry-permitted MITRE candidate; not confirmed without supporting evidence.")
        if use_case_id == "auth_success_after_failure":
            if technique.technique_id == "T1110.001" and evidence_status == "candidate":
                why = (
                    "Repeated failed login attempts followed by a successful login for the same user "
                    "may indicate password guessing / brute-force behavior."
                )
            elif technique.technique_id == "T1078" and evidence_status == "candidate":
                why = (
                    "Successful login after repeated failures is a Valid Accounts candidate; "
                    "confirm account criticality, MFA result, source ownership, and post-login activity."
                )
        payloads.append(
            {
                "technique_id": technique.technique_id,
                "name": technique.name,
                "tactic": technique.tactic,
                "status": evidence_status,
                "evidence_status": evidence_status,
                "status_reason": why,
                "evidence_keys": [str(item) for item in detail.get("evidence_keys") or []],
                "why": why,
                "evidence_requirements": list(technique.evidence_requirements),
                "source_refs": list(source_refs),
                "recommended_pivots": list(technique.recommended_pivots),
            }
        )
    return payloads
