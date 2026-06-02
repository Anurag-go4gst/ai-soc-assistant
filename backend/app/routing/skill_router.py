from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.evidence_mcp_mapping import map_evidence_need_to_mcp_tools
from app.query_understanding.models import QueryUnderstandingResult
from app.query_understanding.parser import understand_query
from app.routing.deterministic_router import LOW_CONFIDENCE_ROUTE, route_skill_deterministic
from app.routing.governance import (
    ROUTING_MODE_DETERMINISTIC_ONLY,
    ROUTING_MODE_LLM_ASSISTED_SEMANTIC,
    ROUTING_MODE_LLM_PRIMARY_LAB,
    ROUTING_MODE_LLM_SHADOW_ONLY,
    _deterministic_uncertain,
    build_llm_semantic_advisory,
    build_route_decision_record,
    clarification_route,
    normalize_assisted_selection,
    requires_context_clarification,
)
from app.routing.llm_planner import route_skill_llm_shadow
from app.routing.route_compare import compare_routes
from app.routing.select_route_from_understanding import select_route_from_understanding

logger = logging.getLogger(__name__)


def resolve_query_understanding(
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
    *,
    qu_failed: bool = False,
) -> tuple[QueryUnderstandingResult | None, bool, bool]:
    """Return (understanding, qu_failed, degraded). Exactly one parse attempt when not pre-supplied."""
    if qu_failed and query_understanding is None:
        return None, True, True
    if query_understanding is not None:
        return query_understanding, False, False
    try:
        return understand_query(query), False, False
    except Exception:
        logger.warning("understand_query failed; deterministic keyword failover", exc_info=True)
        return None, True, True


