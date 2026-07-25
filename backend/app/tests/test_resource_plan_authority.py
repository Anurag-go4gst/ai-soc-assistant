"""Guard tests — only plan_evidence_from_canonical may compose ResourcePlan."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import ResourcePlanAuthorityViolation
from app.query_understanding.parser import understand_query


def test_compose_resource_plan_requires_authority() -> None:
    from app.planner import resource_plan_authority as rpa

    plan = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    token = rpa._authority.set(None)
    try:
        with pytest.raises(ResourcePlanAuthorityViolation):
            compose_resource_plan(plan, intent_family="knowledge_only")
    finally:
        rpa._authority.reset(token)


def test_plan_evidence_from_canonical_is_approved_authority() -> None:
    query = "What is CVE-2026-12345?"
    qu = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification={"intent_family": "reference_knowledge", "primary_intent": "knowledge_recall"},
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="cpi:authority-test",
    )
    plan, _, _ = plan_evidence_from_canonical(canonical, query_understanding=qu)
    assert plan.resource_plan is not None


def test_only_approved_modules_compose_resource_plan() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in repo_root.rglob("*.py"):
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith("app/tests/"):
            continue
        if rel in {
            "app/planner/composer.py",
            "app/chat/plan_evidence_from_canonical.py",
            "app/chat/evidence_planner.py",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        if "compose_resource_plan(" in text or "compose_guided_resource_plan(" in text:
            offenders.append(rel)
    assert offenders == [], f"unexpected ResourcePlan composers: {offenders}"
