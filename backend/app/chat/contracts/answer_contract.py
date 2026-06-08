"""AnswerContract — deterministic read-model projection from existing deciders."""

from __future__ import annotations

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
    success_after_failure_context: bool = False


_SECTION_PRIORITY: dict[str, int] = {
    "severity_assessment": 10,
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
) -> AnswerContract:
    intent = intent_classification or {}
    plan = evidence_plan or {}
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
    not_claimed = [str(item) for item in (decision.get("not_claimed") or [])]
    for item in decision.get("rejected_techniques") or []:
        tid = str(item)
        if tid and tid not in not_claimed:
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

    missing: list[str] = [str(item) for item in plan.get("missing_required_evidence") or [] if item]
    if severity_decision is not None:
        missing.extend(str(item) for item in getattr(severity_decision, "missing_evidence", None) or [])
    if not missing:
        missing = _default_limitations(goals, spl_present, exec_status)
    missing = _dedupe(missing)

    limitations = _dedupe([str(item) for item in plan.get("limitations") or [] if item])
    checklist = _safe_display_list(plan.get("checklist") or [])
    unsupported = _dedupe([str(item) for item in plan.get("unsupported_claims_avoid") or [] if item])
    assumptions = _safe_display_list((candidate_spl or {}).get("assumptions") or [])
    answer_rules = _safe_display_list(plan.get("answer_rules") or [])
    spl_status = _spl_status(spl_validation)
    hil_status = _hil_status(review, plan, missing)
    candidate_mitre = _branch_bucket(branch, "candidate_mitre")
    evidence_supported_mitre = _branch_bucket(branch, "evidence_supported_mitre")
    requires_validation_mitre = _branch_bucket(branch, "requires_validation_mitre")
    not_claimed_mitre = _branch_bucket(branch, "not_claimed_mitre")
    ruled_out_mitre = _branch_bucket(branch, "ruled_out_mitre")

    section_order = _section_order(goals)
    render = _render_sections(
        goals=goals,
        answer_mode=str(plan.get("answer_mode") or ""),
        mitre_visible=bool(decision.get("answer_visible")) and bool(mitre_ids),
        not_claimed=not_claimed,
        spl_present=spl_present,
        playbook_eligible="policy_citation" in goals or "procedural_steps" in goals or "analyst_action_guidance" in goals,
    )

    severity_label = None
    severity_confidence = None
    if severity_decision is not None:
        severity_label = getattr(severity_decision, "severity_label", None)
        if exec_label in {"review_only_not_executed", "validated_not_executed", "blocked_approval_required"}:
            severity_confidence = "Medium" if exec_status != "executed" else "High"

    return AnswerContract(
        answer_goal=goals,
        intent_family=str(intent.get("intent_family") or "") or None,
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
        success_after_failure_context=_success_after_failure_context(
            query_signals, str(intent.get("intent_family") or "")
        ),
    )


def _branch_bucket(branch: dict[str, Any], key: str) -> list[str]:
    if not isinstance(branch, dict) or branch.get("branch_authority") != "planner_mitre_branch":
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


def _spl_status(spl_validation: dict[str, Any] | None) -> SplStatus:
    if not isinstance(spl_validation, dict):
        return "not_required"
    if spl_validation.get("approved") and spl_validation.get("normalized_spl"):
        return "ready_for_review"
    if spl_validation.get("review_required"):
        return "review_required"
    return "blocked"


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


def _section_order(goals: list[str]) -> list[str]:
    ordered = sorted({goal for goal in goals if goal in _SECTION_PRIORITY}, key=lambda g: _SECTION_PRIORITY[g])
    if ordered and "limitations" not in ordered:
        ordered.append("limitations")
    return ordered


def _render_sections(
    *,
    goals: list[str],
    answer_mode: str,
    mitre_visible: bool,
    not_claimed: list[str],
    spl_present: bool,
    playbook_eligible: bool,
) -> dict[str, bool]:
    show_mitre = mitre_visible and ("mitre_mapping" in goals or "mitre_explanation" in goals or answer_mode == "live_investigation")
    if answer_mode == "rag_only":
        show_mitre = False
    return {
        "severity_assessment": "severity_assessment" in goals or bool(spl_present),
        "mitre_mapping": show_mitre,
        "not_claimed": show_mitre and bool(not_claimed),
        "spl_artifact": spl_present and ("spl_artifact" in goals or answer_mode in {"live_investigation", "hybrid"}),
        "live_results": "live_results" in goals,
        "analyst_action_guidance": "analyst_action_guidance" in goals,
        "policy_citation": playbook_eligible and answer_mode in {"rag_only", "hybrid"},
        "procedural_steps": "procedural_steps" in goals,
        "limitations": True,
    }


def _default_limitations(goals: list[str], spl_present: bool, exec_status: str | None) -> list[str]:
    if exec_status == "executed":
        return []
    if not spl_present and "severity_assessment" not in goals:
        return []
    return [
        "privileged_account_impacted",
        "critical_asset",
        "source_ownership",
        "mfa_status",
        "post_login_activity",
    ]


def _success_after_failure_context(query_signals: dict[str, Any] | None, intent_family: str) -> bool:
    """Read-model only: source the flag from the deterministic query signal.

    No query re-parsing — the `success_after_failure` signal is computed once in
    `chat.query_signals` and threaded here, keeping the contract a pure
    projection of the deciders.
    """
    if intent_family != "hybrid_alert_review":
        return False
    return bool((query_signals or {}).get("success_after_failure"))