def route_skill(
    query: str,
    trace_id: str | None = None,
    telemetry: Any | None = None,
    llm_connector: Any | None = None,
    threshold: float | None = None,
    *,
    query_understanding: QueryUnderstandingResult | None = None,
    qu_failed: bool = False,
) -> dict[str, Any]:
    trace_id = trace_id or str(uuid4())
    telemetry = telemetry or get_telemetry_connector()
    threshold = settings.routing_deterministic_threshold if threshold is None else threshold
    routing_mode = settings.routing_mode.strip().lower()

    understanding, qu_failed, degraded = resolve_query_understanding(
        query,
        query_understanding,
        qu_failed=qu_failed,
    )

    llm_shadow: dict[str, Any] | None = None
    llm_advisory = None
    disagreements: list[str] = []
    guard_checks = ["llm_cannot_grant_execution", "llm_confidence_metadata_only"]
    routing_provenance: dict[str, Any]

    if requires_context_clarification(query):
        selected = clarification_route(query)
        selected_by = "deterministic_clarification"
        selection_reason = "context-dependent request requires supplied alert/event details"
        guard_checks.append("deterministic_clarification_override")
        if understanding is not None:
            routing_provenance = _provenance_from_selection(
                understanding,
                selected,
                selected_by,
                "deterministic_clarification",
                qu_failed=qu_failed,
                degraded=degraded,
            )
        else:
            routing_provenance = _failover_provenance(query, selected, selected_by, qu_failed=True, degraded=True)
        base_route = dict(selected)
    elif understanding is None:
        base_route, routing_provenance = _qu_failover_route(query)
        selected = dict(base_route)
        selected_by = routing_provenance.get("selected_by", "keyword_router_failover")
        selection_reason = "understand_query failed; deterministic keyword failover"
        guard_checks.append("qu_parse_failed")
    else:
        base_route, routing_provenance = select_route_from_understanding(understanding, query)
        routing_provenance["qu_failed"] = qu_failed
        routing_provenance["degraded"] = degraded
        selected = dict(base_route)
        selected_by = str(routing_provenance.get("selected_by", "query_understanding"))
        selection_reason = "query understanding selected route"

        if routing_mode == ROUTING_MODE_DETERMINISTIC_ONLY:
            selection_reason = "routing_mode deterministic_only"
        elif qu_failed:
            selection_reason = "qu_failed deterministic failover"
        elif routing_mode == ROUTING_MODE_LLM_SHADOW_ONLY:
            if settings.routing_llm_shadow_enabled:
                llm_shadow = _safe_llm_shadow(query, llm_connector)
                llm_advisory = build_llm_semantic_advisory(query, llm_shadow)
                selected_by = "shadow_only"
                selection_reason = "LLM shadow compared only; deterministic route selected"
            else:
                selection_reason = "routing_llm_shadow_enabled false; deterministic route selected"
                guard_checks.append("llm_shadow_disabled")
        elif routing_mode in (ROUTING_MODE_LLM_ASSISTED_SEMANTIC, ROUTING_MODE_LLM_PRIMARY_LAB):
            if routing_mode == ROUTING_MODE_LLM_PRIMARY_LAB and (
                not settings.routing_lab_llm_primary_enabled or settings.ai_soc_environment_mode == "production"
            ):
                selection_reason = "llm_primary_lab blocked outside explicit lab/dev config; deterministic route selected"
                guard_checks.append("lab_llm_primary_blocked")
            else:
                llm_shadow = _safe_llm_shadow(query, llm_connector)
                llm_advisory = build_llm_semantic_advisory(query, llm_shadow)
                if _qu_route_retains_authority(understanding, base_route):
                    selected_by = str(routing_provenance.get("selected_by", selected_by))
                    selection_reason = "QU route retained; LLM advisory recorded for comparison only"
                    guard_checks.append("qu_route_authority_preserved")
                    if llm_shadow and llm_shadow.get("skill") != base_route.get("skill"):
                        disagreements.append("selected_skill")
                else:
                    selected, selected_by, disagreements, guard_checks = normalize_assisted_selection(
                        query=query,
                        deterministic=base_route,
                        advisory=llm_advisory,
                        understanding=understanding,
                    )
                    if routing_mode == ROUTING_MODE_LLM_PRIMARY_LAB and selected_by == "llm_advisory_validated":
                        selected_by = "lab_llm_primary"
                    selection_reason = "LLM semantic advisory normalized through deterministic registry and policy"
        else:
            selection_reason = "unsupported routing mode fallback to deterministic route"
            guard_checks.append("unsupported_routing_mode_fallback")

    comparison = compare_routes(llm_shadow, base_route) if llm_shadow else _deterministic_only_comparison()
    if llm_shadow and llm_shadow.get("skill") != base_route.get("skill"):
        disagreements.append("selected_skill")

    deterministic_tool_mapping_summary = _deterministic_tool_mapping_summary(llm_advisory)
    confidence = float(selected.get("confidence", 0))

    adjudication_status, adjudication_reason = _resolve_adjudication(
        selected_by=selected_by,
        qu_failed=qu_failed,
        understanding=understanding,
        base_route=base_route,
        advisory=llm_advisory,
        routing_mode=routing_mode,
    )

    decision_record = build_route_decision_record(
        query=query,
        routing_mode=routing_mode,
        deterministic=base_route,
        advisory=llm_advisory,
        selected=selected,
        selected_by=selected_by,
        selection_reason=selection_reason,
        disagreements=disagreements,
        guard_checks=guard_checks,
        deterministic_tool_mapping_summary=deterministic_tool_mapping_summary,
        understanding=understanding,
        qu_failed=qu_failed,
        adjudication_status=adjudication_status,
        adjudication_reason=adjudication_reason,
    )

    routing_provenance["skill"] = selected["skill"]
    routing_provenance["tool_plan"] = list(selected["tool_plan"])
    routing_provenance["confidence"] = confidence
    routing_provenance["selected_by"] = selected_by

    result = {
        "skill": selected["skill"],
        "tool_plan": list(selected["tool_plan"]),
        "confidence": confidence,
        "reasons": _selected_reasons(selected, selection_reason),
        "trace_id": trace_id,
        "deterministic": base_route,
        "llm_shadow": llm_shadow,
        "llm_semantic_advisory": llm_advisory.model_dump() if llm_advisory else None,
        "selected": selected,
        "selected_by": selected_by,
        "routing_provenance": routing_provenance,
        "query_understanding_match_path": routing_provenance.get("deterministic_match_path"),
        "llm_adjudication": {
            "status": decision_record.adjudication_status,
            "reason": decision_record.adjudication_reason,
            "deterministic_reconsidered_after_llm": decision_record.deterministic_reconsidered_after_llm,
            "deterministic_match_path": decision_record.deterministic_match_path,
            "deterministic_question_ref": decision_record.deterministic_question_ref,
            "llm_question_ref_candidate": decision_record.llm_question_ref_candidate,
            "llm_use_case_candidate": decision_record.llm_use_case_candidate,
            "selected_question_ref": decision_record.selected_question_ref,
            "selected_coverage_id": decision_record.selected_coverage_id,
            "selected_by": selected_by,
        },
        "route_decision": decision_record.model_dump(),
        "comparison": {
            "match": comparison["match"],
            "skill_match": comparison["skill_match"],
            "tool_plan_match": comparison["tool_plan_match"],
            "confidence_delta": comparison["confidence_delta"],
        },
    }

    if settings.routing_compare_logging_enabled:
        _record_routing_telemetry(
            telemetry,
            trace_id,
            query,
            base_route,
            llm_shadow,
            selected,
            comparison,
            confidence,
            routing_provenance=routing_provenance,
        )

    return result


