"""Post-P10 3.2 — J7 evidence authority pins for the convergence bank."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.remediation_runtime import (
    handle_remediation_review,
    maybe_attach_remediation_offer,
    remediation_offer_cta_eligible,
)
from app.config import settings

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _ROOT / "docs" / "evals" / "answer_shape" / "fixtures"


@pytest.fixture(autouse=True)
def _enable_remediation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)


def _fixture(row_id: str) -> dict:
    name = "cv_multi_01a_outcome.json" if row_id == "CV.MULTI.01A" else "cv_multi_01b_outcome.json"
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _investigation_rqc() -> dict:
    return {
        "intent_family": "hybrid_investigation_plus_policy",
        "answer_goal": "analyst_action_guidance",
        "required_capabilities": ["spl", "mcp"],
        "requested_conditional_actions": [
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
        ],
    }


def test_cv_multi_01a_inconclusive_has_no_remediation_plan() -> None:
    outcome = _fixture("CV.MULTI.01A")["investigation_outcome"]
    state = {
        "investigation_outcome": outcome,
        "resolved_query_contract": _investigation_rqc(),
        "context_sufficiency": {"answer_mode": "insufficient_evidence"},
    }

    result = maybe_attach_remediation_offer(state)

    assert outcome["investigation_status"] == "incomplete"
    assert outcome["disposition"] == "inconclusive"
    assert "remediation_approval" not in result
    assert "approved_remediation_envelope" not in result
    assert result["resolved_query_contract"]["requested_conditional_actions"][0][
        "lifecycle_state"
    ] == "PENDING_CONDITION"


def test_cv_sop_01_knowledge_contract_has_no_remediation_plan() -> None:
    malformed_outcome = {
        **_fixture("CV.MULTI.01B")["investigation_outcome"],
        "remediation_offer_required": True,
    }
    state = {
        "investigation_outcome": malformed_outcome,
        "resolved_query_contract": {
            "intent_family": "knowledge_only",
            "answer_goal": "policy_citation",
            "required_capabilities": [],
        },
        "context_sufficiency": {"answer_mode": "knowledge_only_answer"},
    }

    assert remediation_offer_cta_eligible(state) is False
    assert "remediation_approval" not in maybe_attach_remediation_offer(state)


def test_cv_multi_01b_plan_may_present_without_compromise_claim_or_write() -> None:
    outcome = {
        **_fixture("CV.MULTI.01B")["investigation_outcome"],
        # Isolate REMEDIATION PLAN ELIGIBILITY. A pre-requested action follows the
        # no-re-ask path wired in 3.3; it must not weaken this evidence gate.
        "remediation_offer_required": True,
    }
    state = {
        "investigation_outcome": outcome,
        "resolved_query_contract": _investigation_rqc(),
        "context_sufficiency": {"answer_mode": "rag_plus_live"},
        "capability_snapshot": None,
    }

    assert remediation_offer_cta_eligible(state) is True
    offered = maybe_attach_remediation_offer(state)
    planned = handle_remediation_review(
        offered,
        action="create",
        raw_output_provider=lambda: "{}",
    )

    assert planned["remediation_approval"]["status"] == "awaiting_approval"
    assert planned["remediation_approval"]["validated_plan"] is not None
    assert "approved_remediation_envelope" not in planned
    assert "remediation_execution" not in planned
    assert planned["resolved_query_contract"]["requested_conditional_actions"][1][
        "lifecycle_state"
    ] == "PENDING_CONDITION"
    blob = json.dumps(planned).lower()
    assert '"compromise_confirmed": true' not in blob
    assert '"execution_authorized": true' not in blob
