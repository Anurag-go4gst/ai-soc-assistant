"""ChatPipelineState v2 additive projection (C1 / S2).

Packaging-only: derives visibility fields from finalized state without changing
routing authority (`routed` / `selected_skill` remain canonical).
"""

from __future__ import annotations

from typing import Any

from app.chat.node_trace import validate_node_trace
from app.use_cases.content_enrichment import curated_enrichment_trace


def resolve_planning_or_analytic_skill(state: dict[str, Any]) -> str | None:
    route_shadow = state.get("route_plan_shadow")
    if isinstance(route_shadow, dict):
        compare = route_shadow.get("route_authority_compare")
        if isinstance(compare, dict):
            planning = compare.get("planning_primary_skill")
            if isinstance(planning, str) and planning.strip():
                return planning.strip()
    planning_decision = state.get("planning_decision")
    if isinstance(planning_decision, dict):
        planning = planning_decision.get("planning_or_analytic_skill")
        if isinstance(planning, str) and planning.strip():
            return planning.strip()
    return None


def build_execution_decision(
    execution: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(execution, dict) and not isinstance(human_review, dict):
        return None
    execution = execution if isinstance(execution, dict) else {}
    human_review = human_review if isinstance(human_review, dict) else {}
    return {
        "execution_status": execution.get("status"),
        "execution_block_reason": execution.get("block_reason"),
        "human_review_required": bool(human_review.get("required")),
        "review_type": human_review.get("review_type"),
    }


def project_chat_pipeline_state_v2(
    state: dict[str, Any],
    *,
    visibility: dict[str, Any],
    final_answer_validation: dict[str, Any] | None,
    execution: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    use_case_id: str | None,
) -> dict[str, Any]:
    """Return additive v2 keys to merge into ChatPipelineState."""
    routed = state.get("routed") if isinstance(state.get("routed"), dict) else {}
    node_trace_raw = visibility.get("node_trace")
    node_trace: list[dict[str, Any]] = []
    if isinstance(node_trace_raw, list):
        node_trace = validate_node_trace(
            [row for row in node_trace_raw if isinstance(row, dict)]
        )
        node_trace = [row.model_dump() for row in node_trace]

    skill_enrichment = curated_enrichment_trace(use_case_id) if use_case_id else None

    return {
        "live_execution_skill": routed.get("skill"),
        "planning_or_analytic_skill": resolve_planning_or_analytic_skill(state),
        "skill_enrichment": skill_enrichment,
        "spl_template_status": visibility.get("spl_template_status"),
        "mitre_evidence_status": visibility.get("mitre_evidence_status"),
        "execution_decision": build_execution_decision(execution, human_review),
        "final_answer_validation": final_answer_validation,
        "node_trace": node_trace,
    }
