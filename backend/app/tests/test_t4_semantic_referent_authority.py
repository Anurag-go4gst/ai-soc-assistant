"""Unresolved semantic referents belong to T4, not a T1–T3 CLARIFY skip."""

from __future__ import annotations

import json
import time

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import attach_understanding_authority, build_resolved_query_contract
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.config import settings
from app.query_understanding.parser import understand_query

SEMANTIC_REFERENT_QUERY = (
    "has the contractor token we rotated shown up in any other SaaS sign-ins?"
)
BOUND_FOLLOWUP_QUERY = "did it reconnect?"
BOUND_HOST = "ws-finance-04"
HUNT_QUERY = "find signs of credential stuffing against our SSO portal"


@pytest.fixture(autouse=True)
def _t4_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)


def _build_t4(query: str) -> ResolvedQueryContract:
    return build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )


def test_exact_structured_binding_does_not_require_t4_for_the_referent() -> None:
    base = _build_t4(BOUND_FOLLOWUP_QUERY)
    bound = attach_understanding_authority(
        base.model_copy(
            update={
                "entities": {**dict(base.entities or {}), "host": BOUND_HOST},
                "understanding_sufficiency": None,
                "locked_fields": {},
                "unresolved_fields": [],
            }
        )
    )
    assert bound.clarification_required is False
    assert "semantic_referent" not in (bound.unresolved_fields or [])
    assert bound.locked_fields.get("entities.host") == BOUND_HOST
    assert (bound.understanding_sufficiency or {}).get("next_action") != "CLARIFY"


def test_semantic_unresolved_referent_calls_t4() -> None:
    contract = _build_t4(SEMANTIC_REFERENT_QUERY)
    sufficiency = contract.understanding_sufficiency or {}
    assert sufficiency.get("next_action") == "CALL_T4"
    assert contract.clarification_required is False
    assert "semantic_referent" in (contract.unresolved_fields or [])
    assert "clarification_required" not in (contract.locked_fields or {})


def test_t4_valid_clarification_proposal_is_merged() -> None:
    original = _build_t4(SEMANTIC_REFERENT_QUERY)
    enriched = maybe_enrich_t4_semantic(
        original,
        query=SEMANTIC_REFERENT_QUERY,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": (
                    "determine whether a rotated contractor token appeared in other SaaS sign-ins"
                ),
                "semantic_ambiguity": "clarification_required",
                "clarification_required": True,
                "clarification_reason": "which contractor token was rotated",
                "semantic_confidence": 0.4,
            }
        ),
    )
    assert enriched.clarification_required is True
    assert enriched.ambiguity_state == "clarification_required"
    reasons = (enriched.provenance.get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "clarification_without_unresolved_referent" not in reasons


def test_t4_resolves_supplied_conversation_context_without_forced_clarification() -> None:
    base = _build_t4(BOUND_FOLLOWUP_QUERY)
    bound = attach_understanding_authority(
        base.model_copy(
            update={
                "entities": {"host": BOUND_HOST},
                "understanding_sufficiency": None,
                "locked_fields": {},
                "unresolved_fields": [],
            }
        )
    )
    enriched = maybe_enrich_t4_semantic(
        bound,
        query=BOUND_FOLLOWUP_QUERY,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": f"determine whether {BOUND_HOST} reconnected",
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
                "evidence_requirements": [f"network activity from {BOUND_HOST}"],
            }
        ),
    )
    assert enriched.clarification_required is False
    assert BOUND_HOST in (enriched.normalized_goal or "")


def test_t4_unavailable_fail_closed_does_not_guess_referent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_timeout_seconds", 0.15)

    def _hang(_query: str, _contract: ResolvedQueryContract) -> str:
        time.sleep(1.0)
        return json.dumps({"normalized_goal": "tok-7741 reused in Okta"})

    original = _build_t4(SEMANTIC_REFERENT_QUERY)
    enriched = maybe_enrich_t4_semantic(
        original, query=SEMANTIC_REFERENT_QUERY, raw_output_provider=_hang
    )
    trace = enriched.provenance["semantic_t4"]
    assert enriched.clarification_required is True
    assert enriched.clarification_reason == "t4_unavailable_unresolved_semantic_referent"
    assert trace["fallback"] == "deterministic_fail_closed"
    assert trace["degradation"] is True
    assert "tok-7741" not in (enriched.normalized_goal or "")
    assert "tok-7741" not in str(enriched.entities or {})


def test_missing_investigation_evidence_does_not_become_clarification() -> None:
    original = _build_t4(HUNT_QUERY)
    enriched = maybe_enrich_t4_semantic(
        original,
        query=HUNT_QUERY,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "find signs of credential stuffing against the SSO portal",
                "clarification_required": True,
                "clarification_reason": "need a threshold and example logs",
                "semantic_ambiguity": "unambiguous",
            }
        ),
    )
    assert enriched.clarification_required is False
    assert "clarification_without_unresolved_referent" in (
        enriched.provenance["semantic_t4"]["rejected_reasons"]
    )
