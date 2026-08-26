"""Post-P10 3.3 — deterministic B4 conditional-action lifecycle."""

from __future__ import annotations

import pytest

from app.chat.remediation_runtime import maybe_attach_remediation_offer
from app.config import settings


@pytest.fixture(autouse=True)
def _enable_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _actions() -> list[dict]:
    return [
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


def _state(*, predicate_evidence: bool, simulated: bool = False) -> dict:
    evidence_item = {
        "key": "account_compromise_confirmed",
        "status": "obtained",
        "provenance": "mock_mcp" if simulated else "canonical_facts",
        "scope": {
            "simulated": simulated,
            "predicate_id": "account_compromise_confirmed",
            "predicate_value": True,
            "evidence_refs": ["ev.auth"],
        },
    }
    return {
        "investigation_outcome": {
            "schema_version": "investigation_outcome_v2",
            "investigation_status": "completed",
            "disposition": "suspicious",
            "remediation_offer_required": False,
            "evidence_refs": ["ev.auth"],
            "findings": ["accepted evidence confirms account compromise"],
            "action_eligibility": {"allowed_actions": [], "unavailable_actions": []},
        },
        "resolved_query_contract": {
            "intent_family": "hybrid_investigation_plus_policy",
            "answer_goal": "analyst_action_guidance",
            "required_capabilities": ["spl", "mcp"],
            "requested_conditional_actions": _actions(),
        },
        "context_sufficiency": {"answer_mode": "rag_plus_live"},
        "evidence_state": {
            "obtained": ["account_compromise_confirmed"] if predicate_evidence else [],
            "items": [evidence_item] if predicate_evidence else [],
        },
        "final_evidence_gate": {
            "allow_environment_fact_claims": True,
            "environment_evidence_count": 1,
            "source_evidence_status": "collected",
        },
    }


def _states(result: dict) -> dict[str, str]:
    return {
        action["action_kind"]: action["lifecycle_state"]
        for action in result["resolved_query_contract"]["requested_conditional_actions"]
    }


def test_cv_multi_01a_unmet_predicate_stays_pending_without_plan() -> None:
    state = _state(predicate_evidence=False)
    state["investigation_outcome"] = {
        **state["investigation_outcome"],
        "investigation_status": "incomplete",
        "disposition": "inconclusive",
        "evidence_refs": [],
    }

    result = maybe_attach_remediation_offer(state, raw_output_provider=lambda: "{}")

    assert _states(result) == {
        "remediation": "PENDING_CONDITION",
        "email_draft": "PENDING_CONDITION",
    }
    assert "remediation_approval" not in result


def test_requested_action_with_predicate_normalizes_to_pending() -> None:
    state = _state(predicate_evidence=False)
    state["resolved_query_contract"]["requested_conditional_actions"][0][
        "lifecycle_state"
    ] = "REQUESTED"

    result = maybe_attach_remediation_offer(state, raw_output_provider=lambda: "{}")

    assert _states(result)["remediation"] == "PENDING_CONDITION"


def test_suspicious_without_exact_predicate_evidence_stays_pending_but_plan_may_present() -> None:
    result = maybe_attach_remediation_offer(_state(predicate_evidence=False))

    assert _states(result) == {
        "remediation": "PENDING_CONDITION",
        "email_draft": "PENDING_CONDITION",
    }
    assert result["remediation_approval"]["status"] == "awaiting_approval"
    assert result["remediation_approval"]["validated_plan"] is not None
    assert result["remediation_planning_trace"]["attempted"] is False
    assert result["remediation_planning_trace"]["skipped_reason"] == (
        "automatic_requested_plan_uses_deterministic_baseline"
    )
    assert "approved_remediation_envelope" not in result
    assert "remediation_execution" not in result


def test_cv_multi_01b_exact_accepted_predicate_advances_to_eligible() -> None:
    result = maybe_attach_remediation_offer(
        _state(predicate_evidence=True),
        raw_output_provider=lambda: "{}",
    )

    assert _states(result) == {"remediation": "ELIGIBLE", "email_draft": "ELIGIBLE"}
    assert result["remediation_approval"]["status"] == "awaiting_approval"
    assert result["remediation_approval"]["validated_plan"] is not None
    assert "approved_remediation_envelope" not in result
    assert "remediation_execution" not in result


def test_simulated_evidence_cannot_satisfy_user_predicate() -> None:
    result = maybe_attach_remediation_offer(
        _state(predicate_evidence=True, simulated=True),
        raw_output_provider=lambda: "{}",
    )
    assert _states(result) == {
        "remediation": "PENDING_CONDITION",
        "email_draft": "PENDING_CONDITION",
    }


def test_obtained_key_without_true_bound_assertion_cannot_satisfy_predicate() -> None:
    state = _state(predicate_evidence=True)
    state["evidence_state"]["items"][0]["scope"]["predicate_value"] = False

    result = maybe_attach_remediation_offer(state, raw_output_provider=lambda: "{}")

    assert _states(result) == {
        "remediation": "PENDING_CONDITION",
        "email_draft": "PENDING_CONDITION",
    }
