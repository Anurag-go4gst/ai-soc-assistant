"""REV4 batch 2 P12 — guided hybrid evidence collection."""

from __future__ import annotations

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.chat.guided_hybrid_collection import collect_guided_hybrid_evidence
from app.planner.composer import compose_guided_resource_plan


def _hybrid_evidence() -> EvidencePlan:
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
        spl_review_allowed=False,
        safe_spl_execution_allowed=True,
        freeform_spl_execution_allowed=False,
        mcp_action_allowed=False,
    )


def test_collect_guided_hybrid_records_planned_discovery_and_catalog_hops() -> None:
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        hypotheses=["Beaconing"],
        evidence_needed=["DNS and firewall context"],
        read_only_tool_requests=["mcp_tool:splunk_get_metadata"],
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    plan = compose_guided_resource_plan(evidence, investigation)
    validated = validate_guided_resource_plan(evidence, plan).validated_resource_plan
    state, collected_count = collect_guided_hybrid_evidence({}, validated_resource=validated)
    assert collected_count == 0
    hops = state.get("mcp_evidence") or []
    assert len(hops) == 2
    tools = {hop.get("tool") for hop in hops}
    assert "splunk_get_metadata" in tools
    assert "guided_safe_catalog" in tools
    assert all(hop.get("outcome") == "planned" for hop in hops)
    assert all(hop.get("tool") != "splunk_run_query" for hop in hops)
