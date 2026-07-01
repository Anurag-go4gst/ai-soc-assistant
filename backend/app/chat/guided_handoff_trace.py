"""Trace spine segment for guided hybrid handoff (REV4 P6)."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_capability_validator import GuidedCapabilityValidationResult
from app.planner.resource_plan import ResourcePlan


def build_guided_handoff_trace(
    *,
    investigation_plan_validated: InvestigationPlan,
    resource_plan_pre_validation: ResourcePlan,
    resource_plan_validated: ResourcePlan,
    blocked_resources: list[dict[str, Any]],
    investigation_plan_raw_llm: dict[str, Any] | None = None,
    evidence_collected: int | None = None,
) -> dict[str, Any]:
    """Build ``control_plane_trace.guided_handoff`` for batch 1."""
    safe_template_ids = [
        step.resource_id.removeprefix("spl_template_family:")
        for step in resource_plan_validated.steps
        if step.purpose == "safe_catalog_query"
    ]
    mcp_tool_ids = [
        step.resource_id
        for step in resource_plan_validated.steps
        if step.purpose == "mcp_discovery"
    ]
    return {
        "investigation_plan_validated": investigation_plan_validated.model_dump(),
        "investigation_plan_raw_llm": investigation_plan_raw_llm,
        "resource_plan_pre_validation": resource_plan_pre_validation.summary(),
        "resource_plan_validated": resource_plan_validated.summary(),
        "blocked_resources": blocked_resources,
        "safe_spl_template_ids": safe_template_ids,
        "mcp_tool_ids": mcp_tool_ids,
        "evidence_planned": len(resource_plan_validated.steps),
        "evidence_collected": 0 if evidence_collected is None else evidence_collected,
        "answer_evidence_refs": [],
    }


def blocked_resources_wire(
    validation: GuidedCapabilityValidationResult,
) -> list[dict[str, Any]]:
    return [item.model_dump() for item in validation.blocked_resources]
