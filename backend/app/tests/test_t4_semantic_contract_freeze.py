"""Frozen production T4 semantic proposal contract."""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.contracts.semantic_t4_proposal import (
    FROZEN_SEMANTIC_AMBIGUITY_VALUES,
    FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS,
    SemanticT4Proposal,
)
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.chat.semantic_t4_understanding import (
    _job_aware_unresolved_schema_names,
    _parse_proposal,
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


def test_frozen_proposal_fields_are_exactly_the_validated_contract() -> None:
    assert FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS == (
        "normalized_goal",
        "evidence_requirements",
        "competing_hypotheses",
        "semantic_ambiguity",
        "clarification_required",
        "clarification_reason",
        "semantic_confidence",
    )
    assert FROZEN_SEMANTIC_AMBIGUITY_VALUES == ("unambiguous", "clarification_required")


def test_offered_schema_is_frozen_fields_without_authority_keys() -> None:
    schema = _schema_limited_to_unresolved(_t4_contract())
    offered = set(schema["properties"])
    for field in FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS:
        assert field in offered, field
    for blocked in (
        "intent_family",
        "answer_goal",
        "required_capabilities",
        "prohibited_capabilities",
        "skill",
        "route",
        "spl",
        "mcp",
    ):
        assert blocked not in offered
    names = _job_aware_unresolved_schema_names(_t4_contract())
    assert "competing_hypotheses" in names
    assert "semantic_ambiguity" in names
    assert "semantic_confidence" in names
    assert "intent_family" not in names


def test_legacy_ambiguity_and_confidence_aliases_parse() -> None:
    proposal, reason = _parse_proposal(
        json.dumps(
            {
                "normalized_goal": "identify unusual outbound traffic",
                "ambiguity_state": "unambiguous",
                "clarification_required": False,
                "confidence": 0.55,
                "evidence_requirements": ["outbound volumes versus baseline"],
            }
        )
    )
    assert reason is None
    assert proposal is not None
    assert proposal.semantic_ambiguity == "unambiguous"
    assert proposal.semantic_confidence == 0.55
    assert proposal.ambiguity_state == "unambiguous"


def test_frozen_field_names_parse_without_legacy_aliases() -> None:
    proposal, reason = _parse_proposal(
        json.dumps(
            {
                "normalized_goal": "identify unusual outbound traffic from a finance server",
                "evidence_requirements": ["outbound volumes versus baseline"],
                "competing_hypotheses": ["benign backup traffic", "unauthorized transfer"],
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
                "clarification_reason": None,
                "semantic_confidence": 0.6,
            }
        )
    )
    assert reason is None
    assert proposal is not None
    assert proposal.competing_hypotheses == [
        "benign backup traffic",
        "unauthorized transfer",
    ]
    assert proposal.semantic_ambiguity == "unambiguous"
    assert proposal.semantic_confidence == 0.6


def test_competing_hypotheses_merge_does_not_grant_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _t4_contract()
    enriched = maybe_enrich_t4_semantic(
        original,
        query="a scheduled task named UpdateHelper appeared on twelve workstations",
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "assess whether UpdateHelper is a patch artifact or persistence",
                "competing_hypotheses": [
                    "patch installer",
                    "persistence via scheduled task",
                ],
                "evidence_requirements": ["task command line"],
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
                "semantic_confidence": 0.6,
            }
        ),
    )
    assert "patch installer" in enriched.competing_hypotheses
    assert "persistence via scheduled task" in enriched.competing_hypotheses
    assert enriched.intent_family == original.intent_family
    assert enriched.required_capabilities == original.required_capabilities


def test_semantic_confidence_does_not_overwrite_rqc_confidence() -> None:
    original = ResolvedQueryContract(
        normalized_goal="hunt",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.41,
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query="unusual outbound traffic from a finance server",
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "identify unusual outbound traffic from a finance server",
                "semantic_confidence": 0.91,
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
            }
        ),
    )
    assert enriched.confidence == 0.41
    assert enriched.provenance["semantic_t4"]["semantic_confidence"] == 0.91


def test_proposal_model_round_trip_frozen_contract() -> None:
    payload = {
        "normalized_goal": "x",
        "evidence_requirements": ["a"],
        "competing_hypotheses": ["b"],
        "semantic_ambiguity": "unambiguous",
        "clarification_required": False,
        "clarification_reason": None,
        "semantic_confidence": 0.5,
    }
    model = SemanticT4Proposal.model_validate(payload)
    dumped = model.model_dump()
    for field in FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS:
        assert field in dumped
