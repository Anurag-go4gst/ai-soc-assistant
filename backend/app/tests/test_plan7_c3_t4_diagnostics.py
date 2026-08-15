"""Plan 7 C3 — the T4 observation seam must survive being redacted twice.

A live turn redacts the resolved-query contract once into `control_plane_trace`
and again in `debug_summary`. The second pass sees the *already redacted* dict,
which has no `provenance` — so any field read only from `provenance` is silently
erased. That is exactly why the first C3 measurement reported empty
`field_sources` and could not tell a schema-valid echo from a useful completion.

These tests pin the diagnostic contract itself: names and labels only, no values,
and no influence on routing, planning, capabilities or acceptance.
"""

from __future__ import annotations

import json

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.debug_summary import redact_resolved_query
from app.chat.resolved_query_builder import capabilities_for_intent_family
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.config import settings

RESOLVED_ANSWER = {
    "normalized_goal": "identify DNS lookups involving domains that appear algorithmically generated",
    "evidence_requirements": ["DNS lookup events containing domain names to assess"],
    "ambiguity_state": "unambiguous",
    "clarification_required": False,
    "confidence": 0.95,
}


def _contract(**overrides) -> ResolvedQueryContract:
    payload = {
        "normalized_goal": "deterministic goal",
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "ambiguity_state": "unambiguous",
        "qualification_tier": "T4",
        "qualification_source": "deterministic_qualification",
    }
    payload.update(overrides)
    return ResolvedQueryContract(**payload)


def _enriched(monkeypatch, payload: dict, query: str = "any domain lookups that look algorithmically generated"):
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    return maybe_enrich_t4_semantic(
        _contract(), query=query, raw_output_provider=lambda _q, _c: json.dumps(payload)
    )


def test_field_sources_survive_a_second_redaction(monkeypatch) -> None:
    """THE regression: redacting the redacted output must not empty the measurement."""
    enriched = _enriched(monkeypatch, RESOLVED_ANSWER)

    once = redact_resolved_query(enriched.model_dump())
    assert once["field_sources"], "first redaction lost provenance.field_sources"
    assert "normalized_goal" in once["semantic_t4_fields"]

    twice = redact_resolved_query(once)
    assert twice["field_sources"] == once["field_sources"]
    assert twice["semantic_t4_fields"] == once["semantic_t4_fields"]


def test_proposed_and_accepted_fields_are_both_reported(monkeypatch) -> None:
    """"The model answered" and "we kept it" are different facts."""
    enriched = _enriched(monkeypatch, RESOLVED_ANSWER)
    block = redact_resolved_query(enriched.model_dump())["semantic_t4"]

    assert "normalized_goal" in block["proposed_fields"]
    assert "evidence_requirements" in block["proposed_fields"]
    assert "normalized_goal" in block["accepted_fields"]


def test_rejected_contribution_is_visible_as_proposed_but_not_accepted(monkeypatch) -> None:
    """A refused field must be observable, or a measurement cannot see the refusal."""
    enriched = _enriched(
        monkeypatch, {**RESOLVED_ANSWER, "time_scope": "last 24 hours"}
    )
    block = redact_resolved_query(enriched.model_dump())["semantic_t4"]

    assert "time_scope" in block["proposed_fields"]
    assert "time_scope" not in block["accepted_fields"]
    assert "time_scope_not_grounded_in_query" in block["rejected_reasons"]


def test_a_fully_rejected_hop_reports_no_accepted_fields(monkeypatch) -> None:
    enriched = _enriched(monkeypatch, {"output": {**RESOLVED_ANSWER, "skill": "spl_generation"}})
    block = redact_resolved_query(enriched.model_dump())["semantic_t4"]

    assert block["accepted"] is False
    assert block["accepted_fields"] == []
    assert "authority_key_present" in block["rejected_reasons"]


def test_diagnostics_carry_names_only_never_values(monkeypatch) -> None:
    """The seam is observational; it must not become a content channel."""
    secret_goal = "identify DNS lookups involving domains that appear algorithmically generated"
    enriched = _enriched(monkeypatch, RESOLVED_ANSWER)
    block = redact_resolved_query(enriched.model_dump())["semantic_t4"]

    serialized = json.dumps(block)
    assert secret_goal not in serialized
    assert all(isinstance(name, str) for name in block["proposed_fields"])


def test_instrumentation_does_not_change_acceptance(monkeypatch) -> None:
    """Adding observation must not move the accept/reject boundary."""
    base = _contract()
    accepted = _enriched(monkeypatch, RESOLVED_ANSWER)

    assert accepted.provenance["semantic_t4"]["accepted"] is True
    # Semantic completion changed meaning fields only. Route-bearing state is
    # identical to the deterministic contract it started from.
    assert accepted.intent_family == base.intent_family
    assert accepted.answer_goal == base.answer_goal
    assert accepted.clarification_required == base.clarification_required

    # Capabilities are derived deterministically from the locked intent family,
    # never granted by the model: the merge applies `capabilities_for_intent_family`
    # and the provenance must not attribute them to `semantic_t4`.
    family_required, family_prohibited = capabilities_for_intent_family(base.intent_family)
    assert accepted.required_capabilities == frozenset(family_required)
    assert accepted.prohibited_capabilities == frozenset(family_prohibited)
    field_sources = accepted.provenance["field_sources"]
    assert field_sources.get("required_capabilities") != "semantic_t4"
    assert field_sources.get("prohibited_capabilities") != "semantic_t4"
