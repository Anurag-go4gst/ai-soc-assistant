"""AnswerContract — deterministic read-model projection from existing deciders."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

AnswerGoal = Literal[
    "live_results",
    "analyst_action_guidance",
    "policy_citation",
    "spl_artifact",
    "mitre_mapping",
    "mitre_explanation",
    "severity_assessment",
    "procedural_steps",
    "clarification",
]

ExecutionStatusLabel = Literal[
    "review_only_not_executed",
    "validated_not_executed",
    "execution_pending_mcp_unavailable",
    "executed_mock_evidence",
    "executed_live_evidence",
    "blocked_approval_required",
]

SplStatus = Literal["not_required", "ready_for_review", "blocked", "review_required"]
HilStatus = Literal["not_required", "required", "missing_evidence_review", "clarification_required"]


class AnswerContract(BaseModel):
    """Read-only projection; makes no new authority decisions."""

    answer_goal: list[str] = Field(default_factory=list)
    intent_family: str | None = None
    answer_mode: str | None = None
    spl_allowed: bool = False
    mcp_allowed: bool = False
    needs_mitre: bool = False
    mitre_answer_visible: bool = False
    mitre_technique_ids: list[str] = Field(default_factory=list)
    not_claimed_technique_ids: list[str] = Field(default_factory=list)
    severity_label: str | None = None
    severity_confidence: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    answer_rules_applied: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    analyst_checklist_safe: list[str] = Field(default_factory=list)
    investigation_steps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unsupported_claims_avoid: list[str] = Field(default_factory=list)
    spl_status: SplStatus = "not_required"
    hil_status: HilStatus = "not_required"
    candidate_mitre: list[str] = Field(default_factory=list)
    evidence_supported_mitre: list[str] = Field(default_factory=list)
    requires_validation_mitre: list[str] = Field(default_factory=list)
    not_claimed_mitre: list[str] = Field(default_factory=list)
    ruled_out_mitre: list[str] = Field(default_factory=list)
    spl_present: bool = False
    spl_approved: bool = False
    execution_status: str | None = None
    execution_block_reason: str | None = None
    human_review_required: bool = False
    execution_status_label: ExecutionStatusLabel | None = None
    execution_status_display: str | None = None
    section_order: list[str] = Field(default_factory=list)
    render_sections: dict[str, bool] = Field(default_factory=dict)
    # WS1 T1.4 — honest out-of-catalog handling.
    out_of_catalog_notice: str | None = None
    nearest_questions: list[dict] = Field(default_factory=list)
    success_after_failure_context: bool = False
    use_case_id: str | None = None
    required_evidence: list[str] = Field(default_factory=list)
    spl_status_detail: dict[str, Any] | None = None


_SECTION_PRIORITY: dict[str, int] = {
    "severity_assessment": 10,
    "investigation_guidance": 15,
    "mitre_mapping": 20,
    "mitre_explanation": 25,
    "spl_artifact": 30,
    "live_results": 40,
    "analyst_action_guidance": 50,
    "policy_citation": 60,
    "procedural_steps": 65,
    "clarification": 70,
    "limitations": 80,
}


def build_answer_contract(
    *,
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    mitre_decision: dict[str, Any] | None,
    severity_decision: Any | None,
    spl_validation: dict[str, Any] | None,
    execution: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    mitre_mappings: list[Any] | None = None,
    mitre_branch_result: dict[str, Any] | None = None,
    candidate_spl: dict[str, Any] | None = None,
    user_query: str | None = None,
    query_signals: dict[str, Any] | None = None,
    use_case_id: str | None = None,
    match_path: str | None = None,
) -> AnswerContract:
    intent = intent_classification or {}
    plan = evidence_plan or {}
    if str(intent.get("intent_family") or "") == "guided_investigation" and not plan:
        plan = {
            "answer_mode": "guided_investigation",
            "spl_allowed": True,
            "mcp_allowed": False,
            "needs_mitre": False,
            "requires_hil": True,
            "needs_hil": True,
            "checklist": [
                "Confirm asset ownership, criticality, and expected communications.",
                "Review firewall, DNS, proxy, and endpoint telemetry for a bounded window.",
                "Compare the activity with peer assets and approved change or vendor access.",
                "Have an analyst validate evidence before severity, MITRE, or containment decisions.",
            ],
            "investigation_workflow": [
                "Scope the affected assets and observation window.",
                "Collect and correlate the available telemetry.",
                "Test benign and suspicious hypotheses.",
                "Document limitations and analyst-approved next steps.",
            ],
            "limitations": [
                "No live query was executed.",
                "No MITRE technique or incident severity is asserted without evidence.",
            ],
            "unsupported_claims_avoid": [
                "confirmed compromise",
                "confirmed MITRE technique",
                "P1/P2 severity",
            ],
        }
    decision = mitre_decision or {}
    execution_payload = execution or {}
    review = human_review or {}
    branch = mitre_branch_result or {}
    goals = [str(item) for item in intent.get("answer_goal") or [] if item]

    mitre_ids = [
        str(item.get("technique_id") if isinstance(item, dict) else getattr(item, "technique_id", ""))
        for item in (mitre_mappings or [])
    ]
    mitre_ids = [item for item in mitre_ids if item]
    positive_mitre = set(mitre_ids)
    candidate_mitre = _branch_bucket(branch, "candidate_mitre")
    evidence_supported_mitre = _branch_bucket(branch, "evidence_supported_mitre")
    requires_validation_mitre = _branch_bucket(branch, "requires_validation_mitre")
    not_claimed_mitre = _branch_bucket(branch, "not_claimed_mitre")
    ruled_out_mitre = _branch_bucket(branch, "ruled_out_mitre")
    positive_mitre.update(candidate_mitre)
    positive_mitre.update(evidence_supported_mitre)
    positive_mitre.update(requires_validation_mitre)

    not_claimed = list(not_claimed_mitre)
    for item in decision.get("not_claimed") or []:
        tid = str(item)
        if tid and tid not in not_claimed and tid not in positive_mitre:
            not_claimed.append(tid)
    for item in ruled_out_mitre:
        if item not in not_claimed and item not in positive_mitre:
            not_claimed.append(item)
    for item in decision.get("rejected_techniques") or []:
        tid = str(item)
        if tid and tid not in not_claimed and tid not in positive_mitre:
            not_claimed.append(tid)

    spl_approved = bool(isinstance(spl_validation, dict) and spl_validation.get("approved"))
    spl_present = spl_approved and bool(
        isinstance(spl_validation, dict) and spl_validation.get("normalized_spl")
    )
    exec_status = str(execution_payload.get("status") or "") or None
    exec_label, exec_display = _execution_label(
        execution_payload=execution_payload,
        spl_present=spl_present,
        spl_approved=spl_approved,
        mcp_allowed=bool(plan.get("mcp_allowed")),
        human_review_required=bool(review.get("required")),
    )

    resolved_use_case_id = (
        str(use_case_id or plan.get("use_case_id") or "") or None
    )
    intent_family = str(intent.get("intent_family") or "") or None
    answer_mode = str(plan.get("answer_mode") or "") or None
    required_evidence = _dedupe(
        [str(item) for item in plan.get("required_evidence_keys") or [] if item]
    )

    missing: list[str] = [str(item) for item in plan.get("missing_required_evidence") or [] if item]
    if severity_decision is not None and _is_auth_use_case(resolved_use_case_id, intent_family):
        missing.extend(
            str(item)
            for item in getattr(severity_decision, "missing_evidence", None) or []
            if str(item) in _AUTH_LIMITATION_KEYS
        )
    if not missing:
        missing = _default_limitations(
            goals,
            spl_present,
            exec_status,
            intent_family=intent_family,
            answer_mode=answer_mode,
            use_case_id=resolved_use_case_id,
        )
    missing = _filter_missing_evidence_for_use_case(missing, resolved_use_case_id, intent_family)
    missing = _dedupe(missing)

    limitations = _dedupe([str(item) for item in plan.get("limitations") or [] if item])
    checklist = _safe_display_list(plan.get("checklist") or [])
    investigation_steps = _safe_display_list(plan.get("investigation_workflow") or [])
    if not investigation_steps:
        investigation_steps = list(checklist)
    unsupported = _dedupe([str(item) for item in plan.get("unsupported_claims_avoid") or [] if item])
    assumptions = _safe_display_list((candidate_spl or {}).get("assumptions") or [])
    answer_rules = _safe_display_list(plan.get("answer_rules") or [])
    spl_status = _spl_status(spl_validation, spl_allowed=bool(plan.get("spl_allowed")))
    spl_status_detail = _spl_status_detail(spl_validation, candidate_spl)
    hil_status = _hil_status(review, plan, missing)
    success_after_failure = _success_after_failure_context(
        query_signals, str(intent.get("intent_family") or "")
    )
    has_limitations_content = _has_limitations_content(
        limitations=limitations,
        missing_evidence=missing,
        intent_family=intent_family,
        answer_mode=answer_mode,
        use_case_id=resolved_use_case_id,
        success_after_failure_context=success_after_failure,
    )
    section_order = _section_order(
        goals,
        answer_mode=answer_mode,
        intent_family=intent_family,
        has_investigation_guidance=bool(
            required_evidence or checklist or investigation_steps or limitations
        ),
        has_limitations_content=has_limitations_content,
    )
    out_of_catalog_notice = None
    nearest_questions: list[dict] = []
    # Refusals/explicit human-review turns perform no guidance and carry no
    # notice. The default clarification fallback DOES — "did you mean" with
    # the nearest governed questions is the honest version of that turn.
    is_clarification_turn = str(plan.get("answer_mode") or "") == "clarification" or bool(
        intent.get("requires_clarification")
    )
    if str(match_path or "") == "out_of_registry" and not bool(review.get("required")):
        if is_clarification_turn:
            out_of_catalog_notice = (
                "This question is outside the governed question catalog. The closest "
                "governed questions are suggested below — confirm one or refine the ask."
            )
        else:
            out_of_catalog_notice = (
                "This question is outside the governed question catalog. The guidance "
                "below is general, review-only, and makes no claims beyond available evidence."
            )
        if user_query:
            from app.coverage.semantic_question_index import semantic_candidates

            nearest_questions = [
                {"question_ref": item["question_ref"], "question": item["question"]}
                for item in semantic_candidates(user_query)
            ]

    render = _render_sections(
        goals=goals,
        answer_mode=answer_mode or "",
        intent_family=intent_family,
        mitre_visible=bool(decision.get("answer_visible")) and bool(mitre_ids),
        not_claimed=not_claimed,
        spl_present=spl_present,
        playbook_eligible="policy_citation" in goals or "procedural_steps" in goals or "analyst_action_guidance" in goals,
        has_investigation_guidance=bool(
            required_evidence or checklist or investigation_steps or limitations
        ),
        has_limitations_content=has_limitations_content,
        hil_review_required=bool(review.get("required")),
    )

    severity_label = None
    severity_confidence = None
    if (
        severity_decision is not None
        and intent_family != "guided_investigation"
        and not _is_knowledge_profile(intent_family, answer_mode, user_query)
    ):
        severity_label = getattr(severity_decision, "severity_label", None)
        if exec_label in {"review_only_not_executed", "validated_not_executed", "blocked_approval_required"}:
            severity_confidence = "Medium" if exec_status != "executed" else "High"

    if out_of_catalog_notice:
        render["out_of_catalog_notice"] = True
    # WS2 T2.3 — skill-derived sections, content-driven (never goal-promised):
    # triage checklist from curated enrichment, evidence checklist from the
    # deterministic evidence requirements.
    render["triage_checklist"] = bool(checklist)
    render["evidence_checklist"] = bool(required_evidence)

    return AnswerContract(
        answer_goal=goals,
        intent_family=intent_family,
        answer_mode=str(plan.get("answer_mode") or "") or None,
        spl_allowed=bool(plan.get("spl_allowed")),
        mcp_allowed=bool(plan.get("mcp_allowed")),
        needs_mitre=bool(plan.get("needs_mitre")),
        mitre_answer_visible=bool(decision.get("answer_visible")),
        mitre_technique_ids=mitre_ids,
        not_claimed_technique_ids=not_claimed,
        severity_label=str(severity_label) if severity_label else None,
        severity_confidence=severity_confidence,
        missing_evidence=missing,
        answer_rules_applied=answer_rules,
        limitations=limitations,
        analyst_checklist_safe=checklist,
        investigation_steps=investigation_steps,
        assumptions=assumptions,
        unsupported_claims_avoid=unsupported,
        spl_status=spl_status,
        hil_status=hil_status,
        candidate_mitre=candidate_mitre,
        evidence_supported_mitre=evidence_supported_mitre,
        requires_validation_mitre=requires_validation_mitre,
        not_claimed_mitre=not_claimed_mitre,
        ruled_out_mitre=ruled_out_mitre,
        spl_present=spl_present,
        spl_approved=spl_approved,
        execution_status=exec_status,
        execution_block_reason=str(execution_payload.get("block_reason") or "") or None,
        human_review_required=bool(review.get("required")),
        execution_status_label=exec_label,
        execution_status_display=exec_display,
        section_order=section_order,
        render_sections=render,
        out_of_catalog_notice=out_of_catalog_notice,
        nearest_questions=nearest_questions,
        success_after_failure_context=success_after_failure,
        use_case_id=resolved_use_case_id,
        required_evidence=required_evidence,
        spl_status_detail=spl_status_detail,
    )


def _branch_bucket(branch: dict[str, Any], key: str) -> list[str]:
    if not isinstance(branch, dict) or key not in branch:
        return []
    authority = branch.get("branch_authority")
    if authority is not None and authority != "planner_mitre_branch":
        return []
    return _dedupe([str(item) for item in branch.get(key) or [] if item])


def _safe_display_list(values: Any) -> list[str]:
    safe: list[str] = []
    source = values if isinstance(values, list) else []
    for value in source:
        text = " ".join(str(value).split())
        lowered = text.lower()
        if not text or "skill.md" in lowered or "github.com" in lowered or "/skills/" in lowered:
            continue
        safe.append(text[:240])
    return _dedupe(safe)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _spl_status(spl_validation: dict[str, Any] | None, *, spl_allowed: bool = True) -> SplStatus:
    if not spl_allowed:
        return "not_required"
    if not isinstance(spl_validation, dict):
        return "not_required"
    if spl_validation.get("approved") and spl_validation.get("normalized_spl"):
        return "ready_for_review"
    if spl_validation.get("review_required"):
        return "review_required"
    return "blocked"


def _spl_status_detail(
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(spl_validation, dict):
        return None
    template_status = str(spl_validation.get("spl_template_status") or "unknown")
    reason = _spl_block_reason(spl_validation)
    if spl_validation.get("approved") and spl_validation.get("normalized_spl"):
        return {
            "template_status": template_status,
            "generation_status": "generated",
            "generation": "review_required",
            "review_required": True,
            "block_reason": None,
            "reason": "candidate_spl_review_only",
            "reason_display": "Governed SPL draft ready for analyst review (not executed).",
            "required_fields": [],
            "template_id": spl_validation.get("template_id") or (candidate_spl or {}).get("template_id"),
        }
    if not reason and spl_validation.get("llm_fallback_status") != "clarification_required":
        return None
    generation_status = "blocked" if reason else "review_required"
    reason_key = reason or "spl_generation_requires_source_clarification"
    required_fields = _spl_required_fields(spl_validation, candidate_spl, reason_key)
    reason_display = {
        "spl_template_active_source_profile_missing": "Source profile missing",
        "spl_template_missing": "No default template bound",
        "runtime_spl_governance_not_allowed": "Curated enrichment activation incomplete",
    }.get(reason_key, reason_key.replace("_", " "))
    return {
        "template_status": template_status,
        "generation_status": generation_status,
        "generation": generation_status,
        "review_required": bool(spl_validation.get("review_required") or reason),
        "block_reason": reason_key if generation_status == "blocked" else None,
        "reason": reason_key,
        "reason_display": reason_display,
        "required_fields": required_fields,
        "template_id": spl_validation.get("template_id") or (candidate_spl or {}).get("template_id"),
    }


def _spl_block_reason(spl_validation: dict[str, Any]) -> str:
    reject_reasons = [str(item) for item in spl_validation.get("reject_reasons") or [] if item]
    if {"missing_index", "missing_sourcetype", "index_or_datamodel"} & set(reject_reasons):
        return "spl_template_active_source_profile_missing"
    for key in ("review_required_reason", "llm_fallback_reason", "candidate_provider_reason", "governed_limitation"):
        value = str(spl_validation.get(key) or "")
        if value:
            return value
    return reject_reasons[0] if reject_reasons else ""


def _spl_required_fields(
    spl_validation: dict[str, Any],
    candidate_spl: dict[str, Any] | None,
    reason_key: str,
) -> list[str]:
    values: list[str] = []
    for source in (spl_validation, candidate_spl or {}):
        for key in ("required_fields", "enrichment_evidence_requirements"):
            for item in source.get(key) or []:
                text = str(item)
                if text and text not in values:
                    values.append(text)
    if values:
        return values
    if reason_key == "spl_template_active_source_profile_missing":
        return ["index", "sourcetype", "key fields", "time range"]
    return []


def _hil_status(
    review: dict[str, Any],
    plan: dict[str, Any],
    missing_evidence: list[str],
) -> HilStatus:
    if review.get("required"):
        review_type = str(review.get("review_type") or "")
        if "clarification" in review_type:
            return "clarification_required"
        return "required"
    if missing_evidence and (plan.get("requires_hil") or plan.get("needs_hil")):
        return "missing_evidence_review"
    if plan.get("answer_mode") == "guided_investigation" and plan.get("requires_hil"):
        return "required"
    return "not_required"


def _execution_label(
    *,
    execution_payload: dict[str, Any],
    spl_present: bool,
    spl_approved: bool,
    mcp_allowed: bool,
    human_review_required: bool,
) -> tuple[ExecutionStatusLabel | None, str | None]:
    if human_review_required:
        return "blocked_approval_required", "Blocked — approval required"
    status = str(execution_payload.get("status") or "")
    if status == "executed":
        origin = (execution_payload.get("splunk_result_envelope") or {}).get("origin")
        if origin == "fixture":
            return "executed_mock_evidence", "Executed — mock evidence"
        return "executed_live_evidence", "Executed — live evidence"
    if not spl_present:
        return None, None
    if spl_approved and not mcp_allowed:
        return "review_only_not_executed", "Review only — not executed"
    if spl_approved and mcp_allowed and status in {"skipped", "requires_human_review"}:
        block = str(execution_payload.get("block_reason") or "")
        if "mcp" in block.lower():
            return "execution_pending_mcp_unavailable", "Execution pending — MCP unavailable"
    if spl_approved:
        return "validated_not_executed", "Validated — not executed"
    return None, None


def _section_order(
    goals: list[str],
    *,
    answer_mode: str | None = None,
    intent_family: str | None = None,
    has_investigation_guidance: bool = False,
    has_limitations_content: bool = False,
) -> list[str]:
    if _is_knowledge_profile(intent_family, answer_mode):
        ordered = [goal for goal in ("policy_citation", "procedural_steps") if goal in goals]
        return ordered
    ordered = sorted({goal for goal in goals if goal in _SECTION_PRIORITY}, key=lambda g: _SECTION_PRIORITY[g])
    if has_investigation_guidance and "investigation_guidance" not in ordered:
        ordered.insert(0, "investigation_guidance")
    if ordered and has_limitations_content and "limitations" not in ordered:
        ordered.append("limitations")
    return ordered


def _render_sections(
    *,
    goals: list[str],
    answer_mode: str,
    intent_family: str | None,
    mitre_visible: bool,
    not_claimed: list[str],
    spl_present: bool,
    playbook_eligible: bool,
    has_investigation_guidance: bool = False,
    has_limitations_content: bool = False,
    hil_review_required: bool = False,
) -> dict[str, bool]:
    knowledge_profile = _is_knowledge_profile(intent_family, answer_mode)
    show_mitre = (
        not knowledge_profile
        and mitre_visible
        and ("mitre_mapping" in goals or "mitre_explanation" in goals or answer_mode == "live_investigation")
    )
    return {
        "severity_assessment": not knowledge_profile and ("severity_assessment" in goals or bool(spl_present)),
        "mitre_mapping": show_mitre,
        "not_claimed": show_mitre and bool(not_claimed),
        "spl_artifact": spl_present and ("spl_artifact" in goals or answer_mode in {"live_investigation", "hybrid"}),
        "live_results": "live_results" in goals,
        # AQ-001-consistent: the flag is content-driven. A goal alone is an
        # empty promise; HIL review turns are backed by the review notice.
        "analyst_action_guidance": has_investigation_guidance or hil_review_required,
        "policy_citation": playbook_eligible and answer_mode in {"rag_only", "hybrid"},
        "procedural_steps": "procedural_steps" in goals or has_investigation_guidance,
        "limitations": has_limitations_content,
        "investigation_guidance": has_investigation_guidance and not knowledge_profile,
    }


_EXCLUDED_LIMITATION_KEYS = frozenset({"confirmed_success", "success_after_failure"})


def _has_limitations_content(
    *,
    limitations: list[str],
    missing_evidence: list[str],
    intent_family: str | None,
    answer_mode: str | None,
    use_case_id: str | None,
    success_after_failure_context: bool,
) -> bool:
    """True only when deterministic limitation text will render (AQ-001)."""
    if _is_knowledge_profile(intent_family, answer_mode):
        return False
    if limitations:
        return True
    if success_after_failure_context and _is_auth_hybrid_use_case(use_case_id, intent_family):
        return True
    if intent_family == "hybrid_alert_review" and _is_auth_hybrid_use_case(use_case_id, intent_family):
        return True
    return bool(_missing_evidence_limitation_keys(missing_evidence, use_case_id=use_case_id))


def _is_auth_hybrid_use_case(use_case_id: str | None, intent_family: str | None) -> bool:
    if use_case_id:
        if use_case_id in _NON_AUTH_USE_CASES:
            return False
        return use_case_id.startswith(_AUTH_USE_CASE_PREFIXES)
    return intent_family == "hybrid_alert_review"


def _missing_evidence_limitation_keys(
    missing_evidence: list[str],
    *,
    use_case_id: str | None,
) -> list[str]:
    auth_only_keys = set(_AUTH_LIMITATION_KEYS)
    use_case = str(use_case_id or "")
    keys: list[str] = []
    for key in missing_evidence:
        text = str(key)
        if not text or text in _EXCLUDED_LIMITATION_KEYS:
            continue
        if text in auth_only_keys and not use_case.startswith("auth_"):
            continue
        keys.append(text)
    return keys


_AUTH_LIMITATION_KEYS = (
    "privileged_account_impacted",
    "critical_asset",
    "source_ownership",
    "mfa_status",
    "post_login_activity",
)

_NON_AUTH_USE_CASES = frozenset(
    {
        "edr_powershell_suspicious_command",
        "dns_beaconing_candidate",
        "soc_show_sop",
        "email_phishing_header_review",
    }
)

_AUTH_USE_CASE_PREFIXES = ("auth_",)


def _is_auth_use_case(use_case_id: str | None, intent_family: str | None) -> bool:
    if use_case_id:
        if use_case_id in _NON_AUTH_USE_CASES:
            return False
        return use_case_id.startswith(_AUTH_USE_CASE_PREFIXES)
    return intent_family == "hybrid_alert_review"


def _is_knowledge_profile(
    intent_family: str | None,
    answer_mode: str | None,
    user_query: str | None = None,
) -> bool:
    if answer_mode == "rag_only" or intent_family in {"sop_or_playbook", "policy_knowledge", "knowledge_only"}:
        return True
    if user_query and intent_family in {"sop_or_playbook", "policy_knowledge", "knowledge_only"}:
        return not bool(re.search(r"\b(?:alert|alt)[\s:=]+[A-Za-z0-9]", user_query, re.IGNORECASE))
    return False


def _filter_missing_evidence_for_use_case(
    missing: list[str],
    use_case_id: str | None,
    intent_family: str | None,
) -> list[str]:
    if _is_auth_use_case(use_case_id, intent_family):
        return missing
    auth_keys = set(_AUTH_LIMITATION_KEYS)
    return [item for item in missing if str(item) not in auth_keys]


def _default_limitations(
    goals: list[str],
    spl_present: bool,
    exec_status: str | None,
    *,
    intent_family: str | None = None,
    answer_mode: str | None = None,
    use_case_id: str | None = None,
) -> list[str]:
    if exec_status == "executed":
        return []
    if answer_mode == "rag_only" or intent_family in {"sop_or_playbook", "policy_knowledge", "knowledge_only"}:
        return []
    if use_case_id in _NON_AUTH_USE_CASES:
        return []
    if intent_family != "hybrid_alert_review":
        return []
    if not spl_present and "severity_assessment" not in goals:
        return []
    return list(_AUTH_LIMITATION_KEYS)


def _success_after_failure_context(query_signals: dict[str, Any] | None, intent_family: str) -> bool:
    """Read-model only: source the flag from the deterministic query signal.

    No query re-parsing — the `success_after_failure` signal is computed once in
    `chat.query_signals` and threaded here, keeping the contract a pure
    projection of the deciders.
    """
    if intent_family != "hybrid_alert_review":
        return False
    return bool((query_signals or {}).get("success_after_failure"))
