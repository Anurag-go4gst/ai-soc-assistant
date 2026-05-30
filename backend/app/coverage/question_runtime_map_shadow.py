"""Stage 3L-S6.1: Surface question runtime map on route_plan_shadow (observational only)."""

from __future__ import annotations

from typing import Any

from app.coverage.coverage_loader import coverage_for_id
from app.coverage.question_runtime_map import question_runtime_entry
from app.routing.route_authority_gate import resolve_coverage_id_from_shadow


def _coverage_id_from_compare(shadow: dict[str, Any]) -> str | None:
    compare = shadow.get("route_authority_compare")
    if not isinstance(compare, dict):
        return None
    resolved = compare.get("coverage_id_resolved")
    if isinstance(resolved, str) and resolved.strip():
        return resolved.strip()
    return None


def resolve_question_runtime_map_for_shadow(
    route_plan_shadow: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve S6 map row from shadow coverage_id; does not change routing authority."""
    coverage_id = _coverage_id_from_compare(route_plan_shadow) or resolve_coverage_id_from_shadow(
        route_plan_shadow
    )
    if not coverage_id:
        return None

    manifest_entry = coverage_for_id(coverage_id)
    if manifest_entry is None:
        return {
            "coverage_id": coverage_id,
            "question_ref": None,
            "map_entry_found": False,
            "observation_only": True,
        }

    row = question_runtime_entry(manifest_entry.question_ref)
    if row is None:
        return {
            "coverage_id": coverage_id,
            "question_ref": manifest_entry.question_ref,
            "map_entry_found": False,
            "observation_only": True,
        }

    return {
        "coverage_id": coverage_id,
        "question_ref": manifest_entry.question_ref,
        "map_entry_found": True,
        "observation_only": True,
        "proposed_primary_skill": row.get("proposed_primary_skill"),
        "proposed_operation_type": row.get("proposed_operation_type"),
        "promotion_status": row.get("promotion_status"),
        "s3_authority_ready": row.get("s3_authority_ready"),
        "manifest_coverage_id": row.get("manifest_coverage_id"),
    }


def apply_question_runtime_map_to_shadow(route_plan_shadow: dict[str, Any]) -> dict[str, Any] | None:
    payload = resolve_question_runtime_map_for_shadow(route_plan_shadow)
    route_plan_shadow["question_runtime_map"] = payload
    return payload
