"""P3 — Final RQC product applicability (SPL authoring ≠ investigation).

Pins evidence_planner, final_evidence_gate, InvestigationOutcome, and remediation
offer seams against Final-RQC semantics. No firewall keyword special-cases.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.investigation_outcome import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V2,
    derive_investigation_outcome,
)
from app.chat.evidence_planner import plan_evidence
from app.chat.investigation_shaped import (
    investigation_outcome_applicable,
    is_investigation_shaped_final_rqc,
)
from app.chat.remediation_runtime import maybe_attach_remediation_offer
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL
from app.chat.spl_authoring_intent import is_explicit_review_only_spl_authoring
from app.config import settings
from app.evidence.final_evidence_gate import apply_final_evidence_gate


def _spl_authoring_rqc(**overrides: object) -> dict:
    base = {
        "intent_family": "spl_generation_only",
        "answer_goal": "spl_artifact",
        "required_capabilities": [CAPABILITY_SPL],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
        "normalized_goal": "author review-only SPL",
    }
    base.update(overrides)
    return base


def _investigation_rqc(**overrides: object) -> dict:
    base = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "required_capabilities": [CAPABILITY_SPL, CAPABILITY_MCP],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
        "normalized_goal": "investigate failed logins",
    }
    base.update(overrides)
    return base


def _spl_generation_intent(*, explicit: bool = True) -> IntentClassification:
    return IntentClassification(
        intent_family="spl_generation_only",
        primary_intent="ask_for_query_generation",
        query_type="ask_for_query_generation",
        answer_goal=["spl_artifact"],
        confidence=0.9,
        confidence_band="high",
        requires_clarification=False,
        reason="test_spl_authoring_product",
    )


def test_shared_applicability_predicate_parity() -> None:
    """Evidence / outcome / remediation must resolve the same Final-RQC shape."""
    spl = _spl_authoring_rqc()
    inv = _investigation_rqc()
    assert investigation_outcome_applicable(resolved_query_contract=spl) is False
    assert is_investigation_shaped_final_rqc(resolved_query_contract=spl) is False
    assert investigation_outcome_applicable(resolved_query_contract=inv) is True
    assert is_investigation_shaped_final_rqc(resolved_query_contract=inv) is True


def test_surrogate_signals_alone_do_not_make_spl_authoring_investigation() -> None:
    """T4 / MCP-down / zero evidence / live-data / unresolved are not product authority."""
    rqc = _spl_authoring_rqc(
        understanding_source="semantic_t4",
        provenance={"t4_used": True, "source_unresolved": True},
    )
    assert investigation_outcome_applicable(resolved_query_contract=rqc) is False
    assert is_investigation_shaped_final_rqc(
        resolved_query_contract=rqc,
        query_understanding=SimpleNamespace(soc_investigation_shaped=False),
    ) is False


def test_explicit_review_only_spl_authoring_signal() -> None:
    assert is_explicit_review_only_spl_authoring(
        {"explicit_spl_authoring": True, "live_data_request": True}
    )
    assert not is_explicit_review_only_spl_authoring(
        {"explicit_spl_authoring": True, "explicit_run_spl": True}
    )
    assert not is_explicit_review_only_spl_authoring({"live_data_request": True})


def test_evidence_planner_explicit_spl_authoring_is_not_live_investigation() -> None:
    intent = _spl_generation_intent()
    q2i = {
        "intent_classification": intent.model_dump(),
        "query_signals": {
            "explicit_spl_authoring": True,
            "live_data_request": True,
        },
    }
    plan = plan_evidence(
        intent,
        q2i,
        routed={},
        query_understanding=SimpleNamespace(
            deterministic_match_path="out_of_registry",
            soc_investigation_shaped=False,
        ),
    )
    assert plan.answer_mode == "spl_utility_authoring"
    assert plan.needs_spl is True
    assert plan.needs_mcp is False
    assert plan.mcp_allowed is False
    assert (
        "explicit_spl_authoring_review_only" in plan.reasons
        or "universal_spl_utility_authoring" in plan.reasons
    )
    if "explicit_spl_authoring_review_only" in plan.reasons:
        assert "live_data_interest_not_investigation_product" in plan.reasons


def test_evidence_planner_non_explicit_live_data_spl_keeps_descriptive_mcp() -> None:
    """Catalogue / live-data SPL asks without explicit authoring keep prior plan shape."""
    intent = _spl_generation_intent(explicit=False)
    q2i = {
        "intent_classification": intent.model_dump(),
        "query_signals": {"live_data_request": True, "explicit_spl_authoring": False},
    }
    plan = plan_evidence(intent, q2i, routed={}, query_understanding=None)
    assert plan.answer_mode == "live_investigation"
    assert plan.needs_mcp is True
    assert plan.mcp_allowed is False


def test_final_evidence_gate_spl_utility_does_not_assess_severity_or_force_hil() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={
            "answer_mode": "spl_utility_authoring",
            "needs_mitre": False,
            "needs_mcp": False,
            "mcp_allowed": False,
        },
        intent={"intent_family": "spl_generation_only"},
        spl_validation={"approved": False, "normalized_spl": None},
        route_live_data_request=True,
        execution_authorized=False,
        effective_hil_required=False,
        policy_backed=True,
        severity_label="P2 High",
    )
    assert gate.allow_severity_assessment is False
    assert gate.severity_label is None
    assert gate.effective_hil_required is False
    assert gate.allow_live_result_language is False
    assert gate.collected_evidence_count == 0


def test_final_evidence_gate_zero_evidence_live_data_does_not_resurrect_investigation_severity() -> None:
    gate = apply_final_evidence_gate(
        source_evidence=[],
        execution={"status": "skipped"},
        soc_kb_retrieval=None,
        mcp_evidence=None,
        evidence_plan={
            "answer_mode": "spl_utility_authoring",
            "needs_mitre": False,
        },
        intent={"intent_family": "spl_generation_only"},
        spl_validation=None,
        route_live_data_request=True,
        execution_authorized=False,
    )
    assert gate.allow_severity_assessment is False
    assert gate.collected_evidence_count == 0
    assert gate.allow_live_result_language is False


def test_pure_spl_authoring_outcome_has_no_investigation_status() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["mcp_rows"], "next_action": "BLOCK"},
        context_sufficiency={"status": "INSUFFICIENT"},
        final_evidence_gate={"collected_evidence_refs": [], "allow_live_result_language": False},
        resolved_query_contract=_spl_authoring_rqc(),
        outcome_v2_enabled=True,
    )
    payload = outcome.model_dump(mode="json")
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "investigation_status" not in payload
    assert payload.get("remediation_offer_required") is not True
    assert payload["disposition"] != "blocked"
    assert payload["provenance"].get("investigation_outcome_applicable") is False


def test_spl_authoring_mcp_unavailable_and_zero_evidence_do_not_create_investigation() -> None:
    outcome = derive_investigation_outcome(
        evidence_state={"obtained": [], "missing": ["live_rows"], "blocked": ["mcp"]},
        evidence_sufficiency={"status": "BLOCKED", "missing": ["live_rows"], "next_action": "BLOCK"},
        final_evidence_gate={
            "collected_evidence_refs": [],
            "collected_evidence_count": 0,
            "allow_live_result_language": False,
        },
        resolved_query_contract=_spl_authoring_rqc(
            provenance={"mcp_unavailable": True, "t4_used": True}
        ),
        outcome_v2_enabled=True,
    )
    payload = outcome.model_dump(mode="json")
    assert "investigation_status" not in payload
    assert payload.get("recommended_next_action") is None


def test_spl_authoring_via_t4_source_same_product_lifecycle() -> None:
    """Understanding path (ACCEPT vs T4) must not change product applicability."""
    det = _spl_authoring_rqc(understanding_source="deterministic_qualification")
    t4 = _spl_authoring_rqc(understanding_source="semantic_t4", provenance={"t4_used": True})
    assert investigation_outcome_applicable(resolved_query_contract=det) is False
    assert investigation_outcome_applicable(resolved_query_contract=t4) is False
    for rqc in (det, t4):
        payload = derive_investigation_outcome(
            evidence_sufficiency={"status": "BLOCKED", "next_action": "BLOCK"},
            resolved_query_contract=rqc,
            outcome_v2_enabled=True,
        ).model_dump(mode="json")
        assert "investigation_status" not in payload


def test_genuine_investigation_still_gets_outcome_v2() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "PARTIAL", "missing": ["session"], "next_action": "CONTINUE"},
        evidence_state={"obtained": ["auth"], "missing": ["session"]},
        final_evidence_gate={"collected_evidence_refs": ["ev1"], "allow_live_result_language": True},
        resolved_query_contract=_investigation_rqc(),
        investigation_approval={"status": "approved"},
        outcome_v2_enabled=True,
    )
    assert outcome.schema_version == SCHEMA_VERSION_V2
    assert outcome.investigation_status == "incomplete"
    assert outcome.remediation_offer_required is True


def test_genuine_investigation_evidence_unavailable_remains_investigation() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["connector"], "next_action": "BLOCK"},
        context_sufficiency={"status": "blocked_by_policy", "reasons": ["mcp unavailable"]},
        investigation_run_status={"status": "blocked", "next_action": "request_operator_readiness"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    assert outcome.schema_version == SCHEMA_VERSION_V2
    assert outcome.investigation_status == "blocked"
    assert outcome.disposition == "inconclusive"


def test_remediation_offer_not_attached_for_spl_authoring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "next_action": "BLOCK"},
        resolved_query_contract=_spl_authoring_rqc(),
        outcome_v2_enabled=True,
    ).model_dump(mode="json")
    state = maybe_attach_remediation_offer({"investigation_outcome": outcome})
    assert "remediation_approval" not in state


def test_remediation_offer_preserved_for_investigation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "SUFFICIENT", "missing": [], "next_action": "CONTINUE"},
        investigation_run_status={"status": "completed"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    ).model_dump(mode="json")
    assert outcome.get("remediation_offer_required") is True
    state = maybe_attach_remediation_offer({"investigation_outcome": outcome})
    assert state.get("remediation_approval", {}).get("status") == "offered"


def test_review_only_do_not_execute_shape_via_signals() -> None:
    """Review-only / do-not-execute is a product shape, not a sentence special-case."""
    intent = IntentClassification(
        intent_family="spl_generation_only",
        primary_intent="ask_for_query_generation",
        query_type="ask_for_query_generation",
        answer_goal=["spl_artifact"],
        confidence=0.95,
        confidence_band="high",
        requires_clarification=False,
        reason="review_only_spl_shape",
    )
    signals = {
        "explicit_spl_authoring": True,
        "live_data_request": True,
        "do_not_execute": True,
        "explicit_run_spl": False,
        "run_execution": False,
    }
    plan = plan_evidence(
        intent,
        {"intent_classification": intent.model_dump(), "query_signals": signals},
        routed={},
        query_understanding=SimpleNamespace(
            deterministic_match_path="out_of_registry",
            soc_investigation_shaped=False,
        ),
    )
    assert plan.answer_mode == "spl_utility_authoring"
    assert plan.mcp_allowed is False
    rqc = _spl_authoring_rqc(
        provenance={
            "explicit_user_constraints": {
                "data_scope": {"index": ["pgcil_soc"], "sourcetype": ["cisco:firepower"]},
                "time_window": "30d",
                "execution_prohibited": True,
            }
        }
    )
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "next_action": "BLOCK"},
        resolved_query_contract=rqc,
        outcome_v2_enabled=True,
    ).model_dump(mode="json")
    assert "investigation_status" not in outcome
    constraints = (rqc.get("provenance") or {}).get("explicit_user_constraints") or {}
    assert constraints["data_scope"]["index"] == ["pgcil_soc"]
    assert constraints["data_scope"]["sourcetype"] == ["cisco:firepower"]
    assert constraints["time_window"] == "30d"
    assert constraints["execution_prohibited"] is True


def test_legacy_outcome_call_without_rqc_still_packages_v2() -> None:
    """Backward compatible: absent Final-RQC semantics keep prior V2 packaging."""
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["x"], "next_action": "BLOCK"},
        investigation_approval={"status": "approved"},
        outcome_v2_enabled=True,
    )
    assert outcome.schema_version == SCHEMA_VERSION_V2
    assert outcome.investigation_status == "blocked"
