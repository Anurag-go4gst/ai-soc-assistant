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


def test_t4_invokes_only_on_abstain_with_semantic_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _provider(query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(query)
        return json.dumps({"normalized_goal": "resolve referent"})

    # Deferred semantic referent is a real ABSTAIN gap — not invented semantic_goal.
    contract = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="compare this with last week",
            intent_family="live_investigation",
            answer_goal="live_results",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="which event this refers to",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.2,
            provenance={"match_path": "out_of_registry", "deterministic_match_path": "out_of_registry"},
        )
    )
    assert "semantic_referent" in (contract.unresolved_fields or [])
    from app.chat.semantic_t4_understanding import _permits_t4_call, abstain_acceptance

    assert abstain_acceptance(contract).decision == "ABSTAIN"
    assert _permits_t4_call(contract) is True
    maybe_enrich_t4_semantic(contract, query="compare this with last week", raw_output_provider=_provider)
    assert calls == ["compare this with last week"]


def test_complete_deterministic_contract_skips_t4_even_on_t4_tier() -> None:
    calls: list[int] = []

    def _provider(_query: str, _contract: ResolvedQueryContract) -> str:
        calls.append(1)
        return json.dumps({"normalized_goal": "should not run"})

    contract = _t4_contract()
    from app.chat.semantic_t4_understanding import _permits_t4_call, abstain_acceptance

    assert abstain_acceptance(contract).decision == "ACCEPT"
    assert _permits_t4_call(contract) is False
    maybe_enrich_t4_semantic(contract, query="hunt", raw_output_provider=_provider)
    assert calls == []


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
            ambiguity_state="policy_blocked",
            clarification_required=True,
            clarification_reason="unsafe_run_spl",
            qualification_tier="T4",
            qualification_source="out_of_registry",
        )
    )
    assert (contract.understanding_sufficiency or {}).get("next_action") == "BLOCK"
    maybe_enrich_t4_semantic(contract, query="compare this", raw_output_provider=_provider)
    assert calls == []


def test_abstain_prompt_uses_full_query_and_explicit_literals_not_patch_list() -> None:
    contract = _t4_contract()
    prompt = _build_semantic_t4_user_prompt("hunt fragment", contract)
    assert "hunt fragment" in prompt
    assert "unresolved_query_fragment" not in prompt
    # P2-B (architecture 2.2 branch B): T1-T3 commit no partial contract, so the
    # T4 prompt no longer carries locked_fields/unresolved_fields "patch only these"
    # framing. It now grounds on the full query plus binding explicit literals.
    assert "locked_fields_do_not_change" not in prompt
    assert "unresolved_fields_to_resolve" not in prompt
    assert "EXPLICIT_USER_LITERAL_CONSTRAINTS" in prompt or "derived_hints_non_authoritative" in prompt
    assert "field_types" not in prompt
    assert "Never contradict EXPLICIT_USER_LITERAL_CONSTRAINTS" in prompt


def test_live_response_format_uses_full_schema_not_unresolved_subset() -> None:
    """Legacy _schema_limited_to_unresolved must not be the live ABSTAIN authority."""
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module._live_single_hop_provider)
    assert "_schema_limited_to_unresolved" not in source
    assert "_SEMANTIC_T4_SCHEMA" in source
    # Legacy helper remains for non-authoritative neighbours; prove it is not live.
    schema = _schema_limited_to_unresolved(_t4_contract())
    assert "normalized_goal" in schema["properties"]
    assert "intent_family" not in schema["properties"]


def test_t4_cannot_clear_deterministic_clarification() -> None:
    contract = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="need the alert id",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="unsafe_run_spl",
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
    assert enriched.clarification_reason == "unsafe_run_spl"
    assert "spl" in enriched.prohibited_capabilities
