"""Build authoritative routing_provenance snapshot from query understanding + selection."""

from __future__ import annotations

from typing import Any

from app.query_understanding.models import QueryUnderstandingResult, RequestedOutputType


def build_routing_provenance(
    understanding: QueryUnderstandingResult,
    *,
    selected_by: str,
    authority_source: str,
    skill: str,
    tool_plan: list[str],
    confidence: float,
    collapsed_from: str | None = None,
    provisional_route: bool = False,
    catalog_bundle: dict[str, Any] | None = None,
    registry_bundle: dict[str, Any] | None = None,
    qu_failed: bool = False,
    degraded: bool = False,
    keyword_router_would_have_selected: dict[str, Any] | None = None,
    rescue_mode: bool = False,
    why_not_knowledge_recall: str | None = None,
) -> dict[str, Any]:
    """Forward every QU field used or preserved for downstream (H2/H4)."""
    use_case_id = None
    if catalog_bundle:
        use_case_id = catalog_bundle.get("use_case_id")
    elif understanding.mapped_use_case_ids:
        use_case_id = understanding.mapped_use_case_ids[0]

    provenance: dict[str, Any] = {
        "skill": skill,
        "tool_plan": list(tool_plan),
        "confidence": confidence,
        "selected_by": selected_by,
        "authority_source": authority_source,
        "deterministic_match_path": understanding.deterministic_match_path,
        "raw_query": understanding.raw_query,
        "normalized_query": understanding.normalized_query,
        "primary_intent": understanding.primary_intent,
        "secondary_intents": list(understanding.secondary_intents),
        "requested_output_type": _output_type_value(understanding.requested_output_type),
        "output_template": understanding.output_template.value
        if hasattr(understanding.output_template, "value")
        else str(understanding.output_template),
        "entities": understanding.entities.model_dump(),
        "ambiguity_flags": list(understanding.ambiguity_flags),
        "clarification_needed": understanding.clarification_needed,
        "clarification_question": understanding.clarification_question,
        "confidence_qu": understanding.confidence,
        "mapped_question_ref": understanding.mapped_question_ref,
        "mapped_question_number": understanding.mapped_question_number,
        "mapped_coverage_id": understanding.mapped_coverage_id,
        "coverage_id": understanding.mapped_coverage_id,
        "mapped_pattern_type": understanding.mapped_pattern_type,
        "pattern_type": understanding.mapped_pattern_type,
        "mapped_operation_type": understanding.mapped_operation_type,
        "operation_type": understanding.mapped_operation_type,
        "question_registry_match_score": understanding.question_registry_match_score,
        "mapped_primary_skill": understanding.mapped_primary_skill,
        "mapped_use_case_ids": list(understanding.mapped_use_case_ids),
        "use_case_id": use_case_id,
        "question_registry_match_source": understanding.question_registry_match_source,
        "near_match_score": understanding.question_registry_match_score,
        "provisional_route": provisional_route,
        "question_registry_observation_only": understanding.question_registry_observation_only,
        "use_case_catalog_size": understanding.use_case_catalog_size,
        "use_case_match_source": understanding.use_case_match_source,
        "registry_warnings": list(understanding.registry_warnings),
        "registry_consistency": understanding.registry_consistency,
        "llm_advisory_recommended": understanding.llm_advisory_recommended,
        "qu_failed": qu_failed,
        "degraded": degraded,
        "soc_investigation_shaped": understanding.soc_investigation_shaped,
        "route_skill_candidate": understanding.route_skill_candidate,
        "intent_candidate": understanding.intent_candidate,
        "triage_signals": dict(understanding.triage_signals),
        "rescue_mode": rescue_mode,
        "why_not_knowledge_recall": why_not_knowledge_recall,
    }
    if collapsed_from:
        provenance["collapsed_from"] = collapsed_from
    if catalog_bundle:
        provenance["catalog_bundle"] = dict(catalog_bundle)
    if registry_bundle:
        provenance["registry_bundle"] = dict(registry_bundle)
    if keyword_router_would_have_selected is not None:
        provenance["keyword_router_would_have_selected"] = keyword_router_would_have_selected
    return provenance


def _output_type_value(value: RequestedOutputType | str) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def degraded_query_understanding_from_failover(query: str, provenance: dict[str, Any]) -> QueryUnderstandingResult:
    """Minimal QU when parse fails (H3) so downstream nodes receive a stable object."""
    from app.query_understanding.models import OutputTemplate, QueryEntities

    return QueryUnderstandingResult(
        raw_query=query,
        normalized_query=str(provenance.get("normalized_query") or " ".join(query.lower().split())),
        primary_intent="unknown",
        requested_output_type=RequestedOutputType.CLARIFICATION,
        output_template=OutputTemplate.CLARIFICATION_RESPONSE,
        entities=QueryEntities(),
        confidence=float(provenance.get("confidence_qu") or provenance.get("confidence") or 0.2),
        deterministic_match_path=str(provenance.get("deterministic_match_path") or "qu_unavailable"),
        llm_advisory_recommended=bool(provenance.get("llm_advisory_recommended", True)),
    )
