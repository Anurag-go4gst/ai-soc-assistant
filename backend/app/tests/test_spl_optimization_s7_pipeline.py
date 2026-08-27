"""OPTIONAL_PHASE_S S7 — producer_lineage + optimization chain wiring."""

from __future__ import annotations

import pytest

from app.chat import pipeline as pl
from app.schemas.requests import ChatRequest
from app.spl.spl_optimization_chain import resolve_producer_lineage
from app.spl.spl_source_resolve import SourceResolveResult

_RESOLVED_SPL = "search index=pgcil_soc sourcetype=pgcil:auth failed login earliest=-15m latest=now | stats count by user | head 100"
_QUERY = "who are the top users with failed logins in the SOC network"
_APPROVED = {
    "approved": True,
    "normalized_spl": _RESOLVED_SPL,
    "blocked_commands_found": [],
    "time_bounds_present": True,
    "result_limit_present": True,
}


def test_resolve_producer_lineage_free_text() -> None:
    assert (
        resolve_producer_lineage(
            {
                "producer_lineage": "llm_fallback",
                "selected_candidate_spl_provider": "llm_spl_advisory_fallback",
            }
        )
        == "llm_fallback"
    )


def test_derived_artifact_uses_candidate_producer_lineage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pl,
        "resolve_spl_source_profile",
        lambda *a, **k: SourceResolveResult(
            spl=_RESOLVED_SPL,
            fully_resolved=True,
            validation=_APPROVED,
            tiers_used=["session_pin"],
        ),
    )
    state = {
        "request": ChatRequest(message=_QUERY),
        "trace_id": "test-s7-lineage",
        "effective_query": _QUERY,
        "evidence_plan": {"needs_spl": True},
        "candidate_spl": {
            "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> | stats count by user | head 100",
            "lab_tier_exposure": True,
            "producer_lineage": "llm_fallback",
        },
        "spl_validation": {"approved": False, "normalized_spl": None, "lab_candidate_eligible": True},
        "soc_kb_retrieval": {},
        "session_pins": None,
        "workflow_plan": {},
    }
    result = pl.graph_node_spl_source_resolve(state)
    derived = result.get("llm_derived_spl_artifact")
    assert isinstance(derived, dict)
    assert derived["producer_lineage"] == "llm_fallback"
