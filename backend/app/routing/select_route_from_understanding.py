"""QU-first route selection (105, 42 catalog, near, weak, keyword fallback)."""

from __future__ import annotations

from typing import Any

from app.coverage.question_runtime_map import question_runtime_entry
from app.query_understanding.models import QueryUnderstandingResult
from app.routing.deterministic_router import LOW_CONFIDENCE_ROUTE, route_skill_deterministic
from app.routing.governance import _tool_plan_for_skill
from app.routing.routing_provenance import build_routing_provenance
from app.routing.skills import valid_skill
from app.use_cases.registry import get_use_case

# Non-enum catalog primary_skill → legacy routing skill (H1 total function).
CATALOG_SKILL_COLLAPSE: dict[str, str] = {
    "action_planning": "knowledge_recall",
    "investigation_notes": "knowledge_recall",
    "mitre_mapping": "knowledge_recall",
    "ticket_drafting": "knowledge_recall",
}

_EXACT_105_PATHS = frozenset({"exact_105_question", "exact_105_plus_use_case_catalog"})


def select_route_from_understanding(
    understanding: QueryUnderstandingResult,
    query: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (base_route dict, routing_provenance)."""
    path = understanding.deterministic_match_path
    keyword_would_have = route_skill_deterministic(query)

    if path in _EXACT_105_PATHS:
        return _route_exact_105(understanding, query, path, keyword_would_have)
    if path == "near_105_question":
        return _route_near_105(understanding, query, keyword_would_have)
    if path == "use_case_catalog":
        return _route_catalog_only(understanding, query, keyword_would_have)
    if path == "out_of_registry":
        return _route_out_of_registry(understanding, query, keyword_would_have)

    base = dict(LOW_CONFIDENCE_ROUTE)
    base["reasons"] = list(base.get("reasons", [])) + [f"unknown_match_path:{path}"]
    provenance = build_routing_provenance(
        understanding,
        selected_by="query_understanding_weak",
        authority_source="query_understanding_weak",
        skill=base["skill"],
        tool_plan=list(base["tool_plan"]),
        confidence=float(base["confidence"]),
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _route_exact_105(
    understanding: QueryUnderstandingResult,
    query: str,
    path: str,
    keyword_would_have: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    ref = understanding.mapped_question_ref
    entry = question_runtime_entry(ref) if ref else None
    registry_bundle = _registry_bundle(entry, understanding, match_source="exact")
    catalog_bundle = _catalog_bundle_if_overlap(understanding)

    skill, tool_plan, reasons, collapsed = _resolve_105_skill(entry, understanding, catalog_bundle)
    selected_by = "query_understanding_105"
    if catalog_bundle and path == "exact_105_plus_use_case_catalog":
        selected_by = "query_understanding_105_catalog"

    if skill is None:
        base = dict(LOW_CONFIDENCE_ROUTE)
        base["reasons"] = list(base.get("reasons", [])) + reasons
        authority = "query_understanding_weak"
        selected_by = "query_understanding_weak"
    else:
        base = {
            "skill": skill,
            "tool_plan": tool_plan,
            "confidence": max(understanding.confidence, 0.75),
            "reasons": reasons,
        }
        authority = "query_understanding_105"

    provenance = build_routing_provenance(
        understanding,
        selected_by=selected_by,
        authority_source=authority,
        skill=base["skill"],
        tool_plan=list(base["tool_plan"]),
        confidence=float(base["confidence"]),
        collapsed_from=collapsed,
        catalog_bundle=catalog_bundle,
        registry_bundle=registry_bundle,
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _route_near_105(
    understanding: QueryUnderstandingResult,
    query: str,
    keyword_would_have: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    ref = understanding.mapped_question_ref
    entry = question_runtime_entry(ref) if ref else None
    registry_bundle = _registry_bundle(entry, understanding, match_source="near")
    catalog_bundle = _catalog_bundle_if_overlap(understanding)

    skill, tool_plan, reasons, collapsed = _resolve_105_skill(entry, understanding, catalog_bundle)
    if skill is None:
        base = dict(LOW_CONFIDENCE_ROUTE)
        base["reasons"] = list(base.get("reasons", [])) + reasons + ["near_105_no_valid_legacy_hint"]
        provenance = build_routing_provenance(
            understanding,
            selected_by="query_understanding_weak",
            authority_source="query_understanding_105_near",
            skill=base["skill"],
            tool_plan=list(base["tool_plan"]),
            confidence=float(base["confidence"]),
            provisional_route=True,
            catalog_bundle=catalog_bundle,
            registry_bundle=registry_bundle,
            keyword_router_would_have_selected=keyword_would_have,
        )
        return base, provenance

    base = {
        "skill": skill,
        "tool_plan": tool_plan,
        "confidence": max(float(understanding.question_registry_match_score or 0.55), 0.55),
        "reasons": reasons + ["near_105_provisional_route_from_question_runtime_map"],
    }
    provenance = build_routing_provenance(
        understanding,
        selected_by="query_understanding_105_near",
        authority_source="query_understanding_105_near",
        skill=skill,
        tool_plan=tool_plan,
        confidence=float(base["confidence"]),
        collapsed_from=collapsed,
        provisional_route=True,
        catalog_bundle=catalog_bundle,
        registry_bundle=registry_bundle,
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _route_catalog_only(
    understanding: QueryUnderstandingResult,
    query: str,
    keyword_would_have: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    use_case_id = understanding.mapped_use_case_ids[0] if understanding.mapped_use_case_ids else None
    use_case = get_use_case(use_case_id) if use_case_id else None
    if use_case is None:
        return _keyword_fallback(understanding, query, keyword_would_have, reason="catalog_use_case_not_found")

    catalog_bundle = {
        "use_case_id": use_case.use_case_id,
        "primary_skill": use_case.primary_skill,
        "matched_patterns": [],
        "confidence": understanding.confidence,
    }
    primary = use_case.primary_skill
    if valid_skill(primary):
        skill = primary
        collapsed = None
        reasons = [f"use_case_catalog:{use_case_id}", f"primary_skill:{primary}"]
    elif primary in CATALOG_SKILL_COLLAPSE:
        skill = CATALOG_SKILL_COLLAPSE[primary]
        collapsed = primary
        reasons = [
            f"use_case_catalog:{use_case_id}",
            f"catalog_skill_collapsed:{primary}->{skill}",
        ]
    else:
        return _keyword_fallback(
            understanding,
            query,
            keyword_would_have,
            reason=f"unknown_catalog_primary_skill:{primary}",
        )

    base = {
        "skill": skill,
        "tool_plan": _tool_plan_for_skill(skill),
        "confidence": max(understanding.confidence, 0.72),
        "reasons": reasons,
    }
    provenance = build_routing_provenance(
        understanding,
        selected_by="query_understanding_catalog",
        authority_source="query_understanding_catalog",
        skill=skill,
        tool_plan=list(base["tool_plan"]),
        confidence=float(base["confidence"]),
        collapsed_from=collapsed,
        catalog_bundle=catalog_bundle,
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _route_out_of_registry(
    understanding: QueryUnderstandingResult,
    query: str,
    keyword_would_have: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if understanding.soc_investigation_shaped:
        base = {
            "skill": "guided_investigation",
            "tool_plan": _tool_plan_for_skill("guided_investigation"),
            "confidence": 0.42,
            "reasons": ["out_of_registry_soc_investigation_rescue", "execution_disabled"],
        }
        provenance = build_routing_provenance(
            understanding,
            selected_by="out_of_registry_investigation_rescue",
            authority_source="guided_investigation_rescue",
            skill=base["skill"],
            tool_plan=list(base["tool_plan"]),
            confidence=float(base["confidence"]),
            keyword_router_would_have_selected=keyword_would_have,
            rescue_mode=True,
            why_not_knowledge_recall="Query requests an investigation process, not a bounded knowledge lookup.",
        )
        return base, provenance
    base = dict(LOW_CONFIDENCE_ROUTE)
    base["reasons"] = list(base.get("reasons", [])) + ["out_of_registry_no_105_or_catalog_match"]
    provenance = build_routing_provenance(
        understanding,
        selected_by="query_understanding_weak",
        authority_source="query_understanding_weak",
        skill=base["skill"],
        tool_plan=list(base["tool_plan"]),
        confidence=float(base["confidence"]),
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _keyword_fallback(
    understanding: QueryUnderstandingResult,
    query: str,
    keyword_would_have: dict[str, Any],
    *,
    reason: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = route_skill_deterministic(query)
    if base.get("skill") == LOW_CONFIDENCE_ROUTE["skill"] and base.get("tool_plan") == LOW_CONFIDENCE_ROUTE["tool_plan"]:
        authority = "query_understanding_weak"
        selected_by = "query_understanding_weak"
    else:
        authority = "keyword_router_fallback"
        selected_by = "keyword_router_fallback"
    base = dict(base)
    base["reasons"] = list(base.get("reasons", [])) + [reason]
    provenance = build_routing_provenance(
        understanding,
        selected_by=selected_by,
        authority_source=authority,
        skill=str(base["skill"]),
        tool_plan=list(base["tool_plan"]),
        confidence=float(base.get("confidence", 0)),
        keyword_router_would_have_selected=keyword_would_have,
    )
    return base, provenance


def _resolve_105_skill(
    entry: dict[str, Any] | None,
    understanding: QueryUnderstandingResult,
    catalog_bundle: dict[str, Any] | None,
) -> tuple[str | None, list[str], list[str], str | None]:
    reasons: list[str] = []
    collapsed: str | None = None

    if entry:
        hint = entry.get("legacy_router_intent_hint")
        if isinstance(hint, str) and valid_skill(hint):
            return hint, _tool_plan_for_skill(hint), [f"105_legacy_hint:{hint}"], None
        reasons.append(f"invalid_legacy_router_intent_hint:{hint}")

    if catalog_bundle:
        cat_skill = catalog_bundle.get("primary_skill")
        if isinstance(cat_skill, str) and valid_skill(cat_skill):
            return cat_skill, _tool_plan_for_skill(cat_skill), [f"105_catalog_overlap:{cat_skill}"], None

    proposed = understanding.mapped_primary_skill
    if proposed and valid_skill(proposed):
        return proposed, _tool_plan_for_skill(proposed), [f"105_proposed_primary_skill:{proposed}"], None

    return None, [], reasons, collapsed


def _registry_bundle(
    entry: dict[str, Any] | None,
    understanding: QueryUnderstandingResult,
    *,
    match_source: str,
) -> dict[str, Any] | None:
    if not entry and not understanding.mapped_question_ref:
        return None
    return {
        "question_ref": understanding.mapped_question_ref,
        "question_number": understanding.mapped_question_number,
        "coverage_id": understanding.mapped_coverage_id,
        "pattern_type": understanding.mapped_pattern_type,
        "operation_type": understanding.mapped_operation_type,
        "legacy_intent_skill": entry.get("legacy_router_intent_hint") if entry else None,
        "match_source": match_source,
        "match_score": understanding.question_registry_match_score,
    }


def _catalog_bundle_if_overlap(understanding: QueryUnderstandingResult) -> dict[str, Any] | None:
    if not understanding.mapped_use_case_ids:
        return None
    use_case_id = understanding.mapped_use_case_ids[0]
    use_case = get_use_case(use_case_id)
    if use_case is None:
        return None
    return {
        "use_case_id": use_case.use_case_id,
        "primary_skill": use_case.primary_skill,
        "matched_patterns": [],
        "confidence": understanding.confidence,
    }
