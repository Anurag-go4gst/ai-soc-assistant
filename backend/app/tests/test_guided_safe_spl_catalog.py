"""REV4 batch 2 P10 — guided safe SPL catalog allowlist."""

from __future__ import annotations

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.spl.guided_safe_spl_catalog import (
    get_guided_safe_catalog_entry,
    guided_safe_template_ids,
    load_guided_safe_spl_catalog,
)

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def test_guided_safe_spl_catalog_loads_coe_stub() -> None:
    catalog = load_guided_safe_spl_catalog()
    assert catalog.coe_signed is False
    assert "dns_beaconing_candidate" in guided_safe_template_ids()
    entry = get_guided_safe_catalog_entry("dns_beaconing_candidate")
    assert entry is not None
    assert entry.max_rows == 100
    assert entry.max_lookback_hours == 24


def test_validator_a_drops_templates_not_on_guided_catalog() -> None:
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    proposal = {
        "safe_spl_template_requests": [
            "dns_beaconing_candidate",
            "edr_suspicious_process",
        ],
    }
    validated = validate_investigation_plan(baseline, proposal)
    assert validated.safe_spl_template_requests == ["dns_beaconing_candidate"]
    assert any("dropped_unknown_template:edr_suspicious_process" in w for w in validated.validation_warnings)


def _hybrid_evidence_plan(**updates: object) -> EvidencePlan:
    base = EvidencePlan(
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
        discovery_allowed=False,
        investigation_planning_enabled=True,
        spl_review_allowed=False,
        safe_spl_execution_allowed=True,
        freeform_spl_execution_allowed=False,
        mcp_action_allowed=False,
    )
    return base.model_copy(update=updates)


def test_validator_b_blocks_unknown_catalog_template_with_stable_reason() -> None:
    evidence = _hybrid_evidence_plan()
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="safe_catalog_0",
                resource_id="spl_template_family:auth_success_after_failure",
                purpose="safe_catalog_query",
            )
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert result.validated_resource_plan.steps == []
    assert result.blocked_resources[0].reason_code == "catalog_template_not_allowlisted"


def test_validator_b_allows_allowlisted_template_when_capability_on() -> None:
    evidence = _hybrid_evidence_plan()
    plan = ResourcePlan(
        steps=[
            PlanStep(
                step_id="safe_catalog_0",
                resource_id="spl_template_family:dns_beaconing_candidate",
                purpose="safe_catalog_query",
            )
        ]
    )
    result = validate_guided_resource_plan(evidence, plan)
    assert len(result.validated_resource_plan.steps) == 1
    assert result.blocked_resources == []
