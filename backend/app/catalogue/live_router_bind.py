"""Apply unified catalogue tier matches to live routing (fill-blanks only).

COE/manual/session authority and exact 105 runtime-map rows win. This module may
only supply missing ``use_case_id`` / template hints — typically T3 fuzzy alias
binds such as failed-login typos.
"""

from __future__ import annotations

from typing import Any

from app.catalogue.match_tiers import CatalogueMatchResult, match_catalogue_tier
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import get_use_case

_EXACT_AUTHORITY_PATHS = frozenset(
    {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
        "reference_knowledge",
    }
)


def _selection_from_catalogue(match: CatalogueMatchResult) -> UseCaseSelection | None:
    if not match.use_case_id:
        return None
    definition = get_use_case(match.use_case_id)
    if definition is None:
        return None
    confidence = 0.88 if match.tier in {"T1", "T2"} else 0.74
    if match.alias_applied:
        confidence = 0.72
    return UseCaseSelection(
        use_case_id=definition.use_case_id,
        display_name=definition.display_name,
        category=definition.category,
        primary_skill=definition.primary_skill,
        confidence=confidence,
        matched_patterns=list(match.matched_patterns) or [match.match_reason],
        default_spl_template=definition.default_spl_template,
        output_template=definition.output_template,
        required_sources=definition.required_sources,
        optional_sources=definition.optional_sources,
        action_capability_tier=definition.action_capability_tier,
    )


def _has_exact_catalogue_authority(query_understanding: Any | None) -> bool:
    if query_understanding is None:
        return False
    path = str(getattr(query_understanding, "deterministic_match_path", "") or "")
    return path in _EXACT_AUTHORITY_PATHS


def should_apply_catalogue_bind(
    *,
    query_understanding: Any | None,
    selected_use_case: UseCaseSelection | None,
    catalogue: CatalogueMatchResult,
) -> bool:
    if catalogue.tier == "T4" or not catalogue.use_case_id:
        return False
    if catalogue.tier == "T0":
        return False
    if _has_exact_catalogue_authority(query_understanding):
        return False
    if selected_use_case is not None and selected_use_case.use_case_id == catalogue.use_case_id:
        return False
    if selected_use_case is not None and not catalogue.alias_applied:
        return False
    return selected_use_case is None or catalogue.alias_applied


def apply_live_catalogue_bind(
    *,
    query: str,
    query_understanding: Any | None,
    selected_use_case: UseCaseSelection | None,
    routed: dict[str, Any],
    candidate_mappings: dict[str, Any] | None,
) -> tuple[UseCaseSelection | None, dict[str, Any], dict[str, Any]]:
    """Return updated selected use case, routed payload, and candidate mappings."""
    mappings = dict(candidate_mappings or {})
    routed_out = dict(routed)
    catalogue = match_catalogue_tier(query, understanding=query_understanding)

    provenance = routed_out.get("routing_provenance")
    provenance_dict = dict(provenance) if isinstance(provenance, dict) else {}
    provenance_dict.update(
        {
            "catalogue_tier": catalogue.tier,
            "catalogue_match_path": catalogue.match_path,
            "catalogue_alias_applied": catalogue.alias_applied,
            "catalogue_entry_id": catalogue.entry_id,
        }
    )
    if catalogue.use_case_id:
        existing_ids = list(provenance_dict.get("mapped_use_case_ids") or [])
        if not existing_ids:
            provenance_dict["mapped_use_case_ids"] = [catalogue.use_case_id]
    routed_out["routing_provenance"] = provenance_dict

    mappings.setdefault("catalogue_tier", catalogue.tier)
    mappings.setdefault("catalogue_match_path", catalogue.match_path)
    mappings["catalogue_alias_applied"] = catalogue.alias_applied
    if catalogue.use_case_id and not mappings.get("use_case_ids"):
        mappings["use_case_ids"] = [catalogue.use_case_id]
    if catalogue.question_ref and not mappings.get("question_ref"):
        mappings["question_ref"] = catalogue.question_ref

    use_case_out = selected_use_case
    if should_apply_catalogue_bind(
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        catalogue=catalogue,
    ):
        bound = _selection_from_catalogue(catalogue)
        if bound is not None:
            use_case_out = bound
            mappings["use_case_ids"] = [bound.use_case_id]
            mappings["catalogue_bind_reason"] = catalogue.match_reason

    return use_case_out, routed_out, mappings
