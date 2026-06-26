"""T2.1 — skill capability contracts constrain plan composition."""

from __future__ import annotations

import json
from pathlib import Path

from app.chat.contracts.evidence_plan import EvidencePlan
from app.planner.composer import compose_resource_plan
from app.planner.resource_registry import load_resource_registry

CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "skills" / "catalog.json").read_text(encoding="utf-8")
)["skills"]


def _live_plan() -> EvidencePlan:
    return EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=True,
        policy_context_required=False,
        policy_context_recommended=False,
        required_evidence_keys=["user", "src"],
    )


def test_attack_discovery_permits_spl_and_mcp() -> None:
    plan = compose_resource_plan(_live_plan(), skill_id="attack_discovery")
    assert {step.step_id for step in plan.steps} >= {"spl", "mcp"}
    assert not plan.provenance.get("skill_vetoes")


def test_knowledge_recall_vetoes_spl_and_blocks_mcp_step() -> None:
    plan = compose_resource_plan(_live_plan(), skill_id="knowledge_recall")
    assert {step.step_id for step in plan.steps} == {"narration", "mcp"}
    mcp = plan.step_by_id("mcp")
    assert mcp is not None
    assert mcp.status == "blocked_policy"
    assert mcp.status_reason == "skill_contract"
    assert set(plan.provenance["skill_vetoes"]) == {
        "spl_artifact:skill_contract",
        "mcp_execution:skill_contract",
    }


def test_skill_required_evidence_lands_in_policy_checks() -> None:
    plan = compose_resource_plan(_live_plan(), skill_id="attack_discovery")
    spl = plan.step_by_id("spl")
    assert spl is not None
    assert any(check.startswith("skill_required_evidence:") for check in spl.policy_checks)
    assert any("source_evidence" in check for check in spl.policy_checks)


def test_skill_workflow_recorded_in_provenance() -> None:
    plan = compose_resource_plan(_live_plan(), skill_id="attack_discovery")
    assert plan.provenance["skill_id"] == "attack_discovery"
    assert plan.provenance["skill_workflow"][0] == "spl_generation"


def test_unknown_or_missing_skill_changes_nothing() -> None:
    baseline = compose_resource_plan(_live_plan())
    unknown = compose_resource_plan(_live_plan(), skill_id="not_a_skill")
    assert [s.step_id for s in unknown.steps] == [s.step_id for s in baseline.steps]


def test_every_catalog_skill_composes_without_error() -> None:
    registry = load_resource_registry()
    for skill in CATALOG:
        plan = compose_resource_plan(_live_plan(), skill_id=skill["skill_id"], registry=registry)
        assert plan.steps is not None
        # No step may reference a blocked registry resource regardless of skill.
        for step in plan.steps:
            descriptor = registry.by_id(step.resource_id)
            assert descriptor is None or descriptor.availability != "blocked"
