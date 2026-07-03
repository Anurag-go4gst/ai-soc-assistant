"""T4.3 — CVE + MITRE skills as planner-selectable resources."""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_planner import plan_evidence
from app.evals.run_out_of_catalogue_scorecard import extract_evidence_classes, load_probes, run_probe
from app.planner.composer import compose_resource_plan
from app.planner.llm_plan_bridge import validate_llm_plan_proposal
from app.planner.resource_registry import clear_resource_registry_cache, load_resource_registry


def _mcp_only_plan(**overrides) -> EvidencePlan:
    base = {
        "answer_mode": "guided_investigation",
        "rag_phase": "rag_only",
        "needs_rag": True,
        "needs_spl": False,
        "needs_mcp": False,
        "needs_mitre": False,
        "spl_allowed": False,
        "mcp_allowed": False,
        "policy_context_required": False,
        "policy_context_recommended": True,
        "required_evidence_keys": ["vulnerability_source"],
    }
    base.update(overrides)
    return EvidencePlan(**base)


@pytest.fixture()
def registry():
    clear_resource_registry_cache()
    return load_resource_registry(reload=True)


def test_registry_has_cve_lookup_skill(registry) -> None:
    row = registry.by_id("skill:cve_lookup")
    assert row is not None
    assert row.kind == "skill"
    assert row.availability == "available"


def test_composer_emits_cve_step_when_vulnerability_required(registry) -> None:
    plan = compose_resource_plan(_mcp_only_plan(), registry=registry)
    cve_steps = [s for s in plan.steps if s.purpose == "cve_lookup"]
    assert len(cve_steps) == 1
    assert cve_steps[0].resource_id == "skill:cve_lookup"
    assert cve_steps[0].step_id == "cve"


def test_cve_investigation_evidence_plan_includes_cve_resource_step() -> None:
    from app.chat.contracts.intent_classification import IntentClassification

    intent = IntentClassification(
        intent_family="cve_investigation",
        primary_intent="cve_investigation",
        query_type="investigation_with_guidance",
        answer_goal=["procedural_steps"],
        confidence=0.8,
        confidence_band="high",
        requires_clarification=False,
        requires_hil=True,
        action_mode="recommend_only",
        reason="cve_investigation_review_only",
        requested_output_type="INVESTIGATION",
    )
    evidence = plan_evidence(intent.model_dump(), user_query="CVE-2024-3400 exposure on edge devices")
    steps = (evidence.resource_plan or {}).get("steps") or []
    assert any(step.get("purpose") == "cve_lookup" for step in steps)
    assert any(step.get("resource_id") == "skill:cve_lookup" for step in steps)


def test_llm_bridge_promotes_cve_lookup(registry) -> None:
    result = validate_llm_plan_proposal(
        {
            "steps": [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                {"resource_id": "skill:cve_lookup", "purpose": "cve_lookup"},
            ],
            "rationale": "cve advisory",
        },
        registry=registry,
        mcp_allowed=False,
        match_path="out_of_registry",
    )
    assert result.plan is not None
    assert any(step.purpose == "cve_lookup" for step in result.plan.steps)


def test_action_proposal_still_deferred(registry) -> None:
    result = validate_llm_plan_proposal(
        {"steps": [{"resource_id": "skill:ticket_drafting", "purpose": "action_proposal"}]},
        registry=registry,
        mcp_allowed=False,
    )
    assert result.plan is None
    assert result.dropped_steps[0]["reason"] == "unknown_purpose"


def test_scorecard_counts_planner_cve_from_resource_plan_step() -> None:
    payload = {
        "evidence_plan": {
            "needs_rag": True,
            "resource_plan": {
                "steps": [
                    {"step_id": "cve", "purpose": "cve_lookup", "resource_id": "skill:cve_lookup", "status": "planned"}
                ]
            },
        }
    }
    classes = extract_evidence_classes(payload)
    assert "cve" in classes


def test_scorecard_mitre_probe_includes_mitre_class() -> None:
    bank = load_probes()
    probe = next(p for p in bank["probes"] if p["probe_id"] == "harvest.oos.oos.mitre.01")
    row = run_probe(probe, offline=True)
    assert row["status"] == "ok", row.get("error")
    assert "mitre" in row["evidence_classes"]
