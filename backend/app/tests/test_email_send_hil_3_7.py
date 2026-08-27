"""Post-P10 3.7 — email send requires separate HIL; draft/proposal alone never send."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chat.contracts.email_draft import GovernedEmailDraft
from app.chat.contracts.remediation_plan import ApprovedRemediationEnvelope
from app.chat.pipeline import _apply_remediation_lifecycle
from app.chat.remediation_runtime import (
    email_send_eligible,
    handle_remediation_review,
    maybe_attach_remediation_offer,
    resolve_requested_conditional_actions,
)
from app.config import settings


def _conditional_state(*, predicate_satisfied: bool) -> dict:
    evidence_item = {
        "key": "account_compromise_confirmed",
        "status": "obtained",
        "provenance": "canonical_facts",
        "scope": {
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
            "findings": ["25 failed SSH logins were followed by an admin login from 198.51.100.42."],
            "severity_label": "P2 High",
            "action_eligibility": {
                "allowed_actions": ["email_send"],
                "unavailable_actions": [],
            },
        },
        "resolved_query_contract": {
            "intent_family": "hybrid_investigation_plus_policy",
            "answer_goal": "analyst_action_guidance",
            "requested_conditional_actions": [
                {
                    "action_kind": "email_draft",
                    "lifecycle_state": "PENDING_CONDITION",
                    "predicate_id": "account_compromise_confirmed",
                    "recipient_roles": ["firewall_team", "identity_team"],
                }
            ],
        },
        "context_sufficiency": {"answer_mode": "rag_plus_live"},
        "evidence_state": {
            "obtained": ["account_compromise_confirmed"] if predicate_satisfied else [],
            "items": [evidence_item] if predicate_satisfied else [],
        },
        "final_evidence_gate": {
            "allow_environment_fact_claims": True,
            "environment_evidence_count": 1,
            "source_evidence_status": "collected",
        },
        "capability_snapshot": {
            "schema_version": "capability_snapshot_v1",
            "rows": [
                {
                    "capability_id": "email_send",
                    "capability_need": "recommended",
                    "availability": "available",
                }
            ],
        },
        "approved_investigation_envelope": {"envelope_version": 1},
    }


def test_governed_draft_schema_rejects_send_authorization() -> None:
    with pytest.raises(ValidationError):
        GovernedEmailDraft(
            recipient_roles=["firewall_team"],
            subject="x",
            body="y",
            findings=["f"],
            evidence_refs=["ev.auth"],
            send_authorized=True,  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        GovernedEmailDraft(
            recipient_roles=["firewall_team"],
            subject="x",
            body="y",
            findings=["f"],
            evidence_refs=["ev.auth"],
            sent=True,  # type: ignore[arg-type]
        )


def test_draft_ready_without_hil_is_not_send_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    result = _apply_remediation_lifecycle(_conditional_state(predicate_satisfied=True))
    draft = result["email_draft"]
    assert draft["send_authorized"] is False
    assert draft["sent"] is False
    assert draft["recipient_resolution_required"] is True
    assert email_send_eligible(result) is False
    assert all(item["action_kind"] != "email_send" for item in
               result["resolved_query_contract"]["requested_conditional_actions"])
    assert "remediation_execution" not in result


def test_pending_condition_is_not_send_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    result = _apply_remediation_lifecycle(_conditional_state(predicate_satisfied=False))
    assert [(a["action_kind"], a["lifecycle_state"])
            for a in result["resolved_query_contract"]["requested_conditional_actions"]] == [
        ("email_draft", "PENDING_CONDITION")
    ]
    assert "email_draft" not in result
    assert email_send_eligible(result) is False


def test_eligible_without_approval_is_not_send_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    result = resolve_requested_conditional_actions(
        _conditional_state(predicate_satisfied=True)
    )
    assert result["resolved_query_contract"]["requested_conditional_actions"][0][
        "lifecycle_state"
    ] == "ELIGIBLE"
    assert email_send_eligible(result) is False


def test_remediation_plan_approve_does_not_authorize_draft_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remediation Approve ≠ Phase-10 GovernedEmailDraft send authorization."""
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_ALLOWLIST", "soc@example.com")
    state = _conditional_state(predicate_satisfied=True)
    state["investigation_outcome"]["action_eligibility"] = {
        "allowed_actions": ["email_send"],
        "unavailable_actions": [],
        "hil_required": True,
        "current_tier": 1,
    }
    state["resolved_query_contract"]["requested_conditional_actions"] = [
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
    offered = maybe_attach_remediation_offer(state)
    assert offered.get("email_draft") is not None
    assert offered["email_draft"]["send_authorized"] is False
    assert email_send_eligible(offered) is False

    approved = handle_remediation_review(offered, action="approve")
    envelope = ApprovedRemediationEnvelope.model_validate(
        approved["approved_remediation_envelope"]
    )
    assert "email_send" in envelope.executable_capability_ids()
    assert approved["email_draft"]["send_authorized"] is False
    assert approved["email_draft"]["sent"] is False
    assert email_send_eligible(approved) is False
    assert "remediation_execution" not in approved


def test_missing_recipient_resolution_and_unavailable_connector_block_send() -> None:
    adversarial = {
        "email_draft": {
            "send_authorized": False,
            "sent": False,
            "recipient_resolution_required": True,
        },
        "resolved_query_contract": {
            "requested_conditional_actions": [
                {
                    "action_kind": "email_send",
                    "lifecycle_state": "APPROVED",
                    "send_hil_approved": True,
                    "recipient_roles": ["firewall_team"],
                    # no resolved_recipients → fail closed; do not invent addresses
                    "connector_available": False,
                }
            ]
        },
    }
    assert email_send_eligible(adversarial) is False

    with_roles_only = {
        **adversarial,
        "resolved_query_contract": {
            "requested_conditional_actions": [
                {
                    "action_kind": "email_send",
                    "lifecycle_state": "APPROVED",
                    "send_hil_approved": True,
                    "resolved_recipients": ["firewall_team"],  # role id, not an address
                    "connector_available": True,
                }
            ]
        },
        "email_draft": {**adversarial["email_draft"], "send_authorized": True},
    }
    assert email_send_eligible(with_roles_only) is False


def test_llm_shaped_draft_cannot_transition_lifecycle_or_authorize_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    state = _conditional_state(predicate_satisfied=True)
    # Adversarial LLM-looking payload must not advance lifecycle or unlock send.
    state["email_draft"] = {
        "schema_version": "governed_email_draft_v1",
        "status": "draft_ready",
        "recipient_roles": ["firewall_team"],
        "recipient_resolution_required": True,
        "subject": "LLM invented subject",
        "body": "LLM invented body — please send now",
        "findings": ["x"],
        "evidence_refs": ["ev.auth"],
        "generation_source": "llm_unbounded",
        "llm_attempted": True,
        "llm_status": "succeeded",
        "send_authorized": False,
        "sent": False,
    }
    resolved = resolve_requested_conditional_actions(state)
    action = resolved["resolved_query_contract"]["requested_conditional_actions"][0]
    assert action["lifecycle_state"] == "ELIGIBLE"
    assert action["lifecycle_state"] not in {"APPROVED", "EXECUTED"}
    assert email_send_eligible(resolved) is False

    # Production builder still emits the governed deterministic draft flags.
    built = maybe_attach_remediation_offer(state)
    assert built["email_draft"]["generation_source"] == "deterministic_governed"
    assert built["email_draft"]["llm_attempted"] is False
    assert built["email_draft"]["send_authorized"] is False
    assert email_send_eligible(built) is False


def test_cv_multi_01a_send_absent_and_not_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)
    result = _apply_remediation_lifecycle(_conditional_state(predicate_satisfied=False))
    assert email_send_eligible(result) is False
    assert "email_draft" not in result
    assert all(
        item.get("action_kind") != "email_send"
        for item in result["resolved_query_contract"]["requested_conditional_actions"]
    )
