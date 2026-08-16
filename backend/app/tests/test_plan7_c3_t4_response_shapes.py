"""Plan 7 C3 — the T4 seam must hold across the response shapes a model actually returns.

The prompt and the model are replaceable; the downstream contract is not. Every case
here is driven through the injected-provider seam, so it runs with **no LLM**, and it
pins behaviour that must survive a prompt rewrite or a model swap.

Two separate concerns, deliberately not conflated:

* **Shape tolerance** (adapter): a wrapped, echoed or chatty payload is normalized
  rather than thrown away. Losing a valid semantic completion to a stray key is a
  defect, not safety.
* **Authority** (governance): what the model is allowed to change is decided here,
  never by how convincingly it phrased the answer.

The three-uncertainty rule from the C3 review is the load-bearing invariant:

    semantic uncertainty     → may ask the analyst
    evidence uncertainty     → continue investigating
    investigation uncertainty→ preserve hypotheses
"""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.config import settings

HUNT_QUERY = "any domain lookups that look algorithmically generated"
REFERENT_QUERY = "compare this with what happened last week and tell me if it is getting worse"

RESOLVED_ANSWER = {
    "normalized_goal": "identify DNS lookups involving domains that appear algorithmically generated",
    "evidence_requirements": ["DNS lookup events containing domain names to assess"],
    "ambiguity_state": "unambiguous",
    "clarification_required": False,
    "confidence": 0.95,
}


@pytest.fixture(autouse=True)
def _t4_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)


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


def _raw(payload: object):
    return lambda _query, _contract: json.dumps(payload)


def _trace(contract: ResolvedQueryContract) -> dict:
    return contract.provenance["semantic_t4"]


# --- shape tolerance ----------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("flat", RESOLVED_ANSWER),
        ("wrapped_in_output", {"output": RESOLVED_ANSWER}),
        (
            "echoed_envelope_plus_output",
            {
                "query": HUNT_QUERY,
                "locked_fields_do_not_change": {"intent_family": "live_investigation"},
                "vocabulary": {"capabilities": ["mcp", "spl"]},
                "output": RESOLVED_ANSWER,
            },
        ),
        ("chatty_extra_key", {**RESOLVED_ANSWER, "notes": "here is my reasoning"}),
    ],
)
def test_tolerated_shapes_all_yield_the_same_accepted_completion(label, payload) -> None:
    """Four shapes observed from a real 8B, one governed outcome."""
    enriched = maybe_enrich_t4_semantic(
        _contract(), query=HUNT_QUERY, raw_output_provider=_raw(payload)
    )

    trace = _trace(enriched)
    assert trace["accepted"] is True, f"{label} was rejected: {trace['rejected_reasons']}"
    assert enriched.normalized_goal == RESOLVED_ANSWER["normalized_goal"]
    assert "DNS lookup events containing domain names to assess" in enriched.evidence_requirements
    assert enriched.clarification_required is False


def test_markdown_fenced_json_is_still_read() -> None:
    fenced = "```json\n" + json.dumps(RESOLVED_ANSWER) + "\n```"
    enriched = maybe_enrich_t4_semantic(
        _contract(), query=HUNT_QUERY, raw_output_provider=lambda _q, _c: fenced
    )

    assert _trace(enriched)["accepted"] is True


def test_prose_without_json_is_rejected_not_guessed_at() -> None:
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=HUNT_QUERY,
        raw_output_provider=lambda _q, _c: "To answer this you would look at DNS logs.",
    )

    trace = _trace(enriched)
    assert trace["accepted"] is False
    assert enriched.normalized_goal == "deterministic goal"


# --- authority ----------------------------------------------------------------


@pytest.mark.parametrize(
    "authority_key",
    ["skill", "route", "normalized_spl", "mcp_tool", "execution_eligible", "hil"],
)
def test_authority_keys_fail_the_hop_even_inside_a_wrapper(authority_key) -> None:
    """Shape tolerance must not become an authority loophole."""
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=HUNT_QUERY,
        raw_output_provider=_raw({"output": {**RESOLVED_ANSWER, authority_key: "anything"}}),
    )

    trace = _trace(enriched)
    assert trace["accepted"] is False
    assert "authority_key_present" in trace["rejected_reasons"]
    assert enriched.normalized_goal == "deterministic goal"


