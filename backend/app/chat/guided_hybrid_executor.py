"""Execute guided hybrid dispatch from a committed ResourcePlan only."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.chat.canonical_mode import build_canonical_failure_state
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_hybrid_collection import collect_guided_hybrid_evidence
from app.chat.guided_hybrid_dispatch import (
    investigation_plan_from_committed_resource_plan,
    validate_committed_plan_handoff,
)
from app.chat.guided_resource_plan_validator import validate_guided_resource_plan
from app.planner.resource_plan import ResourcePlan


def load_committed_guided_resource_plan(
    state: dict[str, Any],
    evidence_payload: dict[str, Any],
) -> tuple[ResourcePlan | None, dict[str, Any] | None]:
    resource_payload = evidence_payload.get("resource_plan")
    if not isinstance(resource_payload, dict):
        return None, build_canonical_failure_state(
            state,
            outcome="execution_failed",
            reason="guided_missing_committed_resource_plan",
        )
    validated_resource = ResourcePlan.model_validate(resource_payload)
    canonical = state.get("canonical_planning_input")
    if not isinstance(canonical, dict):
        canonical = {}
    trace_block = canonical.get("trace")
    if not isinstance(trace_block, dict):
        trace_block = {}
    handoff_id = trace_block.get("handoff_id")
    handoff_version = trace_block.get("handoff_version")
    mismatch = validate_committed_plan_handoff(
        validated_resource,
        handoff_id=str(handoff_id) if handoff_id else None,
        handoff_version=int(handoff_version) if handoff_version is not None else None,
    )
    if mismatch:
        return None, build_canonical_failure_state(state, outcome="execution_failed", reason=mismatch)
    return validated_resource, None


def build_investigation_projection(
    validated_resource: ResourcePlan,
    *,
    query: str,
    handoff_id: str | None,
    handoff_version: int | None,
) -> InvestigationPlan:
    projection = investigation_plan_from_committed_resource_plan(
        validated_resource,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
    )
    return InvestigationPlan.model_validate(
        {
            "investigation_objective": query,
            "read_only_tool_requests": projection["read_only_tool_requests"],
            "safe_spl_template_requests": projection["safe_spl_template_requests"],
            "refinement_recommended": False,
            "human_review_required": True,
            "plan_source": "deterministic_only",
        }
    )


def collect_from_committed_plan(
    state: dict[str, Any],
    *,
    evidence: EvidencePlan,
    validated_resource: ResourcePlan,
    execute_safe_catalog_spl,
) -> tuple[dict[str, Any], InvestigationPlan, Any]:
    validated_plan = build_investigation_projection(
        validated_resource,
        query=str(state.get("effective_query") or ""),
        handoff_id=(validated_resource.provenance or {}).get("handoff_id"),
        handoff_version=(validated_resource.provenance or {}).get("handoff_version"),
    )
    validation = validate_guided_resource_plan(evidence, validated_resource)
    collection_state, collected_count = collect_guided_hybrid_evidence(
        dict(state),
        validated_resource=validated_resource,
        execute_safe_catalog_spl=execute_safe_catalog_spl,
    )
    llm_result = SimpleNamespace(attempted=False, raw_llm=None)
    return collection_state, validated_plan, (validation, validated_resource, llm_result, collected_count)
