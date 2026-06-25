"""Final-answer validator — deterministic fail-closed backstop.

The AnswerContract + builder are the primary enforcer; a blocked finding shown
as a positive claim is a *builder bug*. This validator runs on the assembled
analyst-response envelope (what the user sees) and fails closed — routing to
analyst review — when the answer contradicts the contract or the deciders. It
does NOT silently repair, which would mask the upstream defect.

Distinct from the dormant LLM-draft Answer Guard (`app/answer_guard`): this is a
deterministic contract check that runs whenever the control plane is on, not
gated by AI_SOC_LLM_ANSWER_GUARD_ENABLED. It reuses `GuardResult` /
`AnswerGuardStatus` shapes so the trace renders uniformly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.answer_guard.models import AnswerGuardStatus

# NOTE: this deterministic validator deliberately does NOT import
# `app.answer_guard.rules` (the dormant LLM-draft semantic guards). That module
# must stay out of the /chat import graph (see
# test_answer_guard_rules_stage3ji2). We mirror only the GuardResult *shape*
# (guard_id / status / severity / message) with a local type so the trace
# renders uniformly without coupling to the dormant guards.


@dataclass(frozen=True)
class _FinalGuardResult:
    guard_id: str
    status: str
    severity: str
    message: str
    affected_field: str | None = None


# Single source of truth for the check ids, so passed/failed reporting in the
# trace can never drift from the checks actually run.
_CHECK_IDS: tuple[str, ...] = (
    "final.blocked_finding_claimed",
    "final.mitre_visible_when_suppressed",
    "final.rag_override_mitre",
    "final.spl_on_rag_only",
    "final.candidate_described_as_confirmed",
    "final.spl_only_missing_action_guidance",
    "final.unsafe_account_compromise_claim",
    "final.unsafe_c2_confirmed_claim",
    "final.unsafe_ransomware_confirmed_claim",
    "final.unsafe_malware_confirmed_claim",
    "final.unsafe_execution_claim",
    "final.evidence_supported_without_status",
    "final.containment_without_hil",
    "final.direct_summary_contains_spl_query",
    "final.direct_summary_contains_full_checklist",
    "final.duplicate_review_only_warning",
    "final.duplicate_soc_checklist",
    "final.priority_prefix_without_severity",
    "final.live_backed_without_execution",
)

_UNSAFE_POSITIVE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("final.unsafe_account_compromise_claim", r"\baccount compromis", "direct_answer_summary"),
    ("final.unsafe_c2_confirmed_claim", r"\b(c2 confirmed|confirmed c2)\b", "direct_answer_summary"),
    ("final.unsafe_ransomware_confirmed_claim", r"\bransomware confirmed\b", "direct_answer_summary"),
    ("final.unsafe_malware_confirmed_claim", r"\bmalware confirmed\b", "direct_answer_summary"),
)


def _blocking(guard_id: str, message: str, field: str | None = None) -> _FinalGuardResult:
    return _FinalGuardResult(
        guard_id=guard_id,
        status="fail",
        severity="blocking_candidate",
        message=message,
        affected_field=field,
    )


def _ids(rows: Any) -> set[str]:
    out: set[str] = set()
    for row in rows or []:
        if isinstance(row, dict):
            value = row.get("Technique") or row.get("technique_id")
            if value:
                out.add(str(value))
    return out


def validate_final_answer(
    *,
    analyst_response: Any | None,
    answer_contract: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    mitre_decision: dict[str, Any] | None,
    human_review: dict[str, Any] | None = None,
    planning_decision: dict[str, Any] | None = None,
    routing_provenance: dict[str, Any] | None = None,
    visible_message: str | None = None,
) -> AnswerGuardStatus:
    """Validate the assembled answer against the contract; fail closed on conflict."""
    if analyst_response is None or answer_contract is None:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="skipped",
            reason="No assembled answer or contract to validate.",
        )

    contract = answer_contract
    plan = evidence_plan or {}
    decision = mitre_decision or {}
    findings: list[_FinalGuardResult] = []

    visible_mitre = _ids(getattr(analyst_response, "mitre_mappings", None))
    blocked_ids = {str(item) for item in contract.get("not_claimed_technique_ids") or []}
    answer_goal = [str(item) for item in contract.get("answer_goal") or []]
    answer_mode = str(plan.get("answer_mode") or contract.get("answer_mode") or "")
    spl_code = getattr(analyst_response, "spl_code", None)
    response_profile = str(getattr(analyst_response, "response_profile", "") or "")
    recommended = getattr(analyst_response, "recommended_actions", None) or []

    # 0. WS1 T1.4 fail-closed: an out-of-catalog answer must say so.
    resource_plan = plan.get("resource_plan") if isinstance(plan.get("resource_plan"), dict) else {}
    provenance = resource_plan.get("provenance") if isinstance(resource_plan.get("provenance"), dict) else {}
    planning_summary = (
        planning_decision.get("resource_plan_summary")
        if isinstance(planning_decision, dict) and isinstance(planning_decision.get("resource_plan_summary"), dict)
        else {}
    )
    match_path = str(
        provenance.get("match_path")
        or planning_summary.get("match_path")
        or (routing_provenance or {}).get("deterministic_match_path")
        or ""
    )
    if (
        match_path == "out_of_registry"
        and not contract.get("out_of_catalog_notice")
        # Refusal/HIL turns intentionally carry no notice (they perform no guidance).
        and not bool(contract.get("human_review_required"))
    ):
        findings.append(
            _blocking(
                "final.out_of_catalog_notice_missing",
                "Out-of-registry answer is missing the out-of-catalog notice.",
                field="out_of_catalog_notice",
            )
        )

    # 1. A blocked / not-claimed finding must never appear as a positive mapping.
    leaked = sorted(visible_mitre & blocked_ids)
    if leaked:
        findings.append(
            _blocking(
                "final.blocked_finding_claimed",
                f"Not-claimed technique(s) shown as a positive MITRE mapping: {', '.join(leaked)}.",
                field="mitre_mappings",
            )
        )

    # 2. MITRE must not be answer-visible when the decision suppresses it.
    if visible_mitre and not bool(contract.get("mitre_answer_visible")):
        findings.append(
            _blocking(
                "final.mitre_visible_when_suppressed",
                "MITRE mappings shown although the MITRE decision is not answer-visible.",
                field="mitre_mappings",
            )
        )

    # 3. RAG/other source must not inject techniques the decider did not surface.
    decider_ids = {str(item) for item in decision.get("registry_candidates") or []}
    for tid in (item.get("technique_id") for item in decision.get("techniques") or [] if isinstance(item, dict)):
        if tid:
            decider_ids.add(str(tid))
    injected = sorted(visible_mitre - decider_ids) if decider_ids else []
    if injected:
        findings.append(
            _blocking(
                "final.rag_override_mitre",
                f"MITRE mapping(s) not sourced from the deterministic decision: {', '.join(injected)}.",
                field="mitre_mappings",
            )
        )

    # 4. rag_only answers carry no SPL or MCP artifacts.
    if answer_mode == "rag_only" and spl_code:
        findings.append(
            _blocking(
                "final.spl_on_rag_only",
                "SPL artifact present on a rag_only (policy/knowledge) answer.",
                field="spl_code",
            )
        )

    # 5. Candidate findings must not be presented as confirmed.
    for row in getattr(analyst_response, "mitre_mappings", None) or []:
        status = str(row.get("Status") or "").lower() if isinstance(row, dict) else ""
        if status in {"confirmed", "supported"}:
            findings.append(
                _blocking(
                    "final.candidate_described_as_confirmed",
                    f"Technique {row.get('Technique')} presented as '{row.get('Status')}'; "
                    "registry mappings are candidate-only without SOC review.",
                    field="mitre_mappings",
                )
            )

    # 6. An action-guidance ask must not be answered SPL-only with no actions.
    if "analyst_action_guidance" in answer_goal and response_profile == "spl_only" and not recommended:
        findings.append(
            _blocking(
                "final.spl_only_missing_action_guidance",
                "Answer goal requested analyst action guidance but the answer is SPL-only "
                "with no recommended actions.",
                field="recommended_actions",
            )
        )

    visible_text = _visible_analyst_text(analyst_response, visible_message=visible_message)
    negated = _has_negated_compromise_wording(visible_text)

    # 7–10. Unsafe positive claims without supporting evidence.
    for guard_id, pattern, field in _UNSAFE_POSITIVE_PATTERNS:
        if re.search(pattern, visible_text, flags=re.IGNORECASE) and not negated:
            findings.append(
                _blocking(
                    guard_id,
                    f"Unsafe wording detected in analyst-visible text ({pattern}).",
                    field=field,
                )
            )

    # 11. Do not describe SPL as executed when execution was review-gated or not run.
    exec_label = str(
        getattr(analyst_response, "execution_status_label", None)
        or contract.get("execution_status_label")
        or ""
    )
    if re.search(r"\b(spl (was )?executed|executed spl)\b", visible_text, flags=re.IGNORECASE):
        allowed_executed = exec_label in {
            "executed_mock_evidence",
            "executed_live_evidence",
            "mock_executed",
            "live_executed",
        }
        if not allowed_executed:
            findings.append(
                _blocking(
                    "final.unsafe_execution_claim",
                    "Answer describes SPL as executed although execution was review-gated or not run.",
                    field="direct_answer_summary",
                )
            )

    # 12. Visible MITRE rows must not claim evidence-supported without resolver status.
    evidence_statuses = {
        str(key): str(value) for key, value in (decision.get("evidence_statuses") or {}).items()
    }
    for row in getattr(analyst_response, "mitre_mappings", None) or []:
        if not isinstance(row, dict):
            continue
        technique_id = str(row.get("Technique") or row.get("technique_id") or "")
        status_text = str(row.get("Status") or "").lower()
        resolver_status = evidence_statuses.get(technique_id, "")
        if status_text in {"evidence-supported", "evidence supported", "supported"} and resolver_status != "evidence_supported":
            findings.append(
                _blocking(
                    "final.evidence_supported_without_status",
                    f"Technique {technique_id} is shown as evidence-supported without resolver evidence status.",
                    field="mitre_mappings",
                )
            )

    # 13. Destructive containment recommendations require HIL.
    review = human_review or {}
    containment_terms = ("isolate host", "block account", "disable user", "contain endpoint", "wipe endpoint")
    recommended_text = " ".join(str(item) for item in recommended).lower()
    if any(term in recommended_text for term in containment_terms) and not bool(review.get("required")):
        findings.append(
            _blocking(
                "final.containment_without_hil",
                "Containment or destructive remediation recommended without human review gate.",
                field="recommended_actions",
            )
        )

    summary_text = str(getattr(analyst_response, "direct_answer_summary", "") or "")
    if "```" in summary_text or re.search(r"\b(search\s+index=|index=[\w<])", summary_text, flags=re.IGNORECASE):
        findings.append(
            _blocking(
                "final.direct_summary_contains_spl_query",
                "direct_answer_summary contains a draft SPL query or code block.",
                field="direct_answer_summary",
            )
        )

    checklist_items = [
        str(item)
        for item in (
            list(getattr(analyst_response, "analyst_checklist", None) or [])
            + list(getattr(analyst_response, "recommended_actions", None) or [])
            + list(getattr(analyst_response, "investigation_steps", None) or [])
        )
        if str(item).strip()
    ]
    checklist_hits = [
        item
        for item in checklist_items
        if item and _normalize_section_text(item) and _normalize_section_text(item) in _normalize_section_text(summary_text)
    ]
    if len(checklist_hits) >= 2:
        findings.append(
            _blocking(
                "final.direct_summary_contains_full_checklist",
                "direct_answer_summary repeats the SOC checklist instead of leaving it in its owned section.",
                field="direct_answer_summary",
            )
        )

    visible_sections = _visible_section_text(analyst_response, visible_message=visible_message)
    visible_lower = visible_sections.lower()
    if visible_lower.count("lab-only draft spl preview") > 1:
        findings.append(
            _blocking(
                "final.duplicate_review_only_warning",
                "Review-only / lab-only SPL warning appears more than once.",
                field="analyst_response",
            )
        )
    if visible_lower.count("soc review checklist") > 1:
        findings.append(
            _blocking(
                "final.duplicate_soc_checklist",
                "SOC review checklist appears more than once.",
                field="analyst_response",
            )
        )

    severity_label = str(getattr(analyst_response, "severity_label", "") or "")
    if not severity_label or "not assigned" in severity_label.lower():
        for item in getattr(analyst_response, "recommended_actions", None) or []:
            if re.match(r"^P[1-3]\s*[—\-–:]", str(item or "")):
                findings.append(
                    _blocking(
                        "final.priority_prefix_without_severity",
                        "P1/P2/P3 action prefix shown although incident severity is not assigned.",
                        field="recommended_actions",
                    )
                )
                break

    execution_status = str(contract.get("execution_status") or "")
    if "live-backed" in visible_lower and execution_status != "executed":
        findings.append(
            _blocking(
                "final.live_backed_without_execution",
                "Visible answer says live-backed although execution was not executed.",
                field="analyst_response",
            )
        )

    blocking = [item for item in findings if item.severity == "blocking_candidate"]
    if blocking:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="blocked",
            failed_checks=[item.guard_id for item in blocking],
            blocked_reason=blocking[0].message,
            analyst_review_required=True,
            reason="Final-answer validation failed; routing to analyst review (fail closed).",
        )
    return AnswerGuardStatus(
        enabled=True,
        guard_status="passed",
        passed_checks=list(_CHECK_IDS),
        reason="Final answer is consistent with the AnswerContract and the deciders.",
    )


def _visible_analyst_text(analyst_response: Any, *, visible_message: str | None = None) -> str:
    parts: list[str] = []
    if isinstance(visible_message, str) and visible_message.strip():
        parts.append(visible_message)
    for field in (
        "direct_answer_summary",
        "one_sentence_finding",
        "finding_title",
        "severity_safety_note",
        "foundation_sec_analysis",
        "evidence_summary",
        "review_notice",
    ):
        value = getattr(analyst_response, field, None)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    for row in getattr(analyst_response, "recommended_actions", None) or []:
        if isinstance(row, str):
            parts.append(row)
    return " ".join(parts).lower()


def _visible_section_text(analyst_response: Any, *, visible_message: str | None = None) -> str:
    parts: list[str] = [_visible_analyst_text(analyst_response, visible_message=visible_message)]
    for field in (
        "analyst_checklist",
        "recommended_actions",
        "investigation_steps",
        "limitations",
        "missing_evidence",
        "required_evidence",
    ):
        for item in getattr(analyst_response, field, None) or []:
            if isinstance(item, str):
                parts.append(item)
    draft = getattr(analyst_response, "spl_draft_preview", None)
    if isinstance(draft, dict):
        for key in ("warning", "not_catalog_approved_notice"):
            value = draft.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def _normalize_section_text(text: str) -> str:
    cleaned = re.sub(r"^P[1-4]\s*[—\-–:]\s*", "", str(text or ""), flags=re.IGNORECASE)
    cleaned = re.sub(r"^Step\s+\d+\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _has_negated_compromise_wording(text: str) -> bool:
    return bool(
        re.search(
            r"\b(not confirmed|no evidence of|not evidence of|candidate only|is not confirmed)\b",
            text,
            flags=re.IGNORECASE,
        )
    )
