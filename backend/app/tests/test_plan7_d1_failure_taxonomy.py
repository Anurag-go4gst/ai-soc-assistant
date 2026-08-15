"""Plan 7 D1 — a provider failure must not be reported as a timeout.

Measured in C3: every provider exception — DNS failure, refused connection, 5xx —
was surfaced as `timed_out=True` with note `llm_assist_timed_out`. That made
"T4 timed out" ambiguous between *the model was slow* and *the endpoint was
unreachable*, which is precisely the distinction D1's LLM-unavailable and
LLM-timeout rows have to make.

The fix is deliberately narrow. `timed_out` keeps its existing meaning for the
many callers that branch on it ("the hop produced nothing, degrade"), and a
separate `failure_kind` carries the accurate class. Nothing about acceptance,
routing or capability changes.
"""

from __future__ import annotations

import json

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.semantic_t4_understanding import maybe_enrich_t4_semantic
from app.config import settings
from app.llm.sidecar_governance import (
    FAILURE_PROVIDER_UNAVAILABLE,
    FAILURE_TIMEOUT,
    NOTE_LLM_PROVIDER_UNAVAILABLE,
    NOTE_LLM_ASSIST_TIMED_OUT,
    run_sidecar_llm_with_timeout,
)


def _contract() -> ResolvedQueryContract:
    return ResolvedQueryContract(
        normalized_goal="deterministic goal",
        intent_family="live_investigation",
        answer_goal="live_results",
        ambiguity_state="unambiguous",
        qualification_tier="T4",
        qualification_source="deterministic_qualification",
    )


# --- the sidecar seam ---------------------------------------------------------


def test_connection_error_is_classified_provider_unavailable_not_timeout() -> None:
    def _boom() -> str:
        raise ConnectionRefusedError("connection refused")

    result = run_sidecar_llm_with_timeout(_boom, timeout_seconds=5.0)

    assert result.failure_kind == FAILURE_PROVIDER_UNAVAILABLE
    assert NOTE_LLM_PROVIDER_UNAVAILABLE in result.notes
    assert NOTE_LLM_ASSIST_TIMED_OUT not in result.notes
    assert result.raw_output is None


def test_dns_failure_is_classified_provider_unavailable() -> None:
    import socket

    def _boom() -> str:
        raise socket.gaierror("Temporary failure in name resolution")

    result = run_sidecar_llm_with_timeout(_boom, timeout_seconds=5.0)

    assert result.failure_kind == FAILURE_PROVIDER_UNAVAILABLE


def test_a_real_timeout_still_maps_to_timeout() -> None:
    import time as _time

    def _slow() -> str:
        _time.sleep(2.0)
        return "{}"

    result = run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.2)

    assert result.failure_kind == FAILURE_TIMEOUT
    assert result.timed_out is True
    assert NOTE_LLM_ASSIST_TIMED_OUT in result.notes


def test_success_carries_no_failure_kind() -> None:
    result = run_sidecar_llm_with_timeout(lambda: "{}", timeout_seconds=5.0)

    assert result.failure_kind is None
    assert result.timed_out is False


# --- what T4 reports ----------------------------------------------------------


@pytest.fixture(autouse=True)
def _t4_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)


def test_t4_reports_provider_unavailable_distinctly(monkeypatch) -> None:
    """The trace must not claim a timeout the model never had."""

    def _unreachable(_query, _contract):
        raise ConnectionRefusedError("connection refused")

    enriched = maybe_enrich_t4_semantic(
        _contract(), query="hunt for beaconing", raw_output_provider=_unreachable
    )
    trace = enriched.provenance["semantic_t4"]

    assert "provider_unavailable" in trace["rejected_reasons"]
    assert "timed_out" not in trace["rejected_reasons"]
    assert trace["timed_out"] is False
    assert trace["accepted"] is False
    # Deterministic degradation is unchanged.
    assert enriched.normalized_goal == "deterministic goal"
    assert enriched.clarification_required is False


def test_t4_still_reports_a_real_timeout_as_timeout(monkeypatch) -> None:
    import time as _time

    def _slow(_query, _contract):
        _time.sleep(2.0)
        return json.dumps({"normalized_goal": "x"})

    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_timeout_seconds", 0.2)
    enriched = maybe_enrich_t4_semantic(
        _contract(), query="hunt for beaconing", raw_output_provider=_slow
    )
    trace = enriched.provenance["semantic_t4"]

    assert "timed_out" in trace["rejected_reasons"]
    assert trace["timed_out"] is True


def test_malformed_output_stays_distinct_from_both(monkeypatch) -> None:
    enriched = maybe_enrich_t4_semantic(
        _contract(),
        query="hunt for beaconing",
        raw_output_provider=lambda _q, _c: "not json at all",
    )
    trace = enriched.provenance["semantic_t4"]

    assert "schema_invalid" in trace["rejected_reasons"]
    assert "timed_out" not in trace["rejected_reasons"]
    assert "provider_unavailable" not in trace["rejected_reasons"]
