"""P8 two-axis outcome, evidence binding, progress hygiene, and rollback tests."""

from __future__ import annotations

import json

from app.chat.contracts.investigation_outcome import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V2,
    apply_llm_outcome_proposal,
    derive_investigation_outcome,
)
from app.chat.investigation_run_compiler import attach_investigation_observation


def test_outcome_v2_lifecycle_off_keeps_legacy_envelope_unchanged() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED"},
        context_sufficiency={"status": "blocked_by_policy"},
    )
    payload = outcome.model_dump(mode="json")
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["disposition"] == "blocked"
    assert "investigation_status" not in payload


def test_blocked_investigation_is_not_a_security_disposition() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["authentication_correlation"]},
        context_sufficiency={"status": "blocked_by_policy", "reasons": ["connector unavailable"]},
        investigation_run_status={
            "status": "blocked",
            "stop_reason": "connector_unavailable",
            "next_action": "request_operator_readiness",
        },
        investigation_approval={"status": "approved"},
        outcome_v2_enabled=True,
    )
    assert outcome.schema_version == SCHEMA_VERSION_V2
    assert outcome.investigation_status == "blocked"
    assert outcome.disposition == "inconclusive"
    assert "blocked" not in type(outcome).model_json_schema()["properties"]["disposition"]["enum"]
    assert outcome.recommended_next_action == "request_operator_readiness"
    assert outcome.remediation_offer_required is True


def test_scenario_b_pattern_alone_remains_inconclusive() -> None:
    outcome = derive_investigation_outcome(
        evidence_state={"obtained": ["ssh_failure_pattern"], "missing": ["session_corroboration"]},
        evidence_sufficiency={"status": "PARTIAL", "missing": ["session_corroboration"]},
        canonical_facts={
            "facts": [
                {
                    "kind": "observed_pattern",
                    "statement": "25 failed SSH logins followed by one success",
                }
            ]
        },
        structured_context={
            "structured_facts": [
                {
                    "statement": "25 failed SSH logins followed by one success",
                    "source_refs": ["ev-ssh"],
                }
            ],
            "source_evidence_refs": ["ev-ssh"],
        },
        final_evidence_gate={
            "collected_evidence_refs": ["ev-ssh"],
            "allow_live_result_language": True,
        },
        severity_label="P3 Medium",
        investigation_run_status={"status": "incomplete", "next_action": "collect_session_corroboration"},
        outcome_v2_enabled=True,
    )
    assert outcome.investigation_status == "incomplete"
    assert outcome.disposition == "inconclusive"


def test_llm_cannot_upgrade_inconclusive_without_evidence_refs() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT"},
        investigation_run_status={"status": "incomplete"},
        outcome_v2_enabled=True,
    )
    updated = apply_llm_outcome_proposal(
        outcome,
        {
            "disposition": "suspicious",
            "findings": [{"text": "confirmed compromise"}],
            "hypotheses": [],
        },
    )
    assert updated.disposition == "inconclusive"
    assert updated.findings == []
    assert updated.llm_proposal_accepted is False


def test_cancelled_outcome_has_no_remediation_offer() -> None:
    outcome = derive_investigation_outcome(
        investigation_approval={"status": "cancelled"},
        outcome_v2_enabled=True,
    )
    assert outcome.investigation_status == "cancelled"
    assert outcome.disposition == "inconclusive"
    assert outcome.remediation_offer_required is False


def test_remediation_offer_skipped_when_final_rqc_already_requested_action() -> None:
    outcome = derive_investigation_outcome(
        investigation_run_status={"status": "completed"},
        resolved_query_contract={
            "normalized_goal": "Investigate the IP and contain it if malicious",
            "answer_goal": "live_results",
        },
        outcome_v2_enabled=True,
    )
    assert outcome.remediation_offer_required is False


def test_progress_is_operational_only_and_empty_completion_has_honest_copy() -> None:
    state = attach_investigation_observation(
        {
            "approved_investigation_envelope": {"envelope_version": 1},
            "evidence_plan": {
                "resource_plan": {
                    "steps": [
                        {
                            "step_id": "search-auth",
                            "purpose": "authentication_correlation",
                            "status": "executed",
                            "resource_id": "splunk_search",
                        }
                    ]
                }
            },
            "source_evidence": [],
            "evidence_sufficiency": {"status": "SUFFICIENT", "missing": []},
        }
    )
    progress = state["investigation_progress"]
    assert progress[0]["evidence_summary"] == "No matching governed evidence was found for this step."
    serialized = json.dumps(progress).lower()
    assert "finding: -" not in serialized
    for forbidden in ("chain_of_thought", "chain-of-thought", "hidden_reasoning", "scratchpad"):
        assert forbidden not in serialized
