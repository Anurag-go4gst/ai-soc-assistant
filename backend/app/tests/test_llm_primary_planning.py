"""LLM-primary inline resource planning (item 1.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import graph_node_evidence_planning
from app.config import settings
from app.llm.turn_llm_budget import TurnLlmBudget
from app.planner.executor import execute_plan_dispatch, walk_plan_steps
from app.planner.plan_promotion_merge import apply_llm_primary_resource_plan, merge_floor_with_promoted, planner_hop_budget_blocked
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.tests.test_resource_plan_step_dispatch import _hooks

_OOS = "Strange OT chatter to a brand new external host overnight, anything to hunt?"
_EXACT_105 = "Which hosts are generating the most SMB traffic?"


@dataclass
class _FakeResult:
    text: str


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, **kwargs: Any) -> _FakeResult:
        return _FakeResult(text=self._text)


def _proposal(steps: list[dict[str, Any]]) -> str:
    return json.dumps({"steps": steps, "rationale": "primary planning test"})


@pytest.fixture(autouse=True)
def _enable_primary_planning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)


def _evidence_state(question: str, *, skill: str = "attack_discovery") -> dict[str, Any]:
    qu = understand_query(question)
    q2i = build_query_to_intent(query=question, query_understanding=qu, routed_skill=skill)
    intent = q2i.intent_classification.model_dump()
    return {
        "request": ChatRequest(message=question, session_id="llm-primary-planning"),
        "query_understanding": qu,
        "query_to_intent": q2i.model_dump(),
        "intent_classification": intent,
        "routed": {"skill": skill, "routing_provenance": {"deterministic_match_path": qu.deterministic_match_path}},
        "llm_turn_budget": TurnLlmBudget(deadline_seconds=300.0, max_sidecar_calls=5),
    }


def _fake_propose(client: _FakeClient, *, match_path: str | None = None):
    def _propose(**kwargs: Any):
        from app.planner.llm_plan_bridge import propose_validated_llm_plan

        clean = {k: v for k, v in kwargs.items() if k not in {"client", "match_path"}}
        return propose_validated_llm_plan(
            **clean,
            client=client,
            match_path=match_path or kwargs.get("match_path"),
        )

    return _propose


def test_oos_promoted_plan_addition_drives_dispatch_order(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                {"resource_id": "skill:mitre_mapping", "purpose": "mitre_mapping"},
            ]
        )
    )
    monkeypatch.setattr(
        "app.planner.plan_promotion_merge.propose_validated_llm_plan",
        _fake_propose(client),
    )
    state = graph_node_evidence_planning(_evidence_state(_OOS))
    resource_plan = (state["evidence_plan"].get("resource_plan") or {})
    assert resource_plan.get("provenance", {}).get("llm_bridge") == "promoted"
    purposes = [step["purpose"] for step in resource_plan.get("steps") or []]
    assert "mitre_mapping" in purposes
    mitre_index = purposes.index("mitre_mapping")
    narration_index = purposes.index("narration")
    assert mitre_index < narration_index

    walk = walk_plan_steps(state)
    assert walk is not None
    assert "mitre_mapping" in [step.get("purpose") for step in walk.steps_in_order]


def test_exact_105_floor_retained_when_proposal_omits_required_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    qu = understand_query(_EXACT_105)
    assert qu.deterministic_match_path == "exact_105_question"
    q2i = build_query_to_intent(query=_EXACT_105, query_understanding=qu, routed_skill="attack_discovery")
    intent = q2i.intent_classification.model_dump()
    floor_payload = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
        routed={"skill": "attack_discovery"},
    ).model_dump()
    floor = ResourcePlan.model_validate(floor_payload["resource_plan"])
    floor_purposes = {step.purpose for step in floor.steps}
    assert "spl_artifact" in floor_purposes or "knowledge_retrieval" in floor_purposes

    client = _FakeClient(
        _proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}])
    )
    monkeypatch.setattr(
        "app.planner.plan_promotion_merge.propose_validated_llm_plan",
        _fake_propose(client, match_path="near_105_question"),
    )
    merged, _ = apply_llm_primary_resource_plan(
        floor,
        query=_EXACT_105,
        match_path="near_105_question",
        action_mode="recommend_only",
        mcp_allowed=False,
    )
    merged_purposes = {step.purpose for step in merged.steps}
    assert floor_purposes.issubset(merged_purposes)
    assert merged.provenance.get("llm_bridge") == "promoted"
    assert merged.provenance.get("floor_merge_rejected")


def test_llm_unavailable_keeps_deterministic_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.planner.plan_promotion_merge.propose_validated_llm_plan",
        lambda **kwargs: None,
    )
    state = graph_node_evidence_planning(_evidence_state(_OOS))
    resource_plan = state["evidence_plan"]["resource_plan"]
    assert resource_plan["plan_source"] == "deterministic"
    assert resource_plan["provenance"]["llm_bridge"] == "rejected:no_valid_proposal"


def test_exhausted_budget_skips_planner_with_provenance() -> None:
    budget = TurnLlmBudget(deadline_seconds=1.0, max_sidecar_calls=5)
    floor = ResourcePlan(
        steps=[PlanStep(step_id="rag", resource_id="rag_corpus:soc_kb", purpose="knowledge_retrieval")],
        provenance={"composer": "deterministic_v1"},
    )
    assert planner_hop_budget_blocked(budget) is True
    merged, called = apply_llm_primary_resource_plan(
        floor,
        query=_OOS,
        match_path="out_of_registry",
        action_mode="recommend_only",
        mcp_allowed=False,
        budget=budget,
    )
    assert called is False
    assert merged.provenance["llm_bridge"] == "skipped:budget"


def test_merge_floor_with_promoted_never_drops_floor_steps() -> None:
    floor = ResourcePlan(
        steps=[
            PlanStep(step_id="rag", resource_id="rag_corpus:soc_kb", purpose="knowledge_retrieval"),
            PlanStep(
                step_id="spl",
                resource_id="spl_template_family:auth_failed_login_spike",
                purpose="spl_artifact",
            ),
            PlanStep(step_id="narration", resource_id="llm_role:narration", purpose="narration"),
        ],
        plan_source="deterministic",
        provenance={"composer": "deterministic_v1"},
    )
    promoted = ResourcePlan(
        steps=[
            PlanStep(step_id="llm_0", resource_id="rag_corpus:soc_kb", purpose="knowledge_retrieval"),
        ],
        plan_source="llm_proposed_validated",
        provenance={"llm_bridge": "promoted"},
    )
    merged, rejected = merge_floor_with_promoted(floor=floor, promoted=promoted)
    assert [step.step_id for step in merged.steps] == ["rag", "spl", "narration"]
    assert rejected


def test_promoted_plan_walk_reaches_added_step(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                {
                    "resource_id": "spl_lab_draft_family:dns_beaconing_hunt",
                    "purpose": "spl_artifact",
                },
            ]
        )
    )
    monkeypatch.setattr(
        "app.planner.plan_promotion_merge.propose_validated_llm_plan",
        _fake_propose(client),
    )
    state = graph_node_evidence_planning(_evidence_state(_OOS))
    calls: list[str] = []
    execute_plan_dispatch(state, _hooks(calls))
    assert "workflow_spl" in calls or "rag_early" in calls


def test_in_catalogue_contract_guard_still_green() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "app/tests/test_in_catalogue_contract_guard.py",
            "-q",
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        env={**__import__("os").environ, "PYTHONPATH": "../backend:.."},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
