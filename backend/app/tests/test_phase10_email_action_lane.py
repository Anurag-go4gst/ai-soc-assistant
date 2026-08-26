"""Post-P10 3.4 — email draft is Phase 10 data, never a ResourcePlan/send step."""

from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.pipeline import _apply_remediation_lifecycle
from app.config import settings
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import resource_plan_authority


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
            "action_eligibility": {"allowed_actions": [], "unavailable_actions": []},
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
    }


def test_cv_multi_01b_plans_draft_on_phase10_without_planning_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Email drafting is not coupled to the optional remediation reasoning role.
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)

    result = _apply_remediation_lifecycle(_conditional_state(predicate_satisfied=True))

    actions = result["resolved_query_contract"]["requested_conditional_actions"]
    assert [(item["action_kind"], item["lifecycle_state"]) for item in actions] == [
        ("email_draft", "ELIGIBLE")
    ]
    assert all(item["action_kind"] != "email_send" for item in actions)
    assert "remediation_approval" not in result
    assert "approved_remediation_envelope" not in result
    assert "remediation_execution" not in result


def test_cv_multi_01a_unmet_predicate_does_not_plan_draft_or_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", False)

    result = _apply_remediation_lifecycle(_conditional_state(predicate_satisfied=False))

    actions = result["resolved_query_contract"]["requested_conditional_actions"]
    assert [(item["action_kind"], item["lifecycle_state"]) for item in actions] == [
        ("email_draft", "PENDING_CONDITION")
    ]
    assert "remediation_approval" not in result
    assert "remediation_execution" not in result


def test_resource_plan_contains_investigation_resources_not_email_actions() -> None:
    evidence_plan = EvidencePlan(
        answer_mode="hybrid",
        rag_phase="pre_mcp",
        needs_rag=True,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
    )
    with resource_plan_authority("test"):
        plan = compose_resource_plan(
            evidence_plan,
            intent_family="hybrid_investigation_plus_policy",
        )

    step_tokens = {
        token
        for step in plan.steps
        for token in (step.step_id, step.resource_id, step.purpose)
    }
    assert "email_draft" not in step_tokens
    assert "email_send" not in step_tokens
    assert all(not step.resource_id.startswith("action:") for step in plan.steps)
