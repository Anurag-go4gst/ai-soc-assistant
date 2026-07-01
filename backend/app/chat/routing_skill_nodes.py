"""S5 — split live route skill from planning/analytic skill (flag-gated, trace-only).

When ``ai_soc_pipeline_split_routing_nodes_enabled`` is true, these nodes run
after ``init_routing`` and populate additive trace fields without changing
``routed`` / ``selected_skill`` authority.
"""

from __future__ import annotations

from typing import Any

from app.chat.pipeline_state_v2 import resolve_planning_or_analytic_skill
from app.use_cases.content_enrichment import curated_enrichment_trace, load_skill_enrichment


def graph_node_route_live_skill(state: dict[str, Any]) -> dict[str, Any]:
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    live_skill = routed.get("skill")
    trace_row = {
        "node_name": "route_live_skill",
        "input_summary": {"query_present": bool(state.get("effective_query") or state.get("request"))},
        "output_summary": {"live_execution_skill": live_skill},
        "decision_reason": "live_execution_skill mirrors routed.skill (authority unchanged)",
        "guardrail_status": "pass",
        "human_review_required": False,
    }
    existing = list(state.get("split_routing_trace") or [])
    return {
        **state,
        "live_execution_skill": live_skill,
        "split_routing_trace": [*existing, trace_row],
    }


def graph_node_resolve_planning_skill(state: dict[str, Any]) -> dict[str, Any]:
    planning_skill = resolve_planning_or_analytic_skill(state)
    trace_row = {
        "node_name": "resolve_planning_skill",
        "input_summary": {
            "route_plan_shadow_present": isinstance(state.get("route_plan_shadow"), dict),
        },
        "output_summary": {"planning_or_analytic_skill": planning_skill},
        "decision_reason": "planning skill derived from route_authority_compare (non-authoritative)",
        "guardrail_status": "pass",
        "human_review_required": False,
    }
    existing = list(state.get("split_routing_trace") or [])
    return {
        **state,
        "planning_or_analytic_skill": planning_skill,
        "split_routing_trace": [*existing, trace_row],
    }


def graph_node_load_skill_enrichment(state: dict[str, Any]) -> dict[str, Any]:
    use_case_id: str | None = None
    selected = state.get("selected_use_case")
    if selected is not None and hasattr(selected, "use_case_id"):
        use_case_id = getattr(selected, "use_case_id", None)
    elif isinstance(state.get("session_pins"), dict):
        use_case_id = state["session_pins"].get("last_use_case_id")
    enrichment = load_skill_enrichment(use_case_id)
    trace_summary = curated_enrichment_trace(use_case_id)
    trace_row = {
        "node_name": "load_skill_enrichment",
        "input_summary": {"use_case_id": use_case_id},
        "output_summary": {
            "enrichment_loaded": enrichment is not None,
            "trace_summary_present": trace_summary is not None,
        },
        "decision_reason": "curated local enrichment only; GitHub markdown never loaded",
        "guardrail_status": "pass",
        "human_review_required": False,
    }
    existing = list(state.get("split_routing_trace") or [])
    return {
        **state,
        "skill_enrichment": trace_summary,
        "split_routing_trace": [*existing, trace_row],
    }
