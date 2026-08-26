"""J7: remediation CTA requires evidence-backed suspicious disposition."""

from __future__ import annotations

import pytest

from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.chat.remediation_runtime import (
    maybe_attach_remediation_offer,
    remediation_offer_cta_eligible,
)
from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL
from app.config import settings


@pytest.fixture(autouse=True)
def _enable_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _investigation_rqc(**overrides) -> dict:
    payload = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "required_capabilities": [CAPABILITY_SPL, CAPABILITY_MCP],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
        "normalized_goal": "investigate confirmed brute force",
    }
    payload.update(overrides)
    return payload


def _pure_sop_rqc() -> dict:
    return {
        "intent_family": "knowledge_only",
        "answer_goal": "policy_citation",
        "required_capabilities": [],
        "understanding_source": "deterministic_qualification",
        "clarification_required": False,
        "ambiguity_state": "unambiguous",
        "normalized_goal": "show the incident response SOP",
    }


def _completed_suspicious(**overrides) -> dict:
    payload = {
        "schema_version": "investigation_outcome_v2",
        "investigation_status": "completed",
        "disposition": "suspicious",
        "remediation_offer_required": True,
        "severity_label": "P2",
        "evidence_refs": ["ev.auth"],
        "findings": ["repeated failed logins"],
    }
    payload.update(overrides)
    return payload


def _state(outcome: dict, **extra) -> dict:
    return {"investigation_outcome": outcome, **extra}


# --- negatives (NEG-1..NEG-7) ---


def test_neg1_knowledge_recall_sop_no_cta() -> None:
    state = _state(
        _completed_suspicious(),
        routed={"skill": "knowledge_recall"},
        resolved_query_contract=_pure_sop_rqc(),
        context_sufficiency={"answer_mode": "knowledge_only_answer"},
    )
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_neg2_knowledge_only_answer_no_cta() -> None:
    state = _state(
        _completed_suspicious(),
        routed={"skill": "attack_discovery"},
        context_sufficiency={"answer_mode": "knowledge_only_answer"},
    )
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_neg3_planned_incomplete_no_cta() -> None:
    state = _state(_completed_suspicious(investigation_status="incomplete"))
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_neg4_blocked_or_empty_evidence_path_no_cta() -> None:
    blocked = _state(_completed_suspicious(investigation_status="blocked", disposition="inconclusive"))
    assert "remediation_approval" not in maybe_attach_remediation_offer(blocked)
    empty = _state(_completed_suspicious(disposition="inconclusive", evidence_refs=[]))
    assert "remediation_approval" not in maybe_attach_remediation_offer(empty)


def test_neg5_completed_inconclusive_no_cta() -> None:
    state = _state(_completed_suspicious(disposition="inconclusive"))
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_neg6_evidence_refs_without_suspicious_no_cta() -> None:
    """Refs alone are not remediation authority — disposition must be suspicious."""
    state = _state(
        _completed_suspicious(disposition="inconclusive", evidence_refs=["ev1", "ev2"])
    )
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_neg7_default_off_no_cta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    state = _state(_completed_suspicious())
    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_suspicious_alone_without_completed_no_cta() -> None:
    state = _state(_completed_suspicious(investigation_status="incomplete"))
    assert remediation_offer_cta_eligible(state) is False


# --- positive (J6-class) ---


def test_pos_completed_suspicious_attaches_cta() -> None:
    state = _state(
        _completed_suspicious(),
        routed={"skill": "attack_discovery"},
        resolved_query_contract=_investigation_rqc(),
        context_sufficiency={"answer_mode": "live_investigation"},
    )
    assert remediation_offer_cta_eligible(state) is True
    offered = maybe_attach_remediation_offer(state)
    assert offered["remediation_approval"]["status"] == "offered"
    assert offered["remediation_approval"]["validated_plan"] is None


def test_multi_goal_investigation_not_vetoed_by_legacy_knowledge_skill() -> None:
    requested_actions = [
        {
            "action_kind": "remediation",
            "lifecycle_state": "PENDING_CONDITION",
            "predicate_id": "account_compromise_confirmed",
            "recipient_roles": [],
        },
        {
            "action_kind": "email_draft",
            "lifecycle_state": "PENDING_CONDITION",
            "predicate_id": "account_compromise_confirmed",
            "recipient_roles": ["firewall_team", "identity_team"],
        },
    ]
    state = _state(
        _completed_suspicious(),
        routed={"skill": "knowledge_recall"},
        resolved_query_contract=_investigation_rqc(
            intent_family="hybrid_investigation_plus_policy",
            answer_goal="analyst_action_guidance",
            requested_conditional_actions=requested_actions,
        ),
        context_sufficiency={"answer_mode": "rag_plus_live"},
    )
    assert remediation_offer_cta_eligible(state) is True
    offered = maybe_attach_remediation_offer(state)
    assert offered["remediation_approval"]["status"] == "offered"
    assert offered["resolved_query_contract"]["requested_conditional_actions"] == requested_actions
    email = next(
        action
        for action in offered["resolved_query_contract"]["requested_conditional_actions"]
        if action["action_kind"] == "email_draft"
    )
    assert email["lifecycle_state"] == "PENDING_CONDITION"


def test_multi_goal_inconclusive_preserves_intents_without_cta() -> None:
    requested_actions = [
        {
            "action_kind": "email_draft",
            "lifecycle_state": "PENDING_CONDITION",
            "predicate_id": "account_compromise_confirmed",
            "recipient_roles": ["firewall_team"],
        }
    ]
    state = _state(
        _completed_suspicious(
            investigation_status="incomplete",
            disposition="inconclusive",
            remediation_offer_required=False,
            evidence_refs=[],
        ),
        routed={"skill": "knowledge_recall"},
        resolved_query_contract=_investigation_rqc(
            intent_family="hybrid_investigation_plus_policy",
            answer_goal="analyst_action_guidance",
            requested_conditional_actions=requested_actions,
        ),
        context_sufficiency={"answer_mode": "insufficient_evidence"},
    )
    unchanged = maybe_attach_remediation_offer(state)
    assert "remediation_approval" not in unchanged
    assert unchanged["resolved_query_contract"]["requested_conditional_actions"] == requested_actions


def test_pos_derived_outcome_with_live_obtained_p2_is_suspicious() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "SUFFICIENT", "missing": [], "next_action": "CONTINUE"},
        evidence_state={"obtained": ["auth_events"], "missing": []},
        final_evidence_gate={
            "collected_evidence_refs": ["ev.auth"],
            "allow_live_result_language": True,
        },
        investigation_run_status={"status": "completed"},
        investigation_approval={"status": "approved"},
        severity_label="P2",
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    ).model_dump(mode="json")
    assert outcome["disposition"] == "suspicious"
    assert outcome["investigation_status"] == "completed"
    state = maybe_attach_remediation_offer({"investigation_outcome": outcome})
    assert state["remediation_approval"]["status"] == "offered"


def test_cta_is_not_execution() -> None:
    offered = maybe_attach_remediation_offer(_state(_completed_suspicious()))
    approval = offered["remediation_approval"]
    assert approval["status"] == "offered"
    assert approval.get("execution_result") is None
    assert approval.get("approved_envelope") is None
