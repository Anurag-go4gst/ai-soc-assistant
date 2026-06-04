"""Runtime MITRE decision contract and deterministic visibility policy."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.threat.mitre_registry_schema import MitreRegistryMetadata

_MITRE_VISIBLE_GOALS = frozenset({"mitre_mapping", "mitre_explanation", "severity_assessment"})
_LIVE_INTENT_FAMILIES = frozenset(
    {"live_investigation", "hybrid_investigation_plus_policy", "hybrid_alert_review", "spl_generation_only"}
)
_POLICY_INTENT_FAMILIES = frozenset({"policy_knowledge", "sop_or_playbook", "knowledge_only"})
_DEFAULT_NOT_CLAIMED = ("T1003", "T1078", "T1562.001")


class MitreDecision(BaseModel):
    """Governed runtime MITRE outcome (visibility + status); not observed evidence."""

    mitre_status: str = "legacy_passthrough"
    techniques: list[dict[str, Any]] = Field(default_factory=list)
    rejected_techniques: list[str] = Field(default_factory=list)
    registry_candidates: list[str] = Field(default_factory=list)
    not_claimed: list[str] = Field(default_factory=list)
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
    **_kwargs: Any,
) -> MitreDecision:
    """Resolve answer-visible MITRE mappings from registry metadata and intent."""
    from app.threat.mitre_registry_enrichment import registry_mitre_metadata

    meta = registry_metadata
    if meta is None:
        meta = registry_mitre_metadata(question_ref=question_ref, use_case_id=use_case_id)

    candidates = meta.all_mapped_technique_ids() if meta is not None else []
    blocked = list(meta.mitre_blocked) if meta is not None else []
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

    if requires_clarification or (meta.mitre_requires_alert_context and not alert_context_present):
        return MitreDecision(
            mitre_status="requires_alert_context",
            techniques=[],
            rejected_techniques=blocked,
            registry_candidates=candidates,
            not_claimed=list(_DEFAULT_NOT_CLAIMED),
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

    explicitly_requested = bool(_MITRE_VISIBLE_GOALS.intersection(answer_goal))
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

    visible_ids = [tid for tid in candidates if tid not in set(blocked)]
    not_claimed_defaults = _not_claimed_for_context(
        visible_ids=visible_ids,
        blocked=blocked,
        use_case_id=use_case_id,
        explicitly_requested=explicitly_requested,
    )
    return MitreDecision(
        mitre_status="candidate",
        techniques=_technique_payloads(visible_ids, refs, use_case_id=use_case_id),
        rejected_techniques=blocked,
        registry_candidates=candidates,
        not_claimed=not_claimed_defaults,
        answer_visible=False,
        requires_alert_context=False,
        requires_more_context_for_supported_mapping=False,
        reason="Registry-permitted MITRE candidates are visible as candidate mappings only; confirmation requires evidence review.",
        registry_metadata=meta,
    ).model_copy(update={"answer_visible": bool(visible_ids)})


def _answer_goal(intent_classification: dict[str, Any] | None) -> set[str]:
    value = (intent_classification or {}).get("answer_goal")
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item}


def _not_claimed_for_context(
    *,
    visible_ids: list[str],
    blocked: list[str],
    use_case_id: str | None,
    explicitly_requested: bool,
) -> list[str]:
    if not explicitly_requested:
        return []
    if use_case_id == "auth_success_after_failure":
        return [item for item in ("T1003", "T1562.001") if item in blocked or item not in visible_ids]
    return [item for item in _DEFAULT_NOT_CLAIMED if item not in visible_ids and item not in blocked]


def _technique_payloads(
    technique_ids: list[str],
    source_refs: list[str],
    *,
    use_case_id: str | None = None,
) -> list[dict[str, Any]]:
    from app.threat.mitre_kb import load_mitre_techniques

    by_id = {item.technique_id.upper(): item for item in load_mitre_techniques()}
    payloads: list[dict[str, Any]] = []
    for technique_id in technique_ids:
        technique = by_id.get(technique_id.upper())
        if technique is None:
            continue
        why = "Registry-permitted MITRE candidate; not confirmed without supporting evidence."
        if use_case_id == "auth_success_after_failure":
            if technique.technique_id == "T1110.001":
                why = (
                    "Repeated failed login attempts followed by a successful login for the same user "
                    "may indicate password guessing / brute-force behavior."
                )
            elif technique.technique_id == "T1078":
                why = (
                    "Successful login after repeated failures is a Valid Accounts candidate; "
                    "confirm account criticality, MFA result, source ownership, and post-login activity."
                )
        payloads.append(
            {
                "technique_id": technique.technique_id,
                "name": technique.name,
                "tactic": technique.tactic,
                "status": "candidate",
                "why": why,
                "evidence_requirements": list(technique.evidence_requirements),
                "source_refs": list(source_refs),
                "recommended_pivots": list(technique.recommended_pivots),
            }
        )
    return payloads
