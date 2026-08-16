"""Plan 8 U2 — merge only validated unresolved T4 fields; recompute derived fields."""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import attach_understanding_authority, capabilities_for_intent_family
from app.chat.semantic_t4_understanding import _merge_proposal, _parse_proposal, maybe_enrich_t4_semantic
from app.config import settings
from app.query_understanding.parser import understand_query
from app.chat.resolved_query_builder import build_resolved_query_contract


@pytest.fixture(autouse=True)
def _t4_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)


def _locked_live_contract() -> ResolvedQueryContract:
    query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    base = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    return attach_understanding_authority(
        base.model_copy(
            update={
                "entities": {**dict(base.entities), "source_ip": ["203.0.113.24"]},
                "time_scope": "yesterday",
            }
        )
    )


def _merge(contract: ResolvedQueryContract, payload: dict, query: str) -> ResolvedQueryContract:
    proposal, reason = _parse_proposal(json.dumps(payload))
    assert proposal is not None, reason
    return _merge_proposal(contract, proposal, {"rejected_reasons": []}, query=query)


def test_locked_source_ip_and_time_scope_cannot_be_changed() -> None:
    original = _locked_live_contract()
    assert original.locked_fields.get("entities.source_ip") == ["203.0.113.24"]
    assert original.locked_fields.get("time_scope") == "yesterday"
    merged = _merge(
        original,
        {
            "normalized_goal": "failed vpn admin logins",
            "entities": {"source_ip": "10.0.0.1"},
            "time_scope": "last 7 days",
        },
        "Hunt for CI/CD supply-chain compromise indicators across our environment",
    )
    assert merged.entities.get("source_ip") == ["203.0.113.24"]
    assert merged.time_scope == "yesterday"
    reasons = (merged.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "locked_field_change_rejected:entities.source_ip" in reasons
    assert "locked_field_change_rejected:time_scope" in reasons


def test_capability_and_route_grants_are_rejected() -> None:
    original = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="explain the incident response playbook",
            intent_family="knowledge_only",
            answer_goal="policy_citation",
            ambiguity_state="unambiguous",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            prohibited_capabilities=["spl", "mcp"],
        )
    )
    family_req, family_proh = capabilities_for_intent_family("knowledge_only")
    merged = _merge(
        original,
        {
            "normalized_goal": "run spl against vpn logs",
            "required_capabilities": ["spl", "mcp"],
            "intent_family": "spl_generation_only",
        },
        "explain the incident response playbook",
    )
    assert merged.intent_family == "knowledge_only"
    assert merged.required_capabilities == family_req
    assert family_proh <= merged.prohibited_capabilities
    reasons = (merged.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "locked_field_change_rejected:intent_family" in reasons
    assert "capability_widening_rejected" in reasons


def test_deterministic_clarification_cannot_be_cleared() -> None:
    original = attach_understanding_authority(
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
    merged = _merge(
        original,
        {"clarification_required": False, "ambiguity_state": "unambiguous"},
        "compare this",
    )
    assert merged.clarification_required is True
    assert merged.clarification_reason == "unsafe_run_spl"
    assert merged.ambiguity_state == "policy_blocked"


def test_derived_capabilities_recomputed_from_locked_family() -> None:
    original = _locked_live_contract()
    family_req, _family_proh = capabilities_for_intent_family(original.intent_family)
    merged = _merge(
        original,
        {"normalized_goal": "supply-chain compromise indicators"},
        "Hunt for CI/CD supply-chain compromise indicators across our environment",
    )
    assert family_req <= merged.required_capabilities
    assert "required_capabilities" in original.derived_field_names


def test_fabricated_identifier_is_rejected() -> None:
    original = _locked_live_contract()
    merged = _merge(
        original,
        {"entities": {"user": "suspicious DNS traffic"}},
        "Hunt for CI/CD supply-chain compromise indicators across our environment",
    )
    assert "user" not in (merged.entities or {})
    reasons = (merged.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "entity_not_concrete" in reasons


def test_public_enrichment_path_still_invokes_on_call_t4() -> None:
    original = _locked_live_contract()
    assert (original.understanding_sufficiency or {}).get("next_action") == "CALL_T4"
    enriched = maybe_enrich_t4_semantic(
        original,
        query="Hunt for CI/CD supply-chain compromise indicators across our environment",
        raw_output_provider=lambda _q, _c: json.dumps(
            {"normalized_goal": "supply-chain compromise indicators"}
        ),
    )
    assert enriched.normalized_goal == "supply-chain compromise indicators"
    assert enriched.entities.get("source_ip") == ["203.0.113.24"]
    assert enriched.time_scope == "yesterday"
