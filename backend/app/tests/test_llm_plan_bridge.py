"""T0.5 — LLM-proposed plans validated deterministically; failure = legacy path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.config import settings
from app.planner.llm_plan_bridge import propose_validated_llm_plan


@dataclass
class _FakeResult:
    text: str


class _FakeClient:
    def __init__(self, text: str | None = None, exc: Exception | None = None) -> None:
        self._text = text
        self._exc = exc
        self.calls = 0

    def generate(self, **kwargs: Any) -> _FakeResult:
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return _FakeResult(text=self._text or "")


@pytest.fixture(autouse=True)
def _enable_bridge_flags(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def _proposal(steps: list[dict[str, Any]]) -> str:
    return json.dumps({"steps": steps, "rationale": "test plan"})


def _propose(client: _FakeClient, **overrides: Any):
    kwargs: dict[str, Any] = {
        "query": "Which OT hosts beaconed to rare external domains overnight?",
        "match_path": "out_of_registry",
        "action_mode": "recommend_only",
        "mcp_allowed": False,
        "client": client,
    }
    kwargs.update(overrides)
    return propose_validated_llm_plan(**kwargs)


def test_valid_proposal_becomes_validated_plan() -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval", "args": {}},
                {
                    "resource_id": "spl_lab_draft_family:dns_beaconing_hunt",
                    "purpose": "spl_artifact",
                    "args": {"earliest_time": "-24h", "latest_time": "now"},
                },
            ]
        )
    )
    plan = _propose(client)
    assert plan is not None
    assert plan.plan_source == "llm_proposed_validated"
    assert [step.resource_id for step in plan.steps] == [
        "rag_corpus:soc_kb",
        "spl_lab_draft_family:dns_beaconing_hunt",
    ]
    assert all("llm_proposed_deterministically_validated" in step.policy_checks for step in plan.steps)


def test_unknown_resource_and_blocked_tool_are_dropped_with_reasons() -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                {"resource_id": "made_up:resource", "purpose": "knowledge_retrieval"},
                {"resource_id": "mcp_tool:delete_kvstore_collection", "purpose": "mcp_execution"},
            ]
        )
    )
    plan = _propose(client, mcp_allowed=True)
    assert plan is not None
    assert [step.resource_id for step in plan.steps] == ["rag_corpus:soc_kb"]
    reasons = {item["step"]: item["reason"] for item in plan.provenance["dropped_steps"]}
    assert reasons["made_up:resource"] == "unknown_resource_id"
    assert reasons["mcp_tool:delete_kvstore_collection"] == "resource_blocked"


def test_mcp_step_dropped_when_intent_disallows_mcp() -> None:
    client = _FakeClient(
        _proposal(
            [
                {"resource_id": "mcp_tool:splunk_run_query", "purpose": "mcp_execution"},
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
            ]
        )
    )
    plan = _propose(client, mcp_allowed=False)
    assert plan is not None
    assert [step.resource_id for step in plan.steps] == ["rag_corpus:soc_kb"]
    reasons = {item["reason"] for item in plan.provenance["dropped_steps"]}
    assert "mcp_not_allowed_for_intent" in reasons


def test_raw_spl_args_and_unbounded_windows_rejected() -> None:
    client = _FakeClient(
        _proposal(
            [
                {
                    "resource_id": "spl_lab_draft_family:dns_beaconing_hunt",
                    "purpose": "spl_artifact",
                    "args": {"search_query": "search index=* | delete"},
                },
                {
                    "resource_id": "spl_lab_draft_family:network_threshold_anomaly",
                    "purpose": "spl_artifact",
                    "args": {"earliest_time": "whenever"},
                },
            ]
        )
    )
    plan = _propose(client)
    assert plan is None  # both steps dropped → empty plan → deterministic fallback


def test_client_exception_returns_none_never_raises() -> None:
    client = _FakeClient(exc=RuntimeError("connection refused"))
    assert _propose(client) is None


def test_garbage_output_returns_none() -> None:
    assert _propose(_FakeClient("not json at all")) is None


def test_exact_match_path_never_triggers_bridge() -> None:
    client = _FakeClient(_proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}]))
    assert _propose(client, match_path="exact_105_question") is None
    assert client.calls == 0


def test_flags_off_never_triggers_bridge(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    client = _FakeClient(_proposal([{"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}]))
    assert _propose(client) is None
    assert client.calls == 0


def test_bridge_client_timeout_is_hard_capped(monkeypatch) -> None:
    from dataclasses import dataclass

    import app.planner.llm_plan_bridge as bridge

    @dataclass(frozen=True)
    class _Client:
        timeout_seconds: int = 120

    monkeypatch.setattr(
        "app.llm.clients.local_chat_client.build_synthesis_client_from_settings",
        lambda: _Client(),
    )
    capped = bridge._bridge_client()
    assert capped is not None
    assert capped.timeout_seconds <= bridge._BRIDGE_TIMEOUT_SECONDS_CAP


def test_live_evidence_planning_never_calls_llm_inline(monkeypatch) -> None:
    """Latency guard: the live planning path must not build or call a client,
    even with both bridge flags on; eligible plans carry the deferred marker."""
    from app.chat.evidence_planner import plan_evidence
    from app.chat.intent_classifier import build_query_to_intent
    from app.query_understanding.parser import understand_query

    def _boom() -> None:
        raise AssertionError("LLM client built on live planning path")

    monkeypatch.setattr(
        "app.llm.clients.local_chat_client.build_synthesis_client_from_settings", _boom
    )
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
    if understanding.deterministic_match_path in {"out_of_registry", "near_105_question"}:
        assert plan.resource_plan["provenance"].get("llm_bridge") == "deferred_not_inline"
