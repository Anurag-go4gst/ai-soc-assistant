from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.orchestration.evidence_mcp_mapping import map_evidence_need_to_mcp_tools
from app.routing.deterministic_router import route_skill_deterministic
from app.routing.governance import (
    ROUTING_MODE_DETERMINISTIC_ONLY,
    ROUTING_MODE_LLM_ASSISTED_SEMANTIC,
    ROUTING_MODE_LLM_PRIMARY_LAB,
    ROUTING_MODE_LLM_SHADOW_ONLY,
    build_llm_semantic_advisory,
    build_route_decision_record,
    clarification_route,
    normalize_assisted_selection,
    requires_context_clarification,
)
from app.routing.llm_planner import route_skill_llm_shadow
from app.routing.route_compare import compare_routes


def route_skill(
    query: str,
    trace_id: str | None = None,
    telemetry: Any | None = None,
    llm_connector: Any | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    trace_id = trace_id or str(uuid4())
    telemetry = telemetry or get_telemetry_connector()
    threshold = settings.routing_deterministic_threshold if threshold is None else threshold
    routing_mode = settings.routing_mode.strip().lower()

    deterministic = route_skill_deterministic(query)
    llm_shadow: dict[str, Any] | None = None
    llm_advisory = None
    selected = dict(deterministic)
    selected_by = "deterministic"
    selection_reason = "deterministic router selected final route"
    disagreements: list[str] = []
    guard_checks = ["llm_cannot_grant_execution", "llm_confidence_metadata_only"]

    if requires_context_clarification(query):
        selected = clarification_route(query)
        selected_by = "deterministic_clarification"
        selection_reason = "context-dependent request requires supplied alert/event details"
        guard_checks.append("deterministic_clarification_override")
    elif routing_mode == ROUTING_MODE_DETERMINISTIC_ONLY:
        selection_reason = "routing_mode deterministic_only"
    elif routing_mode == ROUTING_MODE_LLM_SHADOW_ONLY:
        if settings.routing_llm_shadow_enabled:
            llm_shadow = _safe_llm_shadow(query, llm_connector)
            llm_advisory = build_llm_semantic_advisory(query, llm_shadow)
            selected_by = "shadow_only"
            selection_reason = "LLM shadow compared only; deterministic route selected"
        else:
            selection_reason = "routing_llm_shadow_enabled false; deterministic route selected"
            guard_checks.append("llm_shadow_disabled")
    elif routing_mode == ROUTING_MODE_LLM_ASSISTED_SEMANTIC:
        llm_shadow = _safe_llm_shadow(query, llm_connector)
        llm_advisory = build_llm_semantic_advisory(query, llm_shadow)
        selected, selected_by, disagreements, guard_checks = normalize_assisted_selection(
            query=query,
            deterministic=deterministic,
            advisory=llm_advisory,
        )
        selection_reason = "LLM semantic advisory normalized through deterministic registry and policy"
    elif routing_mode == ROUTING_MODE_LLM_PRIMARY_LAB:
        if not settings.routing_lab_llm_primary_enabled or settings.ai_soc_environment_mode == "production":
            selection_reason = "llm_primary_lab blocked outside explicit lab/dev config; deterministic route selected"
            guard_checks.append("lab_llm_primary_blocked")
        else:
            llm_shadow = _safe_llm_shadow(query, llm_connector)
            llm_advisory = build_llm_semantic_advisory(query, llm_shadow)
            selected, selected_by, disagreements, guard_checks = normalize_assisted_selection(
                query=query,
                deterministic=deterministic,
                advisory=llm_advisory,
            )
            selected_by = "lab_llm_primary" if selected_by == "llm_assisted_semantic_normalized" else selected_by
            selection_reason = "lab LLM primary mode still normalized through deterministic registry and policy"
    else:
        selection_reason = "unsupported routing mode fallback to deterministic route"
        guard_checks.append("unsupported_routing_mode_fallback")

    comparison = compare_routes(llm_shadow, deterministic) if llm_shadow else _deterministic_only_comparison()
    if llm_shadow and llm_shadow.get("skill") != deterministic.get("skill"):
        disagreements.append("selected_skill")
    deterministic_tool_mapping_summary = _deterministic_tool_mapping_summary(llm_advisory)
    confidence = float(selected.get("confidence", 0))
    decision_record = build_route_decision_record(
        query=query,
        routing_mode=routing_mode,
        deterministic=deterministic,
        advisory=llm_advisory,
        selected=selected,
        selected_by=selected_by,
        selection_reason=selection_reason,
        disagreements=disagreements,
        guard_checks=guard_checks,
        deterministic_tool_mapping_summary=deterministic_tool_mapping_summary,
    )

    result = {
        "skill": selected["skill"],
        "tool_plan": list(selected["tool_plan"]),
        "confidence": confidence,
        "reasons": _selected_reasons(selected, selection_reason),
        "trace_id": trace_id,
        "deterministic": deterministic,
        "llm_shadow": llm_shadow,
        "llm_semantic_advisory": llm_advisory.model_dump() if llm_advisory else None,
        "selected": selected,
        "selected_by": selected_by,
        "route_decision": decision_record.model_dump(),
        "comparison": {
            "match": comparison["match"],
            "skill_match": comparison["skill_match"],
            "tool_plan_match": comparison["tool_plan_match"],
            "confidence_delta": comparison["confidence_delta"],
        },
    }

    if settings.routing_compare_logging_enabled:
        _record_routing_telemetry(telemetry, trace_id, query, deterministic, llm_shadow, selected, comparison, confidence)

    return result


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
) -> None:
    event = {
        "query": query,
        "deterministic": deterministic,
        "llm_shadow": llm_shadow,
        "selected": selected,
        "confidence": confidence,
    }
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
