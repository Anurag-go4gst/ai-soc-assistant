"""REV4 batch 1 P5 — ResourcePlan Capability Validator (B)."""

from __future__ import annotations

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.planner.composer import compose_guided_resource_plan
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan


def _hybrid_evidence_plan() -> EvidencePlan:
    return EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        discovery_allowed=True,
        investigation_planning_enabled=True,
        spl_review_allowed=True,
        safe_spl_execution_allowed=True,
        freeform_spl_execution_allowed=False,
        mcp_action_allowed=False,
    )


def test_validator_blocks_discovery_when_capability_false() -> None:
    evidence = _hybrid_evidence_plan().model_copy(update={"discovery_allowed": False})
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="discovery_0",
                resource_id="mcp_tool:splunk_get_info",
                purpose="mcp_discovery",
            )
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert result.validated_resource_plan.steps == []
    assert result.blocked_resources[0].reason_code == "discovery_not_allowed"


def test_validator_blocks_safe_catalog_and_review_spl_when_capabilities_false() -> None:
    evidence = _hybrid_evidence_plan().model_copy(
        update={"safe_spl_execution_allowed": False, "spl_review_allowed": False}
    )
    investigation = build_deterministic_investigation_plan(
        query="How should I investigate unusual outbound traffic from an OT host overnight?"
    ).model_copy(
        update={
            "safe_spl_template_requests": ["dns_beaconing_candidate"],
            "spl_review_requested": True,
        }
    )
    plan = compose_guided_resource_plan(evidence, investigation)
    plan.steps.append(
        PlanStep(
            step_id="spl_review",
            resource_id="skill:spl_generation",
            purpose="spl_artifact",
        )
    )
    result = validate_guided_resource_plan(evidence, plan)
    blocked_reasons = {item.reason_code for item in result.blocked_resources}
    assert "safe_catalog_not_allowed" in blocked_reasons
    assert "spl_review_not_allowed" in blocked_reasons
    assert all(step.purpose != "safe_catalog_query" for step in result.validated_resource_plan.steps)
    assert all(step.step_id != "spl_review" for step in result.validated_resource_plan.steps)


def test_validator_blocks_freeform_query_and_action_tools() -> None:
    evidence = _hybrid_evidence_plan()
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="mcp_exec",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
            ),
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert result.blocked_resources[0].reason_code == "freeform_query_blocked"


def test_registry_declared_capability_class_blocks_freeform_run_query() -> None:
    evidence = _hybrid_evidence_plan()
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="mcp_exec",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
            ),
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert result.blocked_resources[0].reason_code == "freeform_query_blocked"


def test_read_only_lookup_allowed_when_discovery_enabled() -> None:
    evidence = _hybrid_evidence_plan()
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="identity_0",
                resource_id="mcp_tool:splunk_get_user_info",
                purpose="mcp_discovery",
            ),
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert len(result.validated_resource_plan.steps) == 1
    assert result.blocked_resources == []


def test_compose_then_validate_keeps_core_guided_steps() -> None:
    evidence = _hybrid_evidence_plan()
    investigation = InvestigationPlan(
        investigation_objective="Review-only OT hunt",
        hypotheses=["Vendor maintenance"],
        evidence_needed=["Firewall sessions"],
        read_only_tool_requests=["mcp_tool:splunk_get_indexes"],
    )
    plan = compose_guided_resource_plan(evidence, investigation)
    result = validate_guided_resource_plan(evidence, plan)
    step_ids = [step.step_id for step in result.validated_resource_plan.steps]
    assert "rag" in step_ids
    assert "discovery_0" in step_ids
    assert "evidence" in step_ids
    assert evidence.mcp_allowed is False
    assert evidence.freeform_spl_execution_allowed is False
