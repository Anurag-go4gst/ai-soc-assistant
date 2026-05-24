from __future__ import annotations

from typing import Any

from app.orchestration.human_review import human_review


def check_context_sufficiency(structured_context: dict[str, Any], source_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    missing_evidence = list(structured_context.get("missing_evidence") or [])
    status = "partial"

    if structured_context.get("context_quality") == "blocked":
        status = "requires_human_review"
        reasons.append("context_collection_blocked")
    if not any(item.get("collection_status") == "collected" for item in source_evidence):
        status = "fail" if status != "requires_human_review" else status
        reasons.append("no_collected_evidence")
    if any(not fact.get("source_refs") for fact in structured_context.get("structured_facts", [])):
        status = "fail"
        reasons.append("structured_fact_missing_source_refs")
    if any(item.get("sensitivity_flags") for item in source_evidence):
        status = "fail"
        reasons.append("sensitive_leak_detected")

    if not reasons and not missing_evidence:
        status = "pass"
    elif status == "partial" and missing_evidence:
        reasons.append("missing_optional_or_required_evidence")

    review = None
    if status == "requires_human_review":
        review = human_review(
            "execution_approval",
            "context_collection_blocked",
            "soc_lead",
            ["approve_execution_after_policy_check", "reject_execution"],
            "Context collection is blocked; synthesis remains disabled until evidence collection is reviewed.",
        )

    return {
        "status": status,
        "synthesis_allowed": False,
        "reasons": sorted(set(reasons)),
        "missing_evidence": sorted(set(missing_evidence)),
        "human_review": review,
    }
