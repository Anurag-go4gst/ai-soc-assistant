"""Phase 3 — shadow-only LLM resource-plan proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.planner.resource_plan_shadow import run_resource_plan_shadow
from app.query_understanding.parser import understand_query


@dataclass
class _FakeResult:
    text: str


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def generate(self, **kwargs: Any) -> _FakeResult:
        self.calls += 1
        return _FakeResult(text=self._text)


@pytest.fixture(autouse=True)
def _enable_shadow_flags(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def _proposal(steps: list[dict[str, Any]]) -> str:
    return json.dumps({"steps": steps, "rationale": "shadow test"})


def test_shadow_proposal_logged_without_promotion() -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval", "args": {}},
            ]
        )
    )
    evidence_plan = {
        "mcp_allowed": False,
        "resource_plan": {
            "plan_source": "deterministic",
            "steps": [{"step_id": "rag_0", "resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}],
            "provenance": {"llm_bridge": "deferred_not_inline"},
        },
    }
    before = json.dumps(evidence_plan["resource_plan"])

    result = run_resource_plan_shadow(
        query="Odd OT chatter overnight — anything to hunt?",
        match_path="out_of_registry",
        evidence_plan=evidence_plan,
        client=client,
    )

    assert client.calls == 1
    assert result.llm_called is True
    assert result.promotion_blocked is True
    assert result.shadow_plan is not None
    assert result.shadow_plan["plan_source"] == "llm_proposed_validated"
    assert json.dumps(evidence_plan["resource_plan"]) == before
    trace = result.to_trace_dict()
    assert trace["shadow_only"] is True
    assert trace["promotion_blocked"] is True


def test_live_evidence_planning_stays_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**kwargs):
        raise AssertionError("LLM client built on live planning path")

    monkeypatch.setattr("app.llm.clients.endpoint_resolver.build_failover_chat_client", _boom)
    query = "Strange OT chatter to a brand new external host overnight, anything to hunt?"
    understanding = understand_query(query)
    result = build_query_to_intent(query=query, query_understanding=understanding)
    plan = plan_evidence(
        result.intent_classification,
        query_to_intent=result.model_dump(),
        query_understanding=understanding,
    )
    assert plan.resource_plan is not None
    assert plan.resource_plan["plan_source"] == "deterministic"

    shadow = run_resource_plan_shadow(
        query=query,
        match_path=understanding.deterministic_match_path,
        evidence_plan=plan.model_dump(),
        client=_FakeClient(_proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}])),
    )
    assert shadow.llm_called is True
    assert plan.resource_plan["plan_source"] == "deterministic"


def test_exact_match_path_skips_shadow() -> None:
    client = _FakeClient(_proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}]))
    result = run_resource_plan_shadow(
        query="Which hosts are generating the most SMB traffic?",
        match_path="exact_105_question",
        evidence_plan={"resource_plan": {"plan_source": "deterministic", "steps": []}},
        client=client,
    )
    assert result.skipped_reason == "match_path_not_eligible"
    assert client.calls == 0


def test_shadow_disabled_when_synthesis_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    client = _FakeClient(_proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}]))
    result = run_resource_plan_shadow(
        query="hunt?",
        match_path="out_of_registry",
        evidence_plan={"resource_plan": {"plan_source": "deterministic", "steps": []}},
        client=client,
    )
    assert result.skipped_reason == "shadow_disabled"
    assert client.calls == 0
