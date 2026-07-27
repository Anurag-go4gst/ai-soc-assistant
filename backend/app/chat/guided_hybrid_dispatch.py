"""Read-only guided hybrid dispatch eligibility helper (shared with pipeline)."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.planner.resource_plan import ResourcePlan


def uses_guided_hybrid_dispatch_from_state(state: dict[str, Any]) -> bool:
    if not settings.ai_soc_guided_hybrid_investigation_enabled:
        return False
    if state.get("processing_lane") == "knowledge_short_circuit":
        return False
    canonical = state.get("canonical_planning_input")
    routing = canonical.get("routing") if isinstance(canonical, dict) and isinstance(canonical.get("routing"), dict) else {}
    answer_goal = str(routing.get("answer_goal") or "")
    planning = state.get("planning_decision")
    path_type = planning.get("path_type") if isinstance(planning, dict) else None
    if path_type != "guided_investigation" and answer_goal != "guided_investigation":
        return False
    evidence = state.get("evidence_plan")
    if not isinstance(evidence, dict):
        return False
    if not evidence.get("resource_plan"):
        return False
    if evidence.get("answer_mode") != "guided_investigation" and answer_goal != "guided_investigation":
        return False
    return evidence.get("investigation_planning_enabled") is True


def investigation_plan_from_committed_resource_plan(
    resource_plan: ResourcePlan,
    *,
    resource_plan_id: str | None = None,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
) -> dict[str, Any]:
    """Execution-local InvestigationPlan projection — not a second final plan."""
    source_step_ids = [step.step_id for step in resource_plan.steps]
    read_only_tools = [
        step.resource_id
        for step in resource_plan.steps
        if step.purpose == "mcp_discovery"
    ]
    safe_spl = [
        step.resource_id.removeprefix("spl_template_family:")
        for step in resource_plan.steps
        if step.purpose == "safe_catalog_query" and step.resource_id.startswith("spl_template_family:")
    ]
    return {
        "resource_plan_id": resource_plan_id or (resource_plan.provenance or {}).get("resource_plan_id"),
        "handoff_id": handoff_id or (resource_plan.provenance or {}).get("handoff_id"),
        "handoff_version": handoff_version or (resource_plan.provenance or {}).get("handoff_version"),
        "source_step_ids": source_step_ids,
        "read_only_tool_requests": read_only_tools,
        "safe_spl_template_requests": safe_spl,
        "refinement_recommended": False,
        "human_review_required": True,
        "plan_source": "deterministic_only",
    }


def validate_committed_plan_handoff(
    resource_plan: ResourcePlan,
    *,
    handoff_id: str | None,
    handoff_version: int | None,
) -> str | None:
    provenance = resource_plan.provenance or {}
    if handoff_id and provenance.get("handoff_id") not in {None, handoff_id}:
        return "handoff_id_mismatch"
    if handoff_version is not None and provenance.get("handoff_version") not in {None, handoff_version}:
        return "handoff_version_mismatch"
    return None
