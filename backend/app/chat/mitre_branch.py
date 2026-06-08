from __future__ import annotations

from typing import Any

from app.chat.contracts.mitre_branch import MitreBranchResult, MitreTechniqueEvidenceStatus
from app.chat.negative_evidence_extractor import extract_negative_evidence
from app.config import settings
from app.threat.mitre_decision import MitreDecision, resolve_mitre_decision
from app.threat.mitre_kb import MitreMappingDecision
from app.threat.mitre_registry_enrichment import registry_mitre_metadata
from app.use_cases.content_enrichment import resolve_use_case_activation


def planner_mitre_branch_suppressed_decision(
    *,
    use_case_id: str | None,
    question_ref: str | None,
    reason: str = "planner_did_not_select_mitre_branch",
) -> dict[str, Any]:
    """Fail-closed MITRE decision when planner branch authority blocks visible mapping."""
    return MitreDecision(
        mitre_status="not_applicable",
        techniques=[],
        rejected_techniques=[],
        registry_candidates=[],
        not_claimed=[],
        evidence_statuses={},
        evidence_status_details={},
        answer_visible=False,
        requires_alert_context=False,
        requires_more_context_for_supported_mapping=False,
        reason=(
            "Planner did not schedule MITRE branch; analyst-visible evidence-supported "
            "mapping is suppressed."
        ),
        registry_metadata=None,
    ).model_dump()


def run_mitre_evidence_branch(
    *,
    query: str,
    question_ref: str | None,
    use_case_id: str | None,
    source_refs: list[str],
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    planning_decision: dict[str, Any] | None,
    query_signals: dict[str, Any] | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
    structured_context: dict[str, Any] | None = None,
    alert_context_present: bool = False,
) -> tuple[list[MitreMappingDecision], dict[str, Any] | None, MitreBranchResult]:
    if not settings.ai_soc_planner_mitre_branch_enabled:
        return [], None, MitreBranchResult(status="skipped", reason="planner_mitre_branch_disabled")

    if not _planner_selected_mitre(planning_decision, evidence_plan):
        return [], None, MitreBranchResult(
            status="not_applicable",
            reason="planner_did_not_select_mitre_branch",
            use_case_id=use_case_id,
            question_ref=question_ref,
        )

    activation = resolve_use_case_activation(use_case_id)
    if use_case_id and activation.runtime_support_status in {"metadata_only", "unsupported"}:
        meta = registry_mitre_metadata(question_ref=question_ref, use_case_id=use_case_id)
        candidates = meta.all_mapped_technique_ids() if meta is not None else []
        return [], None, MitreBranchResult(
            status="completed",
            ran=True,
            reason="metadata_only_use_case_mitre_candidates_not_runtime_evidence",
            use_case_id=use_case_id,
            question_ref=question_ref,
            technique_statuses=[
                MitreTechniqueEvidenceStatus(
                    technique_id=technique_id,
                    status="candidate",
                    reason="MITRE registry metadata is candidate-only for metadata-only use cases.",
                )
                for technique_id in candidates
            ],
            candidate_mitre=list(candidates),
            metadata_only_candidates=list(candidates),
        )

    negative_evidence = extract_negative_evidence(
        query_signals=query_signals,
        source_evidence=source_evidence,
        structured_context=structured_context,
    )
    decision = resolve_mitre_decision(
        question_ref=question_ref,
        use_case_id=use_case_id,
        source_refs=source_refs,
        intent_classification=intent_classification,
        evidence_plan=evidence_plan,
        alert_context_present=alert_context_present,
        negative_evidence=negative_evidence,
        use_case_review_guidance=bool((query_signals or {}).get("use_case_review_guidance")),
    )
    branch_status = "requires_context" if decision.requires_alert_context else "completed"
    branch = _branch_result(
        decision=decision,
        status=branch_status,
        use_case_id=use_case_id,
        question_ref=question_ref,
    )
    visible = [MitreMappingDecision(**item) for item in decision.techniques] if decision.answer_visible else []
    return visible, decision.model_dump(), branch


def _planner_selected_mitre(
    planning_decision: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
) -> bool:
    branches = (planning_decision or {}).get("branches")
    if isinstance(branches, list) and "mitre" in {str(item) for item in branches}:
        return True
    return bool((evidence_plan or {}).get("needs_mitre"))


def _branch_result(
    *,
    decision: MitreDecision,
    status: str,
    use_case_id: str | None,
    question_ref: str | None,
) -> MitreBranchResult:
    details = decision.evidence_status_details or {}
    statuses: list[MitreTechniqueEvidenceStatus] = []
    buckets: dict[str, list[str]] = {
        "evidence_supported": [],
        "candidate": [],
        "requires_validation": [],
        "not_claimed": [],
        "ruled_out": [],
    }
    rejected_ids = {str(item) for item in decision.rejected_techniques}
    for technique_id in decision.registry_candidates:
        detail = details.get(technique_id) or {}
        technique_status = str(detail.get("status") or "candidate")
        if technique_id in rejected_ids:
            technique_status = _status_for_rejected_technique(detail)
        if technique_status not in buckets:
            technique_status = "candidate"
        statuses.append(
            MitreTechniqueEvidenceStatus(
                technique_id=technique_id,
                status=technique_status,  # type: ignore[arg-type]
                reason=str(detail.get("reason") or decision.reason),
                evidence_keys=[str(item) for item in detail.get("evidence_keys") or []],
            )
        )
        buckets[technique_status].append(technique_id)

    for technique_id in decision.rejected_techniques:
        tid = str(technique_id)
        if not tid:
            continue
        bucket = _status_for_rejected_technique(details.get(tid) or {})
        if tid not in buckets[bucket]:
            buckets[bucket].append(tid)
    visible_ids = {str(item.get("technique_id") or "") for item in decision.techniques}
    for technique_id in decision.not_claimed:
        tid = str(technique_id)
        if tid and tid not in visible_ids and tid not in buckets["not_claimed"]:
            buckets["not_claimed"].append(tid)

    return MitreBranchResult(
        status=status,  # type: ignore[arg-type]
        ran=True,
        reason=decision.reason,
        use_case_id=use_case_id,
        question_ref=question_ref,
        mitre_decision=decision.model_dump(),
        technique_statuses=statuses,
        evidence_supported_mitre=buckets["evidence_supported"],
        candidate_mitre=buckets["candidate"],
        requires_validation_mitre=buckets["requires_validation"],
        not_claimed_mitre=buckets["not_claimed"],
        ruled_out_mitre=buckets["ruled_out"],
        metadata_only_candidates=list(decision.registry_candidates),
    )


def _status_for_rejected_technique(detail: dict[str, Any]) -> str:
    status = str(detail.get("status") or "").lower()
    reason = str(detail.get("reason") or "").lower()
    if status == "ruled_out":
        return "ruled_out"
    if any(term in reason for term in ("disprov", "ruled out", "policy blocks", "registry-blocked")):
        return "ruled_out"
    return "not_claimed"
