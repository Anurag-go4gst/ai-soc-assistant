"""Plan 8 C0 — ResourcePlan follows final RQC requirements, not primary-skill veto."""

from __future__ import annotations

from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.chat.intent_family_defaults import build_t0_knowledge_stub
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import resource_plan_authority
from app.query_understanding.parser import understand_query
from app.tests.test_skill_contract_planning import _live_plan


def test_composer_keeps_spl_when_primary_skill_is_knowledge_recall() -> None:
    with resource_plan_authority():
        plan = compose_resource_plan(_live_plan(), skill_id="knowledge_recall")
    assert any(step.purpose == "spl_artifact" or step.step_id == "spl" for step in plan.steps)
    assert not plan.provenance.get("skill_vetoes")


def test_rqc_required_spl_overlays_evidence_plan() -> None:
    query = "What is MITRE T1059?"
    qu = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification=build_t0_knowledge_stub(),
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="c0-rqc",
    )
    clear_all_handoffs_for_tests()
    plan, _, _ = plan_evidence_from_canonical(
        canonical,
        state={"resolved_query_contract": {"required_capabilities": ["spl", "mcp"]}},
        intent_classification=build_t0_knowledge_stub(),
        query_understanding=qu,
    )
    assert plan.needs_spl is True
    assert plan.needs_mcp is True
    assert plan.resource_plan is not None
    steps = (plan.resource_plan or {}).get("steps") or []
    ids = {step.get("step_id") for step in steps}
    assert "spl" in ids
