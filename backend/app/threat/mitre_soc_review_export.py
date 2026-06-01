"""P5-9: SOC review export for per-row MITRE approvals.

Builds the review artifact the SOC team uses to approve or reject
mitre_permitted[] entries for each registry row.

Output schema (per Section C of plan):
  question_ref, coverage_id, primary_operation,
  candidate_mitre_ids[], soc_approved_mitre_ids[],
  status, reviewer, review_date, notes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.threat.mitre_permitted_builder import MitrePermittedResult


def build_soc_review_record(
    result: MitrePermittedResult,
    *,
    coverage_id: str | None = None,
    primary_operation: str | None = None,
    reviewer: str | None = None,
    review_date: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build SOC review artifact for a single registry row.

    soc_approved_mitre_ids is always empty here (report-only).
    SOC team fills this during their review pass.
    """
    candidate_ids = [e.technique_id for e in result.entries if e.in_local_bundle]
    needs_review_ids = [e.technique_id for e in result.entries if not e.in_local_bundle]

    return {
        "question_ref": result.question_ref,
        "coverage_id": coverage_id,
        "primary_operation": primary_operation,
        "use_case_id": result.use_case_id,
        "candidate_mitre_ids": candidate_ids,
        "needs_review_mitre_ids": needs_review_ids,
        "soc_approved_mitre_ids": [],
        "status": result.overall_status,
        "mitre_mapping_source": result.mitre_mapping_source,
        "reviewer": reviewer,
        "review_date": review_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        "notes": notes or "",
        "entries": [e.to_dict() for e in result.entries],
        "export_generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "export_note": (
            "Report-only. soc_approved_mitre_ids requires SOC review. "
            "Only SOC-approved entries may be promoted to mitre_permitted[] with status=supported."
        ),
    }


def build_soc_review_batch(
    results: list[MitrePermittedResult],
    *,
    coverage_map: dict[str, str] | None = None,
    operation_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build batch SOC review export for multiple registry rows."""
    coverage_map = coverage_map or {}
    operation_map = operation_map or {}
    return [
        build_soc_review_record(
            result,
            coverage_id=coverage_map.get(result.question_ref),
            primary_operation=operation_map.get(result.question_ref),
        )
        for result in results
    ]
