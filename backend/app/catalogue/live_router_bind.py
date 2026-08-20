"""Apply unified catalogue tier matches to live routing (fill-blanks only).

COE/manual/session authority and exact 105 runtime-map rows win. This module may
only supply missing ``use_case_id`` / template hints — typically T3 fuzzy alias
binds such as failed-login typos.
"""

from __future__ import annotations

from typing import Any

from app.catalogue.match_tiers import (
    CatalogueBindingCandidate,
    build_catalogue_binding_candidate,
)
from app.chat.query_signals import extract_query_signals
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import get_use_case, has_intent_pattern_hit, match_use_cases

_EXACT_AUTHORITY_PATHS = frozenset(
    {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
        "reference_knowledge",
    }
)


def _selection_from_catalogue(match: CatalogueBindingCandidate) -> UseCaseSelection | None:
    if not match.use_case_id:
        return None
    definition = get_use_case(match.use_case_id)
    if definition is None:
        return None
    confidence = 0.88 if match.binding_candidate_tier in {"T1", "T2"} else 0.74
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
    catalogue: CatalogueBindingCandidate,
) -> bool:
    if not catalogue.accepted:
        return False
    if catalogue.binding_candidate_tier == "T4" or not catalogue.use_case_id:
        return False
    if _has_exact_catalogue_authority(query_understanding):
        return False
    if selected_use_case is not None:
        return False
    return True


def reconcile_catalogue_binding_candidate(
    *,
    query: str,
    query_understanding: Any | None,
    selected_use_case: UseCaseSelection | None = None,
) -> CatalogueBindingCandidate:
    """Apply canonical guards before a candidate may alter the effective path."""
    candidate = build_catalogue_binding_candidate(
        query,
        understanding=query_understanding,
    )
    observed = candidate.observed_match_path
    effective = observed
    accepted = candidate.binding_candidate_tier in {"T1", "T2"}
    decision_reason = "observed_catalogue_authority" if accepted else "no_catalogue_bind"

    if candidate.candidate_match_path == "fuzzy_alias_catalog":
        signals = extract_query_signals(query, query_understanding)
        ambiguity_flags = list(
            getattr(query_understanding, "ambiguity_flags", None) or []
        )
        if _has_exact_catalogue_authority(query_understanding):
            decision_reason = "exact_authority_preserved"
        elif signals.get("non_soc_or_out_of_scope"):
            decision_reason = "non_soc_candidate_rejected"
        elif any(
            signals.get(key)
            for key in ("block_or_contain", "explicit_run_spl", "run_execution")
        ):
            decision_reason = "unsafe_candidate_rejected"
        elif ambiguity_flags or signals.get("ambiguous_t2_query"):
            decision_reason = "ambiguous_candidate_rejected"
        elif (
            selected_use_case is not None
            and selected_use_case.use_case_id != candidate.use_case_id
        ):
            decision_reason = "selected_use_case_authority_preserved"
        else:
            effective = "fuzzy_alias_catalog"
            accepted = True
            decision_reason = "bounded_alias_accepted"

    return candidate.model_copy(
        update={
            "effective_match_path": effective,
            "accepted": accepted,
            "decision_reason": decision_reason,
        }
    )


def apply_live_catalogue_bind(
    *,
    query: str,
    query_understanding: Any | None,
    selected_use_case: UseCaseSelection | None,
    routed: dict[str, Any],
    candidate_mappings: dict[str, Any] | None,
) -> tuple[
    UseCaseSelection | None,
    dict[str, Any],
    dict[str, Any],
    CatalogueBindingCandidate,
]:
    """Return fill-blank routing updates plus the typed binding candidate."""
    mappings = dict(candidate_mappings or {})
    routed_out = dict(routed)
    catalogue = reconcile_catalogue_binding_candidate(
        query=query,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
    )

    provenance = routed_out.get("routing_provenance")
    provenance_dict = dict(provenance) if isinstance(provenance, dict) else {}
    provenance_dict.update(
        {
            "catalogue_tier": catalogue.binding_candidate_tier,
            "binding_candidate_tier": catalogue.binding_candidate_tier,
            "catalogue_match_path": catalogue.candidate_match_path,
            "observed_match_path": catalogue.observed_match_path,
            "effective_catalogue_match_path": catalogue.effective_match_path,
            "catalogue_alias_applied": catalogue.alias_applied,
            "catalogue_entry_id": catalogue.entry_id,
            "catalogue_bind_accepted": catalogue.accepted,
            "catalogue_bind_decision_reason": catalogue.decision_reason,
        }
    )
    if catalogue.use_case_id:
        existing_ids = list(provenance_dict.get("mapped_use_case_ids") or [])
        if not existing_ids:
            provenance_dict["mapped_use_case_ids"] = [catalogue.use_case_id]
    routed_out["routing_provenance"] = provenance_dict

    mappings.setdefault("catalogue_tier", catalogue.binding_candidate_tier)
    mappings.setdefault("binding_candidate_tier", catalogue.binding_candidate_tier)
    mappings.setdefault("catalogue_match_path", catalogue.candidate_match_path)
    mappings["observed_match_path"] = catalogue.observed_match_path
    mappings["effective_catalogue_match_path"] = catalogue.effective_match_path
    mappings["catalogue_alias_applied"] = catalogue.alias_applied
    mappings["catalogue_bind_accepted"] = catalogue.accepted
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
        original_committed = match_use_cases(query)
        resurrecting_abstain = not original_committed and (
            not catalogue.alias_applied or has_intent_pattern_hit(query)
        )
        if not resurrecting_abstain:
            bound = _selection_from_catalogue(catalogue)
            if bound is not None:
                use_case_out = bound
                mappings["use_case_ids"] = [bound.use_case_id]
                mappings["catalogue_bind_reason"] = catalogue.match_reason

    return use_case_out, routed_out, mappings, catalogue