# --- the three kinds of uncertainty ------------------------------------------


def test_evidence_uncertainty_may_not_become_an_analyst_question() -> None:
    """A clear hunt with missing *evidence* must not be turned into clarification.

    This is the measured C3 failure: the model asked the analyst to define
    "algorithmically generated". Missing detection criteria is investigation input,
    not missing meaning.
    """
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=HUNT_QUERY,
        raw_output_provider=_raw(
            {
                "normalized_goal": "identify algorithmically generated domain lookups",
                "clarification_required": True,
                "clarification_reason": "define what counts as algorithmically generated",
                "semantic_ambiguity": "unambiguous",
            }
        ),
    )

    assert enriched.clarification_required is False
    assert enriched.ambiguity_state == "unambiguous"
    assert "clarification_without_unresolved_referent" in _trace(enriched)["rejected_reasons"]


def test_semantic_uncertainty_may_still_ask() -> None:
    """An unresolved referent is exactly the case clarification exists for."""
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=REFERENT_QUERY,
        raw_output_provider=_raw(
            {
                "normalized_goal": "compare an unnamed current event with last week",
                "clarification_required": True,
                "clarification_reason": "the activity referred to by 'this' is not identified",
                "semantic_ambiguity": "clarification_required",
            }
        ),
    )

    assert enriched.clarification_required is True
    assert "clarification_without_unresolved_referent" not in _trace(enriched)["rejected_reasons"]


# --- field semantics ----------------------------------------------------------


def test_category_strings_are_not_recorded_as_entities() -> None:
    """"suspicious DNS" is an investigation topic; recording it invents an observation."""
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=HUNT_QUERY,
        raw_output_provider=_raw(
            {**RESOLVED_ANSWER, "entities": {"observed": "algorithmically generated domains"}}
        ),
    )

    assert enriched.entities.get("observed") is None
    assert "entity_not_concrete" in _trace(enriched)["rejected_reasons"]


def test_concrete_entities_are_kept() -> None:
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query="check 10.20.4.15 for suspicious outbound dns",
        raw_output_provider=_raw({**RESOLVED_ANSWER, "entities": {"host_ip": "10.20.4.15"}}),
    )

    assert enriched.entities.get("host_ip") == "10.20.4.15"


def test_invented_time_scope_is_refused() -> None:
    """No silent "last 24 hours" — the analyst never scoped it."""
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query=HUNT_QUERY,
        raw_output_provider=_raw({**RESOLVED_ANSWER, "time_scope": "last 24 hours"}),
    )

    assert enriched.time_scope in (None, "")
    assert "time_scope_not_grounded_in_query" in _trace(enriched)["rejected_reasons"]


def test_time_scope_stated_by_the_analyst_is_kept() -> None:
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query="show failed admin logins in the last 2 hours",
        raw_output_provider=_raw({**RESOLVED_ANSWER, "time_scope": "last 2 hours"}),
    )

    assert enriched.time_scope == "last 2 hours"


# --- locked fields ------------------------------------------------------------


def test_locked_deterministic_fields_survive_a_contradicting_proposal() -> None:
    """The stage completes meaning; it does not repair upstream classification."""
    deterministic = _contract(intent_family="knowledge_recall", answer_goal="policy_citation")
    enriched = maybe_enrich_t4_semantic(
        deterministic,
        query=HUNT_QUERY,
        raw_output_provider=_raw(
            {**RESOLVED_ANSWER, "intent_family": "spl_generation_and_run", "answer_goal": "live_results"}
        ),
    )

    assert enriched.intent_family == "knowledge_recall"
    assert enriched.answer_goal == "policy_citation"


def test_deterministic_clarification_is_never_cleared_by_the_model() -> None:
    deterministic = _contract(
        ambiguity_state="policy_blocked",
        answer_goal="clarification",
        clarification_required=True,
        clarification_reason="unsafe_run_spl",
    )
    enriched = maybe_enrich_t4_semantic(
        deterministic,
        query=REFERENT_QUERY,
        raw_output_provider=_raw({**RESOLVED_ANSWER, "clarification_required": False}),
    )

    assert enriched.clarification_required is True
