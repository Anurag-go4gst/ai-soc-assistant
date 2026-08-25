"""Trace invariants for factual SPL + LLM provenance (Defect B)."""

from __future__ import annotations

from app.chat.pipeline_visibility import _spl_node_llm_call
from app.quality.store import _llm_used
from app.spl.spl_provenance_trace import (
    build_spl_provenance_summary,
    is_deterministic_spl_provider,
    llm_candidate_generated,
    llm_failover_used_factual,
    llm_used_factual,
    spl_artifact_source,
)


def _assert_invariants(candidate: dict, *, budget_records: list[dict] | None = None) -> None:
    summary = build_spl_provenance_summary(candidate, candidate, budget_records)
    source = summary["spl_artifact_source"]
    live_calls = summary["llm_live_calls"]

    if live_calls == 0:
        assert summary["llm_attempted"] is False or not summary["llm_succeeded"]
        assert _llm_used({"candidate_spl": candidate, "spl_validation": candidate}) is (
            llm_used_factual(candidate_spl=candidate, spl_validation=candidate, budget_records=budget_records)
        )

    if summary["llm_used"]:
        assert live_calls >= 1 or bool((candidate.get("utility_spl_draft_trace") or {}).get("llm_spl_draft_used"))

    provider = str(candidate.get("selected_candidate_spl_provider") or "")
    assert not is_deterministic_spl_provider(provider) or _spl_node_llm_call(candidate) is None

    if source == "live_llm":
        assert llm_candidate_generated(candidate)
        assert summary["llm_candidate_generated"] is True

    if source == "deterministic_fallback":
        assert llm_candidate_generated(candidate) is False

    llm_call = _spl_node_llm_call(candidate)
    if llm_call is not None:
        assert str(llm_call.get("provider") or "") not in {"deterministic_lab_draft", "deterministic_skeleton"}

    if summary["llm_failover_used"]:
        assert summary["llm_attempted"] or llm_candidate_generated(candidate)


def test_invariant_a_zero_live_calls_not_llm_used() -> None:
    candidate = {
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "generation_mode": "deterministic_lab_draft",
        "llm_fallback_used": True,
        "utility_spl_draft_trace": {"llm_spl_draft_requested": False, "llm_spl_draft_used": False},
    }
    assert llm_used_factual(candidate_spl=candidate, spl_validation=candidate, budget_records=[]) is False
    assert _spl_node_llm_call(candidate) is None
    assert _llm_used({"candidate_spl": candidate, "spl_validation": candidate}) is False
    _assert_invariants(candidate, budget_records=[])


def test_invariant_b_llm_used_requires_endpoint_attempt() -> None:
    candidate = {
        "selected_candidate_spl_provider": "utility_llm_spl_draft",
        "generation_mode": "utility_llm_spl_draft",
        "llm_fallback_used": True,
        "utility_spl_draft_trace": {"llm_spl_draft_used": True, "llm_spl_draft_requested": True},
    }
    records = [{"role": "spl_advisory_generator", "outcome": "completed"}]
    assert llm_used_factual(candidate_spl=candidate, spl_validation=candidate, budget_records=records) is True
    assert _spl_node_llm_call(candidate) is not None
    _assert_invariants(candidate, budget_records=records)


def test_invariant_c_no_deterministic_provider_in_llm_call() -> None:
    candidate = {
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "generation_mode": "deterministic_lab_draft",
        "llm_fallback_used": True,
    }
    assert _spl_node_llm_call(candidate) is None


def test_invariant_d_live_llm_source_requires_candidate_generated() -> None:
    candidate = {
        "selected_candidate_spl_provider": "utility_llm_spl_draft",
        "generation_mode": "utility_llm_spl_draft",
        "llm_fallback_used": True,
        "utility_spl_draft_trace": {"llm_spl_draft_used": True},
    }
    assert spl_artifact_source(candidate) == "live_llm"
    assert llm_candidate_generated(candidate) is True


def test_invariant_e_deterministic_fallback_not_llm_candidate() -> None:
    candidate = {
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "generation_mode": "deterministic_lab_draft",
        "utility_spl_draft_trace": {"llm_spl_draft_used": False},
    }
    assert spl_artifact_source(candidate) == "deterministic_fallback"
    assert llm_candidate_generated(candidate) is False


def test_invariant_h_failover_requires_real_attempt() -> None:
    candidate = {
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "generation_mode": "deterministic_lab_draft",
        "llm_fallback_used": True,
        "utility_spl_draft_trace": {"llm_spl_draft_requested": False},
    }
    assert llm_failover_used_factual(candidate_spl=candidate, spl_validation=candidate, budget_records=[]) is False

    fallback_candidate = {
        "selected_candidate_spl_provider": "deterministic_lab_draft",
        "generation_mode": "deterministic_lab_draft",
        "utility_spl_draft_trace": {
            "llm_spl_draft_requested": True,
            "deterministic_skeleton_used": True,
            "llm_spl_draft_used": False,
        },
    }
    records = [{"role": "spl_advisory_generator", "outcome": "timed_out"}]
    assert llm_failover_used_factual(
        candidate_spl=fallback_candidate,
        spl_validation=fallback_candidate,
        budget_records=records,
    ) is True


def test_explicit_spl_authoring_routes_to_utility_path() -> None:
    from app.chat.spl_authoring_intent import is_universal_utility_spl_authoring

    query = (
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    )
    signals = {"explicit_spl_authoring": True}
    assert is_universal_utility_spl_authoring(query, signals) is True
