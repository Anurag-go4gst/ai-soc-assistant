"""Run-shape matrix: final goal + governed scope, not catalogue membership."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.contracts.intent_classification import IntentClassification
from app.chat.evidence_planner import plan_evidence
from app.chat.query_signals import extract_query_signals
from app.chat.spl_authoring_intent import is_explicit_review_only_spl_authoring


def _intent(family: str, goal: str, query_type: str = "ask_for_query_generation") -> IntentClassification:
    return IntentClassification(
        intent_family=family,
        primary_intent=query_type,
        query_type=query_type,  # type: ignore[arg-type]
        answer_goal=[goal],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        reason="run_shape_matrix",
    )


def test_a_catalogued_review_only_spl_is_utility() -> None:
    """Catalogue membership must not force investigation for review-only SPL artifact."""
    query = (
        "Give me only a review-only SPL query for index=pgcil_soc and "
        "sourcetype=cisco:firepower for the last 30 days. Do not execute it."
    )
    signals = extract_query_signals(query)
    assert is_explicit_review_only_spl_authoring(signals)
    assert signals.get("run_execution") is False
    assert signals.get("explicit_spl_authoring") is True
    plan = plan_evidence(
        _intent("spl_generation_only", "spl_artifact"),
        {"query_signals": signals},
        routed={"skill": "spl_generation"},
        query_understanding=SimpleNamespace(
            deterministic_match_path="exact_105_question",
            raw_query=query,
            soc_investigation_shaped=False,
        ),
    )
    assert plan.answer_mode == "spl_utility_authoring"
    assert plan.mcp_allowed is False


def test_b_out_of_registry_review_only_spl_is_utility() -> None:
    query = "give me a spl command to get all the firewall logs for last 30 days"
    signals = extract_query_signals(query)
    assert is_explicit_review_only_spl_authoring(signals)
    plan = plan_evidence(
        _intent("spl_generation_only", "spl_artifact"),
        {"query_signals": signals},
        routed={"skill": "spl_generation"},
        query_understanding=SimpleNamespace(
            deterministic_match_path="out_of_registry",
            raw_query=query,
            soc_investigation_shaped=False,
        ),
    )
    assert plan.answer_mode == "spl_utility_authoring"


def test_c_investigation_using_catalogued_spl_remains_investigation() -> None:
    query = "Investigate firewall deny spike"
    signals = extract_query_signals(query)
    assert not is_explicit_review_only_spl_authoring(signals)
    assert signals.get("block_or_contain") is False
    plan = plan_evidence(
        _intent("live_investigation", "live_results", query_type="ask_for_live_results"),
        {"query_signals": signals},
        routed={"skill": "attack_discovery"},
        query_understanding=SimpleNamespace(
            deterministic_match_path="exact_105_question",
            raw_query=query,
            soc_investigation_shaped=True,
        ),
    )
    assert plan.answer_mode == "live_investigation"
    assert plan.needs_spl is True


def test_firewall_deny_spike_is_not_containment_enforcement() -> None:
    signals = extract_query_signals("Investigate firewall deny spike")
    assert signals.get("block_or_contain") is False
    assert signals.get("firewall_block_or_deny") is True
    enforce = extract_query_signals("add a firewall rule to drop that traffic")
    assert enforce.get("block_or_contain") is True


def test_d_mixed_spl_plus_conclusion_stays_investigation_shaped() -> None:
    query = (
        "Generate SPL for firewall denies from 10.20.30.40 and tell me whether "
        "the host is compromised"
    )
    signals = extract_query_signals(query)
    plan = plan_evidence(
        _intent(
            "hybrid_investigation_plus_policy",
            "live_results",
            query_type="investigation_with_guidance",
        ),
        {"query_signals": signals},
        routed={"skill": "guided_investigation"},
        query_understanding=SimpleNamespace(
            deterministic_match_path="out_of_registry",
            raw_query=query,
            soc_investigation_shaped=True,
        ),
    )
    assert plan.answer_mode in {"hybrid", "live_investigation", "guided_investigation"}
    assert plan.answer_mode != "spl_utility_authoring"


def test_do_not_execute_does_not_set_run_execution() -> None:
    query = "Give me SPL for index=pgcil_soc. Do not execute it."
    signals = extract_query_signals(query)
    assert signals.get("run_execution") is False
    assert signals.get("explicit_run_spl") is False
    assert signals.get("explicit_spl_authoring") is True
