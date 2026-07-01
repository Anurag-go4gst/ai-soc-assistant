"""ResourcePlan Capability Validator (B) for guided hybrid investigation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import ResourceRegistry, load_resource_registry
from app.spl.template_registry import load_spl_templates

CapabilityClass = Literal[
    "metadata_discovery",
    "read_only_lookup",
    "safe_query_execution",
    "freeform_query_execution",
    "action_execution",
    "core_guided",
]

_BLOCKED_REASON = Literal[
    "discovery_not_allowed",
    "spl_review_not_allowed",
    "safe_catalog_not_allowed",
    "freeform_query_blocked",
    "action_tool_blocked",
    "unknown_resource",
    "registry_resource_blocked",
    "policy_tier_exceeded",
]

_CORE_GUIDED_PURPOSES = frozenset(
    {
        "knowledge_retrieval",
        "evidence_collection",
        "context_sufficiency",
        "narration",
    }
)
_METADATA_TOOL_PREFIX = "mcp_tool:splunk_get_"
_FREEFORM_QUERY_TOOL = "mcp_tool:splunk_run_query"


class BlockedResource(BaseModel):
    resource_id: str
    reason_code: _BLOCKED_REASON
    step_id: str | None = None


class GuidedCapabilityValidationResult(BaseModel):
    validated_resource_plan: ResourcePlan
    blocked_resources: list[BlockedResource] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _enabled_template_ids() -> frozenset[str]:
    return frozenset(
        template.template_id
        for template in load_spl_templates()
        if template.enabled
    )


def _capability_class_for_step(step: PlanStep, descriptor: Any | None) -> CapabilityClass:
    purpose = str(step.purpose or "")
    resource_id = str(step.resource_id or "")
    if purpose in _CORE_GUIDED_PURPOSES:
        return "core_guided"
    if purpose == "safe_catalog_query" or resource_id.startswith("spl_template_family:"):
        return "safe_query_execution"
    if purpose == "spl_artifact" or resource_id == "skill:spl_generation":
        return "read_only_lookup"
    if purpose == "mcp_discovery" or resource_id.startswith(_METADATA_TOOL_PREFIX):
        return "metadata_discovery"
    if resource_id == _FREEFORM_QUERY_TOOL or purpose == "mcp_execution":
        return "freeform_query_execution"
    if descriptor is not None and descriptor.availability == "blocked":
        return "action_execution"
    return "read_only_lookup"


def _template_id_from_resource(resource_id: str) -> str | None:
    prefix = "spl_template_family:"
    if resource_id.startswith(prefix):
        return resource_id[len(prefix) :]
    return None


def validate_guided_resource_plan(
    evidence_plan: Any,
    resource_plan: ResourcePlan,
    *,
    registry: ResourceRegistry | None = None,
) -> GuidedCapabilityValidationResult:
    """Validate composed guided ResourcePlan steps against EvidencePlan capabilities."""
    registry = registry or load_resource_registry()
    discovery_allowed = bool(getattr(evidence_plan, "discovery_allowed", False))
    spl_review_allowed = bool(getattr(evidence_plan, "spl_review_allowed", False))
    safe_catalog_allowed = bool(getattr(evidence_plan, "safe_spl_execution_allowed", False))
    freeform_allowed = bool(getattr(evidence_plan, "freeform_spl_execution_allowed", False))
    action_allowed = bool(getattr(evidence_plan, "mcp_action_allowed", False))

    validated_steps: list[PlanStep] = []
    blocked: list[BlockedResource] = []

    for step in resource_plan.steps:
        descriptor = registry.by_id(step.resource_id)
        capability = _capability_class_for_step(step, descriptor)
        reason: _BLOCKED_REASON | None = None

        if descriptor is None and capability != "core_guided":
            reason = "unknown_resource"
        elif descriptor is not None and descriptor.availability == "blocked":
            reason = "registry_resource_blocked"
        elif descriptor is not None and descriptor.policy_tier > 2:
            reason = "policy_tier_exceeded"
        elif capability == "metadata_discovery" and not discovery_allowed:
            reason = "discovery_not_allowed"
        elif capability == "safe_query_execution":
            template_id = _template_id_from_resource(step.resource_id)
            if not safe_catalog_allowed:
                reason = "safe_catalog_not_allowed"
            elif template_id is None or template_id not in _enabled_template_ids():
                reason = "safe_catalog_not_allowed"
        elif capability == "read_only_lookup" and step.purpose == "spl_artifact":
            if not spl_review_allowed:
                reason = "spl_review_not_allowed"
        elif capability == "freeform_query_execution":
            reason = "freeform_query_blocked" if not freeform_allowed else None
        elif capability == "action_execution" and not action_allowed:
            reason = "action_tool_blocked"

        if reason is not None:
            blocked.append(
                BlockedResource(
                    resource_id=step.resource_id,
                    reason_code=reason,
                    step_id=step.step_id,
                )
            )
            continue
        validated_steps.append(step)

    validated = ResourcePlan(
        steps=validated_steps,
        plan_source=resource_plan.plan_source,
        provenance={
            **dict(resource_plan.provenance or {}),
            "guided_capability_validation": {
                "blocked_count": len(blocked),
                "blocked_resources": [item.model_dump() for item in blocked],
            },
        },
    )
    return GuidedCapabilityValidationResult(
        validated_resource_plan=validated,
        blocked_resources=blocked,
    )
