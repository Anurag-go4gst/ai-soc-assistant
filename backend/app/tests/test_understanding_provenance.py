"""P4 — deterministic understanding authority provenance."""

from __future__ import annotations

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.control_plane_trace import build_control_plane_trace
from app.chat.resolved_query_builder import attach_understanding_authority
from app.chat.understanding_provenance import build_understanding_provenance


def _accepted_catalogue_spl() -> ResolvedQueryContract:
    return ResolvedQueryContract(
        normalized_goal="generate spl for failed logins",
        intent_family="spl_generation_only",
        answer_goal="spl_artifact",
        ambiguity_state="unambiguous",
        qualification_tier="T2",
        qualification_source="use_case_catalog",
        confidence=0.92,
        understanding_source="deterministic_qualification",
        provenance={"deterministic_match_path": "use_case_catalog", "match_path": "use_case_catalog"},
    )


def _abstained_t4_spl() -> ResolvedQueryContract:
    """Post-T4 Final RQC: gate abstained, T4 merged SPL authoring semantics."""
    return ResolvedQueryContract(
        normalized_goal="firewall activities spl",
        intent_family="spl_generation_only",
        answer_goal="spl_artifact",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="out_of_registry",
        confidence=0.82,
        understanding_source="semantic_t4",
        required_capabilities=frozenset({"spl"}),
        provenance={
            "deterministic_match_path": "out_of_registry",
            "match_path": "out_of_registry",
            "semantic_t4": {
                "invoked": True,
                "accepted": True,
                "elapsed_ms": 840,
            },
        },
    )


def test_accept_path_shows_t4_skipped_and_final_owner() -> None:
    contract = _accepted_catalogue_spl()
    payload = build_understanding_provenance(
        resolved_query_contract=contract,
        route_adjudication={"selected_skill": "spl_generation"},
    )
    assert payload is not None
    assert payload["acceptance_decision"] == "ACCEPT"
    assert payload["t4_skipped"] is True
    assert payload["t4_invoked"] is False
    labels = [line["label"] for line in payload["lines"]]
    values = {line["label"]: line["value"] for line in payload["lines"]}
    assert labels[:2] == ["T1–T3", "T4"]
    assert values["T1–T3"] == "accepted"
    assert values["T4"] == "skipped"
    assert values["Final intent"] == "SPL authoring"
    assert values["Final owner"] == "spl_generation"


def test_abstain_t4_path_shows_full_ladder() -> None:
    contract = _abstained_t4_spl()
    payload = build_understanding_provenance(
        resolved_query_contract=contract,
        routed={"selected_skill": "spl_generation"},
    )
    assert payload is not None
    assert payload["acceptance_decision"] == "ABSTAIN"
    assert payload["t4_skipped"] is False
    assert payload["t4_invoked"] is True
    assert payload["t4_accepted"] is True
    values = {line["label"]: line["value"] for line in payload["lines"]}
    assert values["T1 exact"] == "no match"
    assert values["T2 catalogue"] == "no accepted match"
    assert values["T3 candidates"] == "abstained"
    assert values["T4 semantic"] == "used"
    assert values["Final intent"] == "SPL authoring"
    assert values["Final owner"] == "spl_generation"


def test_control_plane_trace_includes_understanding_provenance() -> None:
    contract = _accepted_catalogue_spl()
    trace = build_control_plane_trace(
        {
            "resolved_query_contract": contract.model_dump(mode="json"),
            "route_adjudication": {"selected_skill": "spl_generation"},
            "routed": {"selected_skill": "spl_generation"},
        }
    )
    block = trace.get("understanding_provenance")
    assert isinstance(block, dict)
    assert block.get("acceptance_decision") == "ACCEPT"
    assert block.get("lines")


def test_provenance_has_no_chain_of_thought_fields() -> None:
    contract = _abstained_t4_spl()
    payload = build_understanding_provenance(resolved_query_contract=contract)
    assert payload is not None
    serialized = str(payload).lower()
    for forbidden in ("prompt", "reasoning", "chain_of_thought", "raw_output", "model_thought"):
        assert forbidden not in serialized


def test_t4_unavailable_shows_unavailable_not_used() -> None:
    contract = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="ambiguous referent",
            intent_family="live_investigation",
            answer_goal="live_results",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="which host",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.3,
            provenance={
                "deterministic_match_path": "out_of_registry",
                "semantic_t4": {
                    "invoked": True,
                    "accepted": False,
                    "timed_out": True,
                    "rejected_reasons": ["timed_out"],
                },
            },
        )
    )
    payload = build_understanding_provenance(resolved_query_contract=contract)
    assert payload is not None
    values = {line["label"]: line["value"] for line in payload["lines"]}
    assert values["T4 semantic"] == "unavailable"
