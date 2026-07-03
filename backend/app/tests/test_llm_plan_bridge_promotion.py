"""Plan-proposal promotion validation (item 1.2)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.config import settings
from app.planner.llm_plan_bridge import propose_validated_llm_plan, validate_llm_plan_proposal
from app.planner.resource_registry import load_resource_registry


@dataclass
class _FakeResult:
    text: str


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, **kwargs: Any) -> _FakeResult:
        return _FakeResult(text=self._text)


@pytest.fixture
def registry():
    return load_resource_registry()


def _payload(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"steps": steps, "rationale": "promotion test"}


def test_invented_resource_id_dropped(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                {"resource_id": "made_up:resource", "purpose": "knowledge_retrieval"},
            ]
        ),
        registry=registry,
        mcp_allowed=False,
    )
    assert result.plan is not None
    assert [step.resource_id for step in result.plan.steps] == ["rag_corpus:soc_kb"]
    assert result.llm_bridge == "promoted"
    assert result.plan.provenance["llm_bridge"] == "promoted"
    reasons = {item["step"]: item["reason"] for item in result.dropped_steps}
    assert reasons["made_up:resource"] == "unknown_resource_id"


def test_blocked_and_not_implemented_resources_dropped(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload(
            [
                {"resource_id": "mcp_tool:delete_kvstore_collection", "purpose": "mcp_execution"},
                {"resource_id": "mcp_tool:splunk_get_info", "purpose": "mcp_execution"},
            ]
        ),
        registry=registry,
        mcp_allowed=True,
    )
    assert result.plan is None
    assert result.llm_bridge == "rejected:all_steps_dropped"
    reasons = {item["step"]: item["reason"] for item in result.dropped_steps}
    assert reasons["mcp_tool:delete_kvstore_collection"] == "resource_blocked"
    assert reasons["mcp_tool:splunk_get_info"] == "resource_not_dispatchable"


def test_spl_text_in_args_dropped(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload(
            [
                {
                    "resource_id": "spl_lab_draft_family:dns_beaconing_hunt",
                    "purpose": "spl_artifact",
                    "args": {"search_query": "search index=* | delete"},
                }
            ]
        ),
        registry=registry,
        mcp_allowed=False,
    )
    assert result.plan is None
    assert result.llm_bridge == "rejected:all_steps_dropped"
    assert result.dropped_steps[0]["reason"] == "raw_query_args_not_accepted"


def test_garbage_and_empty_proposals_rejected(registry) -> None:
    invalid = validate_llm_plan_proposal({"rationale": "no steps"}, registry=registry, mcp_allowed=False)
    assert invalid.plan is None
    assert invalid.llm_bridge == "rejected:invalid_payload"

    empty = validate_llm_plan_proposal(_payload([]), registry=registry, mcp_allowed=False)
    assert empty.plan is None
    assert empty.llm_bridge == "rejected:all_steps_dropped"


def test_deferred_action_proposal_rejected(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload([{"resource_id": "rag_corpus:soc_kb", "purpose": "action_proposal"}]),
        registry=registry,
        mcp_allowed=False,
    )
    assert result.plan is None
    assert result.dropped_steps[0]["reason"] == "unknown_purpose"


def test_cve_lookup_promoted_with_registry_skill(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload([{"resource_id": "skill:cve_lookup", "purpose": "cve_lookup"}]),
        registry=registry,
        mcp_allowed=False,
        match_path="out_of_registry",
    )
    assert result.plan is not None
    assert result.plan.steps[0].resource_id == "skill:cve_lookup"


def test_valid_multi_tool_proposal_promoted(registry) -> None:
    result = validate_llm_plan_proposal(
        _payload(
            [
                {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval", "args": {}},
                {
                    "resource_id": "spl_lab_draft_family:dns_beaconing_hunt",
                    "purpose": "spl_artifact",
                    "args": {"earliest_time": "-24h", "latest_time": "now"},
                },
                {"resource_id": "skill:mitre_mapping", "purpose": "mitre_mapping", "args": {}},
            ]
        ),
        registry=registry,
        mcp_allowed=False,
        match_path="out_of_registry",
    )
    assert result.plan is not None
    assert result.llm_bridge == "promoted"
    assert result.plan.provenance["llm_bridge"] == "promoted"
    assert [step.resource_id for step in result.plan.steps] == [
        "rag_corpus:soc_kb",
        "spl_lab_draft_family:dns_beaconing_hunt",
        "skill:mitre_mapping",
    ]
    assert all("llm_proposed_deterministically_validated" in step.policy_checks for step in result.plan.steps)


def test_propose_validated_llm_plan_returns_none_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    client = _FakeClient("not json")
    plan = propose_validated_llm_plan(
        query="OT beacon hunt",
        match_path="out_of_registry",
        action_mode="recommend_only",
        mcp_allowed=False,
        client=client,
    )
    assert plan is None


def test_propose_validated_llm_plan_promotes_valid_multi_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    client = _FakeClient(
        json.dumps(
            _payload(
                [
                    {"resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"},
                    {
                        "resource_id": "spl_template_family:auth_failed_login_spike",
                        "purpose": "spl_artifact",
                    },
                ]
            )
        )
    )
    plan = propose_validated_llm_plan(
        query="Failed login spike overnight",
        match_path="near_105_question",
        action_mode="recommend_only",
        mcp_allowed=False,
        client=client,
    )
    assert plan is not None
    assert plan.provenance["llm_bridge"] == "promoted"
    assert len(plan.steps) == 2
