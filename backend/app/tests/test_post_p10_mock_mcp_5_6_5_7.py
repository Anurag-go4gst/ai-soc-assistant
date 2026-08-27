"""Phase 5.6 / 5.7 — mock labelling + no write authority from mock evidence."""

from __future__ import annotations

from app.chat.contracts.answer_contract import _execution_label
from app.chat.remediation_runtime import email_send_eligible, resolve_requested_conditional_actions
from app.evidence.source_evidence import build_source_evidence


def test_mock_connector_origin_is_labelled_simulated_not_live() -> None:
    label, display = _execution_label(
        execution_payload={
            "status": "executed",
            "evidence_source": "mock",
            "mode": "mock",
            "execution": "simulated",
            "splunk_result_envelope": {"origin": "mock_connector"},
        },
        spl_present=True,
        spl_approved=True,
        mcp_allowed=True,
        human_review_required=False,
    )
    assert label == "executed_mock_evidence"
    assert display and "mock" in display.lower()
    assert "live evidence" not in (display or "").lower()


def test_mock_source_evidence_uses_simulated_provenance() -> None:
    items = build_source_evidence(
        trace_id="mock-ev",
        query="hunt",
        selected_skill="attack_discovery",
        spl_validation={
            "approved": True,
            "normalized_spl": "search index=pgcil_soc | head 10",
            "warnings": [],
        },
        execution={
            "status": "executed",
            "evidence_source": "mock",
            "mode": "mock",
            "execution": "simulated",
            "selected_mcp_server": "splunk_soc",
            "selected_mcp_tool": "splunk_run_query",
            "executed_spl": "search index=pgcil_soc | head 10",
            "result_count": 1,
            "results_preview": [{"user": "admin"}],
            "splunk_result_envelope": {"origin": "mock_connector"},
        },
    )
    assert items
    assert items[0]["provenance"] == "ai_soc_simulated_mock_mcp"
    assert "simulated_mock_evidence_not_live_splunk" in (items[0].get("warnings") or [])


def test_mock_evidence_cannot_satisfy_compromise_or_authorize_email_send() -> None:
    state = {
        "investigation_outcome": {
            "schema_version": "investigation_outcome_v2",
            "investigation_status": "completed",
            "disposition": "suspicious",
            "evidence_refs": ["ev.mock"],
            "findings": ["mock row"],
            "remediation_offer_required": False,
        },
        "resolved_query_contract": {
            "requested_conditional_actions": [
                {
                    "action_kind": "email_draft",
                    "lifecycle_state": "PENDING_CONDITION",
                    "predicate_id": "account_compromise_confirmed",
                    "recipient_roles": ["firewall_team"],
                }
            ]
        },
        "evidence_state": {
            "obtained": ["account_compromise_confirmed"],
            "items": [
                {
                    "key": "account_compromise_confirmed",
                    "status": "obtained",
                    "provenance": "ai_soc_simulated_mock_mcp",
                    "scope": {
                        "simulated": True,
                        "predicate_id": "account_compromise_confirmed",
                        "predicate_value": True,
                        "evidence_refs": ["ev.mock"],
                    },
                }
            ],
        },
        "final_evidence_gate": {
            "allow_environment_fact_claims": True,
            "environment_evidence_count": 1,
            "source_evidence_status": "collected",
        },
        "email_draft": {"send_authorized": False, "sent": False},
    }
    resolved = resolve_requested_conditional_actions(state)
    action = resolved["resolved_query_contract"]["requested_conditional_actions"][0]
    assert action["lifecycle_state"] == "PENDING_CONDITION"
    assert email_send_eligible(resolved) is False
    assert "live_mcp_proven" not in str(resolved).lower()
