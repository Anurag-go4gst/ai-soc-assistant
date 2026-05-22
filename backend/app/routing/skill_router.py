from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.config import settings
from app.connectors.telemetry import get_telemetry_connector
from app.routing.deterministic_router import route_skill_deterministic
from app.routing.llm_planner import route_skill_llm_shadow
from app.routing.route_adjudicator import select_route
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

    deterministic = route_skill_deterministic(query)
    llm_shadow = route_skill_llm_shadow(query, llm_connector=llm_connector)
    comparison = compare_routes(llm_shadow, deterministic)
    selected, selection_reason = select_route(deterministic, llm_shadow, threshold)
    confidence = float(selected.get("confidence", 0))

    result = {
        "skill": selected["skill"],
        "tool_plan": list(selected["tool_plan"]),
        "confidence": confidence,
        "reasons": list(selected.get("reasons", [])) + [selection_reason],
        "trace_id": trace_id,
        "deterministic": deterministic,
        "llm_shadow": llm_shadow,
        "selected": selected,
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


def _record_routing_telemetry(
    telemetry: Any,
    trace_id: str,
    query: str,
    deterministic: dict[str, Any],
    llm_shadow: dict[str, Any],
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