def _qu_route_retains_authority(understanding: QueryUnderstandingResult, base_route: dict[str, Any]) -> bool:
    """Exact 105 matches keep query_understanding_105 selected_by; override cannot fire anyway."""
    path = understanding.deterministic_match_path
    if path not in {"exact_105_question", "exact_105_plus_use_case_catalog"}:
        return False
    return not _deterministic_uncertain(base_route, understanding)


def _qu_failover_route(query: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = route_skill_deterministic(query)
    if base.get("skill") == LOW_CONFIDENCE_ROUTE["skill"] and base.get("tool_plan") == LOW_CONFIDENCE_ROUTE["tool_plan"]:
        selected_by = "query_understanding_weak"
        authority = "qu_parse_failed"
    else:
        selected_by = "keyword_router_failover"
        authority = "qu_parse_failed"
    provenance = _failover_provenance(query, base, selected_by, qu_failed=True, degraded=True, authority_source=authority)
    return dict(base), provenance


def _failover_provenance(
    query: str,
    selected: dict[str, Any],
    selected_by: str,
    *,
    qu_failed: bool,
    degraded: bool,
    authority_source: str = "qu_parse_failed",
) -> dict[str, Any]:
    return {
        "skill": selected.get("skill"),
        "tool_plan": list(selected.get("tool_plan", [])),
        "confidence": float(selected.get("confidence", 0)),
        "selected_by": selected_by,
        "authority_source": authority_source,
        "deterministic_match_path": "qu_unavailable",
        "raw_query": query,
        "normalized_query": " ".join(query.lower().split()),
        "qu_failed": qu_failed,
        "degraded": degraded,
        "llm_advisory_recommended": True,
    }


def _provenance_from_selection(
    understanding: QueryUnderstandingResult,
    selected: dict[str, Any],
    selected_by: str,
    authority_source: str,
    *,
    qu_failed: bool,
    degraded: bool,
) -> dict[str, Any]:
    from app.routing.routing_provenance import build_routing_provenance

    return build_routing_provenance(
        understanding,
        selected_by=selected_by,
        authority_source=authority_source,
        skill=str(selected["skill"]),
        tool_plan=list(selected["tool_plan"]),
        confidence=float(selected.get("confidence", 0)),
        qu_failed=qu_failed,
        degraded=degraded,
    )


def _resolve_adjudication(
    *,
    selected_by: str,
    qu_failed: bool,
    understanding: QueryUnderstandingResult | None,
    base_route: dict[str, Any],
    advisory: Any,
    routing_mode: str,
) -> tuple[str, str]:
    if qu_failed:
        return "skipped_qu_failed", "Query understanding failed; LLM adjudication skipped on deterministic failover path."
    if understanding is None:
        return "not_needed", "No query understanding available."
    from app.routing.governance import _adjudication_status

    return _adjudication_status(
        selected_by=selected_by,
        deterministic=base_route,
        understanding=understanding,
        advisory=advisory,
    )


def _selected_reasons(selected: dict[str, Any], selection_reason: str) -> list[str]:
    reasons = list(selected.get("reasons", []))
    if selected.get("tool_plan") == ["needs_clarification"] and not any("needs clarification" in reason for reason in reasons):
        reasons.append("needs clarification before tool execution")
    reasons.append(selection_reason)
    return reasons


def _safe_llm_shadow(query: str, llm_connector: Any | None) -> dict[str, Any] | None:
    try:
        return route_skill_llm_shadow(query, llm_connector=llm_connector)
    except Exception as exc:  # LLM advisory failure must not affect final route.
        return {
            "skill": None,
            "tool_plan": [],
            "confidence": 0.0,
            "reasons": [f"llm_advisory_failed:{type(exc).__name__}"],
            "metadata": {"error": type(exc).__name__},
        }


def _deterministic_only_comparison() -> dict[str, Any]:
    return {
        "match": True,
        "skill_match": True,
        "tool_plan_match": True,
        "confidence_delta": 0.0,
    }


def _deterministic_tool_mapping_summary(llm_advisory: Any | None) -> list[dict[str, Any]]:
    if not llm_advisory:
        return []
    mappings: list[dict[str, Any]] = []
    suggested_tools = list(getattr(llm_advisory, "llm_suggested_mcp_tools", []) or [])
    for need in getattr(llm_advisory, "llm_evidence_needs", []) or []:
        source_type = str(need.get("source_type") or "")
        if not source_type or source_type == "unknown":
            continue
        mapping = map_evidence_need_to_mcp_tools(
            evidence_need=source_type,
            llm_suggested_tool_names=[*suggested_tools, str(need.get("suggested_tool_hint") or "")],
        )
        mappings.append(
            {
                "evidence_need": source_type,
                "deterministic_selected_tool": mapping["selected_mcp_tools"],
                "gated_after_validation_tools": mapping["gated_after_validation_tools"],
                "candidate_only_tools": mapping["candidate_only_tools"],
                "why_selected": "deterministic evidence-need mapping",
                "policy_status": "mapped" if any((mapping["selected_mcp_tools"], mapping["gated_after_validation_tools"], mapping["candidate_only_tools"])) else "ignored",
                "execution_requires_validation": bool(mapping["requires_spl_validation"]),
                "source": "deterministic_tool_mapping",
                "LLM_suggested_tool": suggested_tools,
                "accepted_or_ignored": "ignored_raw_llm_tools",
                "reason_ignored": "LLM tool names are advisory only",
                "warnings": mapping["warnings"],
            }
        )
    return mappings


def _record_routing_telemetry(
    telemetry: Any,
    trace_id: str,
    query: str,
    deterministic: dict[str, Any],
    llm_shadow: dict[str, Any] | None,
    selected: dict[str, Any],
    comparison: dict[str, Any],
    confidence: float,
    *,
    routing_provenance: dict[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "query": query,
        "deterministic": deterministic,
        "llm_shadow": llm_shadow,
        "selected": selected,
        "confidence": confidence,
    }
    if routing_provenance:
        event["deterministic_match_path"] = routing_provenance.get("deterministic_match_path")
        event["mapped_question_ref"] = routing_provenance.get("mapped_question_ref")
        event["mapped_use_case_ids"] = routing_provenance.get("mapped_use_case_ids")
        event["selected_by"] = routing_provenance.get("selected_by")
        event["authority_source"] = routing_provenance.get("authority_source")
        event["near_match_score"] = routing_provenance.get("near_match_score")
        event["provisional_route"] = routing_provenance.get("provisional_route")
    if comparison["match"]:
        telemetry.record_routing_decision(
            trace_id,
            **event,
            disagreement=False,
            disagreement_reason=None,
        )
    else:
        reason = _disagreement_reason(comparison)
        telemetry.record_routing_disagreement(
            trace_id,
            **event,
            disagreement=True,
            disagreement_reason=reason,
        )


def _disagreement_reason(comparison: dict[str, Any]) -> str:
    if not comparison["skill_match"]:
        return "skill_mismatch"
    if not comparison["tool_plan_match"]:
        return "tool_plan_mismatch"
    return "unknown_mismatch"
