"""Plan 8 U1 — T4 invocation is job-aware and field-constrained."""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import attach_understanding_authority, build_resolved_query_contract
from app.chat.semantic_t4_understanding import (
    _build_semantic_t4_user_prompt,
    _schema_limited_to_unresolved,
    maybe_enrich_t4_semantic,
)
from app.config import settings
from app.query_understanding.parser import understand_query


@pytest.fixture(autouse=True)
def _t4_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)


def _t4_contract() -> ResolvedQueryContract:
    query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    return build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )


def test_t4_invokes_only_when_understanding_permits_call_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _provider(query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(query)
        return json.dumps({"normalized_goal": "supply-chain hunt"})

    contract = _t4_contract()
    assert (contract.understanding_sufficiency or {}).get("next_action") == "CALL_T4"
    maybe_enrich_t4_semantic(contract, query="hunt", raw_output_provider=_provider)
    assert calls == ["hunt"]


def test_clarification_sufficiency_does_not_invoke_t4() -> None:
    calls: list[int] = []

    def _provider(_query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(1)
        return json.dumps({"normalized_goal": "should not run"})

    contract = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="compare this",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="unnamed referent",
            qualification_tier="T4",
            qualification_source="out_of_registry",
        )
    )
    assert (contract.understanding_sufficiency or {}).get("next_action") == "CLARIFY"
    maybe_enrich_t4_semantic(contract, query="compare this", raw_output_provider=_provider)
    assert calls == []


def test_prompt_is_limited_to_locked_map_and_unresolved_fields() -> None:
    contract = _t4_contract()
    prompt = _build_semantic_t4_user_prompt("hunt fragment", contract)
    assert "unresolved_query_fragment" in prompt
    assert "locked_fields_do_not_change" in prompt
    assert "required_capabilities" not in prompt or "unresolved_fields_to_resolve" in prompt
    schema = _schema_limited_to_unresolved(contract)
    assert "intent_family" not in schema["properties"]
    assert "required_capabilities" not in schema["properties"]
    assert "answer_goal" not in schema["properties"]
    assert "normalized_goal" in schema["properties"]
    assert "competing_hypotheses" in schema["properties"]
    assert "semantic_ambiguity" in schema["properties"]


def test_t4_cannot_clear_deterministic_clarification() -> None:
    contract = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="need the alert id",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="alert_id missing",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            prohibited_capabilities=["spl", "mcp"],
        )
    )
    enriched = maybe_enrich_t4_semantic(
        contract,
        query="need the alert id",
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "clarification_required": False,
                "required_capabilities": ["spl", "mcp"],
                "normalized_goal": "run spl",
            }
        ),
    )
    assert enriched.clarification_required is True
    assert enriched.clarification_reason == "alert_id missing"
    assert "spl" in enriched.prohibited_capabilities
