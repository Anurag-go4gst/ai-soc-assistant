"""Governance snapshot projection for eval reports.

This helper is intentionally independent of the legacy planner-led shadow graph.
"""

from __future__ import annotations

from typing import Any

from app.schemas.responses import PlaceholderResponse


def governance_snapshot_from_response(response: PlaceholderResponse) -> dict[str, Any]:
    planning = response.planning_decision if isinstance(response.planning_decision, dict) else {}
    mitre_visible = [
        getattr(item, "technique_id", None) or (item.get("technique_id") if isinstance(item, dict) else None)
        for item in (response.mitre_mappings or [])
    ]
    mitre_visible = [item for item in mitre_visible if item]
    spl_validation = response.spl_validation
    execution = response.execution
    human_review = response.human_review
    return {
        "use_case_id": (
            response.selected_use_case.use_case_id
            if response.selected_use_case is not None
            else planning.get("use_case_id")
        ),
        "path_type": planning.get("path_type"),
        "branches": list(planning.get("branches") or []),
        "severity_label": (
            response.severity_decision.severity_label if response.severity_decision is not None else None
        ),
        "mitre_visible": mitre_visible,
        "mitre_answer_visible": (
            response.mitre_decision.get("answer_visible")
            if isinstance(response.mitre_decision, dict)
            else None
        ),
        "spl_approved": spl_validation.approved if spl_validation is not None else None,
        "normalized_spl_present": bool(spl_validation and spl_validation.normalized_spl),
        "execution_status": execution.status if execution is not None else None,
        "execution_intent": execution.execution_intent if execution is not None else None,
        "hil_required": human_review.required if human_review is not None else None,
        "hil_review_type": human_review.review_type if human_review is not None else None,
        "candidate_spl_present": response.candidate_spl is not None,
        "answer_mode": (
            response.evidence_plan.get("answer_mode")
            if isinstance(response.evidence_plan, dict)
            else None
        ),
    }
