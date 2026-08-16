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
    _SEMANTIC_T4_FEW_SHOT,
    _has_unresolved_referent,
    _job_aware_unresolved_schema_names,
    _merge_proposal,
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


DUAL_MEANING_QUERY = "show unusual domain activity from finance systems overnight"


def test_material_dual_meaning_may_clarify_without_deictic_referent() -> None:
    """Fail-first: two material SOC meanings must be askable without a deictic referent.

    'domain activity' can mean DNS/domain-name activity or Active Directory /
    domain authentication. Guessing one would change the investigation.
    """
    assert _has_unresolved_referent(DUAL_MEANING_QUERY) is False
    original = ResolvedQueryContract(
        normalized_goal=DUAL_MEANING_QUERY,
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.4,
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query=DUAL_MEANING_QUERY,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "identify unusual domain activity from finance systems overnight",
                "evidence_requirements": [
                    "which sense of domain activity the analyst means",
                ],
                "competing_hypotheses": [],
                "semantic_ambiguity": "clarification_required",
                "clarification_required": True,
                "clarification_reason": (
                    "domain activity may mean DNS/domain-name lookups or "
                    "Active Directory/domain authentication"
                ),
                "semantic_confidence": 0.5,
            }
        ),
    )
    assert enriched.clarification_required is True
    assert enriched.ambiguity_state == "clarification_required"
    reasons = (enriched.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "clarification_without_unresolved_referent" not in reasons


def test_broad_actionable_hunt_does_not_clarify() -> None:
    query = "find signs of credential stuffing against our SSO portal"
    assert _has_unresolved_referent(query) is False
    original = ResolvedQueryContract(
        normalized_goal=query,
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query=query,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "find signs of credential stuffing against the SSO portal",
                "clarification_required": True,
                "clarification_reason": "need examples of stuffing",
                "semantic_ambiguity": "unambiguous",
                "semantic_confidence": 0.4,
            }
        ),
    )
    assert enriched.clarification_required is False
    assert "clarification_without_unresolved_referent" in (
        enriched.provenance["semantic_t4"]["rejected_reasons"]
    )


def test_missing_evidence_does_not_clarify() -> None:
    query = "find signs of lateral movement across the estate"
    original = ResolvedQueryContract(
        normalized_goal=query,
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query=query,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "identify signs of lateral movement across the estate",
                "clarification_required": True,
                "clarification_reason": "need logs and a detection threshold",
                "semantic_ambiguity": "unambiguous",
            }
        ),
    )
    assert enriched.clarification_required is False


def test_unresolved_referent_still_clarifies() -> None:
    query = "compare this with what happened last week and tell me if it is getting worse"
    assert _has_unresolved_referent(query) is True
    original = ResolvedQueryContract(
        normalized_goal=query,
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    enriched = maybe_enrich_t4_semantic(
        original,
        query=query,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "compare an unnamed current event with last week",
                "clarification_required": True,
                "clarification_reason": "which event 'this' refers to",
                "semantic_ambiguity": "clarification_required",
            }
        ),
    )
    assert enriched.clarification_required is True


def test_locked_unambiguous_meaning_cannot_be_overturned() -> None:
    query = "find signs of credential stuffing against our SSO portal"
    original = ResolvedQueryContract(
        normalized_goal="identify credential stuffing against SSO",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        locked_fields={
            "normalized_goal": "identify credential stuffing against SSO",
            "ambiguity_state": "unambiguous",
            "intent_family": "live_investigation",
            "clarification_required": False,
        },
        unresolved_fields=[],
        understanding_sufficiency={
            "schema_version": "staged_sufficiency_v1",
            "stage": "UNDERSTANDING",
            "status": "PARTIAL",
            "required": [],
            "available": ["normalized_goal"],
            "missing": [],
            "locked": ["normalized_goal", "ambiguity_state", "clarification_required"],
            "unresolved": [],
            "reason_codes": ["unresolved_semantic_fields"],
            "next_action": "CALL_T4",
        },
    )
    proposal, reason = _parse_proposal(
        json.dumps(
            {
                "normalized_goal": "identify credential stuffing against SSO",
                "clarification_required": True,
                "clarification_reason": "domain vs stuffing meaning",
                "semantic_ambiguity": "clarification_required",
            }
        )
    )
    assert proposal is not None, reason
    merged = _merge_proposal(original, proposal, {"rejected_reasons": []}, query=query)
    assert merged.clarification_required is False
    assert merged.ambiguity_state == "unambiguous"
    assert merged.normalized_goal == "identify credential stuffing against SSO"


def test_policy_blocked_cannot_be_overturned() -> None:
    query = "show unusual domain activity from finance systems overnight"
    original = ResolvedQueryContract(
        normalized_goal=query,
        intent_family="clarification_required",
        answer_goal="clarification",
        ambiguity_state="policy_blocked",
        clarification_required=True,
        clarification_reason="unsafe_action",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        prohibited_capabilities=["spl", "mcp"],
    )
    proposal, parse_reason = _parse_proposal(
        json.dumps(
            {
                "normalized_goal": query,
                "clarification_required": True,
                "clarification_reason": "two meanings of domain",
                "semantic_ambiguity": "clarification_required",
            }
        )
    )
    assert proposal is not None, parse_reason
    merged = _merge_proposal(original, proposal, {"rejected_reasons": []}, query=query)
    assert merged.ambiguity_state == "policy_blocked"
    assert merged.clarification_required is True
    assert merged.clarification_reason == "unsafe_action"
    assert "spl" in merged.prohibited_capabilities


def test_one_contrastive_few_shot() -> None:
    assert len(_SEMANTIC_T4_FEW_SHOT) == 1
    example = _SEMANTIC_T4_FEW_SHOT[0]
    assert example["hunt_output"]["clarification_required"] is False
    assert example["meaning_output"]["clarification_required"] is True
    unseen = (
        "show unusual domain activity from finance systems overnight",
        "is this the same campaign as the one we escalated last month?",
        "find signs of credential stuffing against our SSO portal",
    )
    blob = json.dumps(example)
    for query in unseen:
        assert query not in blob


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
