"""P2 — ABSTAIN → T4 → DET validation → one Final RQC.

Frozen architecture.md 2.2 / 11 / 12. Covers ACCEPT/ABSTAIN authority, explicit
literal protection classes, T4-failure negatives, and production constraint
carriage. No user sentence is special-cased.
"""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.explicit_user_constraints import (
    ExplicitUserConstraints,
    build_explicit_user_constraints,
    time_signature,
)
from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.contracts.semantic_t4_proposal import SemanticT4Proposal
from app.chat.resolved_query_builder import attach_understanding_authority, build_resolved_query_contract
from app.chat.semantic_t4_understanding import (
    _permits_t4_call,
    abstain_acceptance,
    explicit_constraints_for,
    maybe_enrich_t4_semantic,
)
from app.config import settings
from app.query_understanding.parser import understand_query

_REQUIRED = dict(
    normalized_goal="deterministic goal",
    intent_family="live_investigation",
    answer_goal="live_results",
    ambiguity_state="unambiguous",
    qualification_source="deterministic",
)


def _abstained(**overrides) -> ResolvedQueryContract:
    """True ABSTAIN: deferred semantic referent gap (not invented semantic_goal)."""
    payload = dict(
        _REQUIRED,
        qualification_tier="T4",
        clarification_required=True,
        clarification_reason="which event this refers to",
        ambiguity_state="clarification_required",
        confidence=0.2,
        provenance={
            "match_path": "out_of_registry",
            "deterministic_match_path": "out_of_registry",
        },
    )
    payload.update(overrides)
    return attach_understanding_authority(ResolvedQueryContract(**payload))


def _accepted_catalogue() -> ResolvedQueryContract:
    return ResolvedQueryContract(
        **_REQUIRED,
        qualification_tier="T1",
        unresolved_fields=[],
        understanding_sufficiency={"missing": []},
        provenance={"deterministic_match_path": "exact_105_question", "match_path": "exact_105_question"},
        confidence=0.95,
    )


# --- ACCEPT / ABSTAIN authority -------------------------------------------------


def test_1_complete_t1_accept_does_not_invoke_t4() -> None:
    contract = _accepted_catalogue()
    assert abstain_acceptance(contract).decision == "ACCEPT"
    assert _permits_t4_call(contract) is False


def test_2_abstain_invokes_t4() -> None:
    contract = _abstained()
    acceptance = abstain_acceptance(contract)
    assert acceptance.decision == "ABSTAIN"
    assert "semantic_referent" in (contract.unresolved_fields or [])
    assert _permits_t4_call(contract) is True


def test_3_abstain_commits_no_partial_semantic_authority() -> None:
    acceptance = abstain_acceptance(_abstained())
    assert acceptance.accepted_candidate_id is None
    assert acceptance.t4_permitted is True


def test_complete_deterministic_spl_authoring_accepts_without_t4() -> None:
    """Governed complete SPL/utility shape: ACCEPT → T4 skipped even on T4 tier."""
    query = (
        "Without using any specific company templates, write a standard, universal SPL "
        "block that extracts the hour of the day and day of the week from an event "
        "timestamp, filtering only for weekend events."
    )
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    assert contract.unresolved_fields == []
    assert abstain_acceptance(contract).decision == "ACCEPT"
    assert abstain_acceptance(contract).reason_codes == ("complete_deterministic_understanding",)
    assert _permits_t4_call(contract) is False


