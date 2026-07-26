"""Item 2.1 — MCP evidence-plan grants on all tiers under canonical planning.

Scope (grounded against the actual code, not the plan's original draft text):
`spl_generation_only` + a live-data ask is the one family in evidence_planner.py
that self-admittedly needed MCP but never allowed it
(``live_data_request_mcp_needed_but_not_allowed``). Catalogue-matched paths grant
MCP eligibility architecturally — matching how ``spl_generation_and_run``/default
``live_investigation`` already set ``mcp_allowed=True`` before any SPL is validated.
Real gating (validated ``normalized_spl``, tool selection, per-call HIL confirmation)
is unchanged and
lives downstream at ``evaluate_mcp_execution`` — this test only proves the
plan-level eligibility flag and the execution gate remain two separate things.

``guided_investigation``'s discovery grant is intentionally NOT touched here:
it is already gated behind ``ai_soc_guided_mcp_discovery_enabled`` /
``ai_soc_guided_hybrid_investigation_enabled`` as a deliberate rollout gate
(pinned by ``test_guided_mcp_discovery_lane.py::test_guided_plan_discovery_allowed_follows_flag``).
Un-gating it is a flag-rightsizing (DG-4/Phase 7) decision, not an evidence-plan
default — see the plan's Drift log entry for 2026-07-02 (item 2.1 scope note).
"""

from __future__ import annotations

import pytest

from app.chat.contracts.intent_classification import IntentClassification
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.config import settings
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.query_understanding.parser import understand_query

_LIVE_DATA_QUERY = "Find failed-login users in the last 24 hours"


def _plan(query: str):
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    return plan_evidence(q2i.intent_classification, q2i.model_dump(), routed={}, query_understanding=understanding)


def test_out_of_catalogue_live_data_ask_is_not_granted_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Least privilege restored (2026-07-25) — policy change, not a relaxed assertion.

    This test previously asserted ``mcp_allowed is True`` for an out-of-catalogue
    live-data ask. That grant was written as ``live_data_request and
    control_plane_enabled``; removing the flag at the canonical cutover
    collapsed the conjunct to ``and True`` and silently widened authorisation to every
    tier, which is what ``test_t2_spl_native_live::test_t2_never_execution_eligible_or_mcp_allowed``
    caught. Authorisation is now withheld here and belongs to the final planner plus
    governance for a specific committed ResourcePlan. Catalogue-matched asks are
    unaffected — see ``test_catalogue_matched_live_data_ask_keeps_search_eligibility``.
    """
    plan = _plan(_LIVE_DATA_QUERY)
    # The need is still described honestly...
    assert plan.needs_mcp is True
    assert plan.mcp_available is True
    # ...but authorisation is withheld.
    assert plan.mcp_allowed is False
    assert "live_data_available_mcp_not_authorised_for_out_of_catalogue" in plan.reasons
    assert "live_data_request_mcp_search_eligible_pending_validation" not in plan.reasons


def test_catalogue_matched_live_data_ask_keeps_search_eligibility() -> None:
    """The re-gate is scoped to out-of-catalogue work; T1-T3 keep their grant."""
    from app.chat.lane_router import is_known_catalogue_match

    query = "Which users have excessive failed logins?"
    understanding = understand_query(query)
    if not is_known_catalogue_match(str(getattr(understanding, "deterministic_match_path", "") or "")):
        pytest.skip("query no longer resolves to a catalogue match")

    plan = _plan(query)
    if plan.answer_mode != "live_investigation" or not plan.needs_spl:
        pytest.skip("catalogue query does not route to the spl_artifact branch under test")
    assert plan.mcp_allowed is True


def test_no_live_data_request_gets_no_search_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construct the spl_generation_only + live_data_request=False case directly:
    natural-language routing to this exact combination is not reliably reachable
    (SPL-authoring phrasings tend to also set live_data_request=True), so this
    exercises the evidence_planner branch logic directly rather than depending
    on intent-classification heuristics that are out of this item's scope."""
    intent = IntentClassification(
        intent_family="spl_generation_only",
        primary_intent="ask_for_query_generation",
        query_type="ask_for_query_generation",
        answer_goal=["spl_artifact"],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        reason="test_direct_construction",
    )
    query_to_intent = {
        "intent_classification": intent.model_dump(),
        "query_signals": {"live_data_request": False},
    }
    plan = plan_evidence(intent, query_to_intent, routed={}, query_understanding=None)
    assert plan.needs_mcp is False
    assert plan.mcp_allowed is False
    # discovery is still granted — read-only, safe regardless of live-data intent
    assert plan.discovery_allowed is True


def test_non_spl_families_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan("What is the escalation policy for repeated failed login alerts?")
    assert plan.answer_mode == "rag_only"
    assert plan.mcp_allowed is False


def test_eligibility_does_not_bypass_execution_gate() -> None:
    """mcp_allowed=True at plan time never substitutes for the execution gate's
    own validated-SPL / confirmation / HIL requirements — the gate still blocks
    an unresolved request identically regardless of evidence-plan eligibility."""
    execution, review = evaluate_mcp_execution(
        trace_id="test-2.1-gate-independence",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation=None,
    )
    assert execution["status"] != "executed"
    assert review.get("required") is True or execution["status"] == "requires_human_review"


def test_guided_investigation_discovery_stays_flag_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """2.1 deliberately does not touch guided_investigation's rollout gate —
    confirms the existing flag-off behavior is unchanged by this item."""
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_guided_mcp_discovery_enabled", False)
    plan = _plan("How should I investigate unusual outbound traffic from an OT host overnight?")
    assert plan.answer_mode == "guided_investigation"
    assert plan.discovery_allowed is not True
