"""Item 2.3 (respec'd 2026-07-03) — derived-artifact pipeline, end to end.

Covers the two nodes the derived artifact flows through:
`graph_node_spl_source_resolve` (creates it, never touches the raw lab-tier
candidate) and `graph_node_execution` (consumes it — low auto-executes,
medium requires HIL, high blocks pre-gate). `resolve_spl_source_profile` is
monkeypatched to isolate this item's new logic from unrelated SOC-KB/session
-pin resolution complexity, which is pre-existing and tested elsewhere.
"""

from __future__ import annotations

import pytest

from app.chat import pipeline as pl
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.spl_source_resolve import SourceResolveResult

_RESOLVED_SPL = "search index=pgcil_soc sourcetype=pgcil:auth failed login earliest=-15m latest=now | stats count by user | head 100"
_QUERY = "who are the top users with failed logins in the SOC network"

_APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": _RESOLVED_SPL,
    "blocked_commands_found": [],
    "time_bounds_present": True,
    "result_limit_present": True,
}


def _lab_tier_state(query: str = _QUERY) -> dict:
    return {
        "request": ChatRequest(message=query),
        "trace_id": "test-derived-pipeline",
        "effective_query": query,
        "evidence_plan": {"needs_spl": True},
        "candidate_spl": {
            "candidate_spl": "search index=<auth_index> sourcetype=<auth_sourcetype> | stats count by user | head 100",
            "lab_tier_exposure": True,
            "detection_family": "auth_failed_login",
        },
        "spl_validation": {"approved": False, "normalized_spl": None, "lab_candidate_eligible": True},
        "soc_kb_retrieval": {},
        "session_pins": None,
        "workflow_plan": {},
    }


def test_derived_artifact_created_raw_candidate_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pl,
        "resolve_spl_source_profile",
        lambda *a, **k: SourceResolveResult(
            spl=_RESOLVED_SPL,
            fully_resolved=True,
            validation=_APPROVED_VALIDATION,
            tiers_used=["session_pin"],
        ),
    )
    state = _lab_tier_state()
    result = pl.graph_node_spl_source_resolve(state)

    # Raw candidate: untouched governance invariant, unchanged from before this item.
    assert result["spl_validation"]["approved"] is False or "approved" not in result["spl_validation"]
    assert result["candidate_spl"]["lab_tier_exposure"] is True

    derived = result.get("llm_derived_spl_artifact")
    assert isinstance(derived, dict)
    assert derived["normalized_spl"] == _RESOLVED_SPL
    assert derived["blocked"] is False
    assert derived["risk_tier"] in {"low", "medium"}
    assert derived["producer_lineage"] == "llm_plan_compiler"


def test_unresolved_slots_go_to_hil_clarification_never_lab_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pl,
        "resolve_spl_source_profile",
        lambda *a, **k: SourceResolveResult(
            spl="search index=<auth_index> sourcetype=<auth_sourcetype> | stats count by user | head 100",
            fully_resolved=False,
            missing_slots=["auth_index", "auth_sourcetype"],
            validation=None,
        ),
    )
    state = _lab_tier_state()
    result = pl.graph_node_spl_source_resolve(state)

    assert "llm_derived_spl_artifact" not in result
    review = result.get("human_review")
    assert isinstance(review, dict) and review.get("required") is True
    assert review.get("review_type") == "spl_source_profile_clarification"
    # Never silently promoted to a lab draft as a substitute for clarification.
    assert result["spl_validation"].get("review_required_reason") == "spl_source_profile_clarification"


@pytest.mark.parametrize(
    "risk_tier,auto_eligible,expected_status",
    [
        ("low", True, "executed"),
        ("medium", False, "requires_human_review"),
    ],
)
def test_execution_node_dispatches_by_risk_tier(
    monkeypatch: pytest.MonkeyPatch, risk_tier: str, auto_eligible: bool, expected_status: str
) -> None:
    # Execution-enablement is checked from THREE independent sources in this
    # codebase and all three must agree for a real mock dispatch to succeed:
    # registry status (app.connectors.mcp.registry, raw env), the gate's own
    # registry.global_execution_enabled check (same raw env), and the mock
    # connector's dispatch check (app.connectors.mcp.mock, settings object).
    monkeypatch.setenv("MCP_MODE", "mock")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", True)
    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    # conftest's disable_spl_execution_confirmation_in_tests autouse fixture
    # defaults this to False for legacy test convenience; production defaults
    # true, and the medium-risk lane's HIL requirement only means anything
    # when confirmation is actually on.
    monkeypatch.setattr(settings, "ai_soc_require_spl_execution_confirmation", True)

    state = {
        "request": ChatRequest(message=_QUERY),
        "trace_id": "test-derived-exec",
        "workflow_plan": {"skill": "attack_discovery", "execution_enabled": False},
        "routed": {"skill": "attack_discovery"},
        "route_plan_shadow": {},
        "session_pins": None,
        "evidence_plan": {"mcp_allowed": True},
        "llm_derived_spl_artifact": {
            "normalized_spl": _RESOLVED_SPL,
            "blocked": False,
            "blocked_reason": None,
            "risk_tier": risk_tier,
            "auto_eligible": auto_eligible,
            "producer_lineage": "llm_plan_compiler",
        },
    }
    monkeypatch.setattr(pl, "_effective_routing_skill", lambda s: "attack_discovery")
    result = pl.graph_node_execution(state)
    assert result["execution"]["status"] == expected_status


def test_execution_node_blocks_high_risk_before_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "request": ChatRequest(message=_QUERY),
        "trace_id": "test-derived-exec-blocked",
        "workflow_plan": {},
        "route_plan_shadow": {},
        "session_pins": None,
        "llm_derived_spl_artifact": {
            "normalized_spl": None,
            "blocked": True,
            "blocked_reason": "prompt_injection_detected",
            "risk_tier": "high",
        },
    }
    result = pl.graph_node_execution(state)
    assert result["execution"]["status"] == "skipped"
    assert result["execution"]["block_reason"] == "prompt_injection_detected"
    assert result["execution"]["tool_selection_status"] == "blocked_by_llm_lineage_vigilance"
    assert result["human_review"]["required"] is False