def test_complete_request_still_works_when_t4_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ACCEPT path must not depend on T4; unavailable provider must not poison it."""
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    query = (
        "Run a Splunk search on the wineventlog index for Event ID 4624 "
        "(Successful Logon) originating from substation subnets outside normal shift hours."
    )
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    assert abstain_acceptance(contract).decision == "ACCEPT"
    calls: list[int] = []

    def _boom(_q: str, _c: ResolvedQueryContract) -> str:
        calls.append(1)
        raise RuntimeError("provider down")

    out = maybe_enrich_t4_semantic(contract, query=query, raw_output_provider=_boom)
    assert calls == []
    assert out.clarification_required is False
    assert out.intent_family == contract.intent_family


def test_genuine_abstain_t4_unavailable_fails_closed_no_partial_resurrection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract = _abstained()
    out = maybe_enrich_t4_semantic(
        contract,
        query="compare this with last week",
        raw_output_provider=lambda _q, _c: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert out.clarification_required is True
    assert out.understanding_source == "deterministic_qualification"
    assert out.provenance["semantic_t4"]["semantic_authority"] == "none"


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        (
            {
                "ambiguity_state": "policy_blocked",
                "clarification_required": True,
                "clarification_reason": "blocked_by_policy",
                "intent_family": "clarification_required",
                "answer_goal": "clarification",
            },
            "a policy block is not a semantic question",
        ),
    ],
)
def test_abstain_that_already_resolves_does_not_call_t4(overrides: dict, why: str) -> None:
    assert _permits_t4_call(_abstained(**overrides)) is False, why


# --- Literal protection matrix -------------------------------------------------

# field → DET_REJECTION | PROTECTED_BY_CONSTRUCTION
LITERAL_PROTECTION_MATRIX = {
    "entity/IP/domain/hash": "DET_REJECTION",  # SemanticT4Proposal.entities
    "time": "DET_REJECTION",  # SemanticT4Proposal.time_scope
    "index": "PROTECTED_BY_CONSTRUCTION",  # not on proposal schema
    "sourcetype": "PROTECTED_BY_CONSTRUCTION",
    "requested_output_form": "PROTECTED_BY_CONSTRUCTION",
    "do_not_execute / execution intent": "PROTECTED_BY_CONSTRUCTION",
    "explicit prohibitions": "PROTECTED_BY_CONSTRUCTION",
}


def test_literal_protection_matrix_matches_live_proposal_schema() -> None:
    proposal_fields = set(SemanticT4Proposal.model_fields)
    assert "entities" in proposal_fields and "time_scope" in proposal_fields
    for absent in ("execute", "execution_intent", "requested_output_type", "index", "sourcetype"):
        assert absent not in proposal_fields
    assert LITERAL_PROTECTION_MATRIX["entity/IP/domain/hash"] == "DET_REJECTION"
    assert LITERAL_PROTECTION_MATRIX["time"] == "DET_REJECTION"
    assert LITERAL_PROTECTION_MATRIX["do_not_execute / execution intent"] == (
        "PROTECTED_BY_CONSTRUCTION"
    )


def _constraints() -> ExplicitUserConstraints:
    return ExplicitUserConstraints(
        entities={"src_ip": ("10.0.0.8",)},
        time_window="earliest=-2h latest=now",
        execution_prohibited=True,
        prohibitions=("do_not_execute",),
        data_scope={"index": ("firewall",)},
    )


def test_4_explicit_literals_survive_and_agreeing_proposal_is_accepted() -> None:
    assert _constraints().material_contradictions(
        {"entities": {"src_ip": ["10.0.0.8"]}, "time_scope": "last 2 hours"}
    ) == ()


@pytest.mark.parametrize(
    ("proposal", "expected"),
    [
        ({"entities": {"src_ip": ["10.0.0.5"]}}, "entity_contradiction:src_ip"),
        ({"time_scope": "last 24 hours"}, "time_window_contradiction"),
    ],
)
def test_5_material_literal_contradiction_is_rejected_when_proposal_can_express_it(
    proposal: dict, expected: str
) -> None:
    """Entity/time are DET_REJECTION — proposal can express them and DET rejects."""
    assert expected in _constraints().material_contradictions(proposal)


def test_execution_prohibition_protected_by_construction_not_proposal_field() -> None:
    """do_not_execute is not a SemanticT4Proposal field — cannot be overridden by T4."""
    assert "execute" not in SemanticT4Proposal.model_fields
    assert "execution_intent" not in SemanticT4Proposal.model_fields
    # Core still detects a contradictory *view* if one were injected at DET.
    assert "execution_prohibition_contradiction" in _constraints().material_contradictions(
        {"execute": True}
    )


def test_do_not_execute_survives_abstain_t4_path_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    query = (
        "create a review-only SPL for 10.0.0.8 in index=firewall for the last 2 hours; "
        "do not execute it"
    )
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    carried = (contract.provenance or {}).get("explicit_user_constraints") or {}
    assert carried.get("execution_prohibited") is True
    # Force ABSTAIN via deferred referent so T4 runs, then propose meaning that
    # cannot carry execution authority.
    abstained = contract.model_copy(
        update={
            "clarification_required": True,
            "clarification_reason": "which host",
            "ambiguity_state": "clarification_required",
            "unresolved_fields": ["semantic_referent"],
            "provenance": {
                **(contract.provenance or {}),
                "t4_owns_unresolved_semantic_referent": True,
            },
        }
    )
    abstained = attach_understanding_authority(
        ResolvedQueryContract(**{**abstained.model_dump(), "clarification_required": True})
    )
    # Re-attach may clear clarification when deferred — ensure referent gap remains.
    if "semantic_referent" not in (abstained.unresolved_fields or []):
        abstained = abstained.model_copy(
            update={
                "unresolved_fields": list(abstained.unresolved_fields or []) + ["semantic_referent"],
                "provenance": {
                    **(abstained.provenance or {}),
                    "t4_owns_unresolved_semantic_referent": True,
                    "explicit_user_constraints": carried,
                },
            }
        )
    else:
        abstained = abstained.model_copy(
            update={
                "provenance": {
                    **(abstained.provenance or {}),
                    "explicit_user_constraints": carried,
                }
            }
        )

    out = maybe_enrich_t4_semantic(
        abstained,
        query=query,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "review-only firewall SPL for 10.0.0.8",
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
                "entities": {"src_ip": ["10.0.0.8"]},
                "time_scope": "last 2 hours",
            }
        ),
    )
    # No proposal field can grant execution; constraints remain binding.
    constraints = explicit_constraints_for(out, query=query)
    assert constraints.execution_prohibited is True
    assert "do_not_execute" in constraints.prohibitions


def test_6_omission_is_not_contradiction_and_hints_are_not_binding() -> None:
    assert _constraints().material_contradictions({}) == ()
    assert _constraints().material_contradictions({"entities": {}}) == ()
    assert ExplicitUserConstraints().material_contradictions(
        {"entities": {"host": ["anything"]}, "time_scope": "last 90 days"}
    ) == ()


def test_time_signature_is_notation_agnostic_but_catches_real_differences() -> None:
    assert time_signature("last 2 hours") == time_signature("earliest=-2h latest=now") == ("h", 2)
    assert time_signature("last 24 hours") != time_signature("last 2 hours")
    assert time_signature("now") is None
    assert time_signature(None) is None


# --- Authority: T4 grants nothing ----------------------------------------------


def test_7_proposal_capabilities_are_not_authority() -> None:
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module._merge_proposal)
    assert 'field_sources["required_capabilities"] = "deterministic_qualification"' in source
    assert 'field_sources["required_capabilities"] = "semantic_t4"' not in source
    assert 'field_sources["prohibited_capabilities"] = "semantic_t4"' not in source


def test_8_proposal_intent_family_is_validated_not_adopted_verbatim() -> None:
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module._merge_proposal)
    assert "intent_family = deterministic.intent_family" in source
    assert 'rejected.append("locked_field_change_rejected:intent_family")' in source
    assert "capabilities_for_intent_family(intent_family)" in source
    body = source.split("field_sources = {", 1)[0]
    assert "material_contradictions" in body


def test_9_t4_cannot_grant_route_plan_mcp_or_hil_authority() -> None:
    from app.chat.semantic_t4_understanding import _SEMANTIC_T4_SYSTEM_PROMPT

    assert "Do not grant route, capability, SPL, MCP, RBAC, HIL" in _SEMANTIC_T4_SYSTEM_PROMPT


# --- T4 failure negatives ------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("unavailable", "provider_unavailable"),
        ("timeout", "timed_out"),
        ("invalid", "schema_invalid"),
    ],
)
def test_10_11_12_t4_failure_fails_closed(failure: str, reason: str) -> None:
    from app.chat.semantic_t4_understanding import _fail_closed_semantic_authority

    contract = _abstained()
    out = _fail_closed_semantic_authority(
        contract, {"rejected_reasons": [reason]}, clarification_reason=f"t4_{failure}"
    )
    assert out.clarification_required is True
    assert out.ambiguity_state == "clarification_required"
    assert out.understanding_source == "deterministic_qualification"
    trace = out.provenance["semantic_t4"]
    assert trace["accepted"] is False
    assert trace["degradation"] is True
    assert trace["semantic_authority"] == "none"


def test_every_t4_failure_path_routes_to_fail_closed() -> None:
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module.maybe_enrich_t4_semantic)
    assert "_with_semantic_trace(prepared, failed_trace)" not in source
    assert source.count("_fail_closed_semantic_authority") >= 2


def test_permits_t4_not_governed_by_unresolved_fields_alone() -> None:
    """Regression: bool(unresolved_fields) must not be the live T4 authority."""
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module._permits_t4_call)
    assert "bool(deterministic.unresolved_fields)" not in source
    assert "abstain_acceptance" in source


def test_live_provider_does_not_restrict_schema_to_unresolved_fields() -> None:
    import inspect

    from app.chat import semantic_t4_understanding as module

    source = inspect.getsource(module._live_single_hop_provider)
    assert "_schema_limited_to_unresolved" not in source


# --- Production constraint carriage + SPL composition --------------------------


def test_13_spl_contract_composes_the_generic_core_without_losing_spl_fields() -> None:
    from app.spl.request_authority import build_deterministic_request_contract
    from app.spl.user_constraint_bindings import build_user_constraint_bindings
    from app.chat.query_signals import extract_query_signals

    query = (
        "create a review-only SPL for 10.0.0.8 in index=firewall sourcetype=cisco:asa "
        "for the last 2 hours; do not execute it"
    )
    signals = extract_query_signals(query, None)
    bindings = build_user_constraint_bindings(query, query_understanding=None)
    contract = build_deterministic_request_contract(
        query_understanding=None, query_signals=signals, bindings=bindings
    )
    assert hasattr(contract, "sufficient_for_spl_authoring")
    assert hasattr(contract, "response_shape")
    assert contract.explicit_constraints is not None
    assert "sufficient_for_spl_authoring" not in contract.explicit_constraints.to_dict()


def test_14_generic_core_carries_only_literals() -> None:
    core = build_explicit_user_constraints(
        query_understanding=None, query_signals={}, bindings=None
    )
    keys = set(core.to_dict())
    assert keys == {
        "entities",
        "predicates",
        "data_scope",
        "time_window",
        "requested_output_type",
        "execution_prohibited",
        "prohibitions",
    }
    assert not keys & {
        "sufficient_for_spl_authoring",
        "response_shape",
        "intent_family",
        "source_family",
    }


def test_explicit_constraints_populated_in_production_provenance() -> None:
    query = "review-only SPL for 10.0.0.8 last 2 hours; do not execute"
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understand_query(query),
        qualification_tier="T4",
        qualification_source="out_of_registry",
    )
    carried = (contract.provenance or {}).get("explicit_user_constraints")
    assert isinstance(carried, dict)
    assert (contract.provenance or {}).get("explicit_constraint_authority_path")
    # Same object used by T4/DET without re-derivation preference.
    assert explicit_constraints_for(contract).entities.get("src_ip") == ("10.0.0.8",) or (
        explicit_constraints_for(contract).execution_prohibited
        or explicit_constraints_for(contract).time_window
    )
