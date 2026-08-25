"""P5 — workflow control vocabulary must not read as containment advice."""

from __future__ import annotations

from app.chat.contracts.investigation_outcome import derive_investigation_outcome


def _investigation_rqc(**overrides: object) -> dict:
    base = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "required_capabilities": ["spl", "mcp"],
        "understanding_source": "deterministic_qualification",
    }
    base.update(overrides)
    return base


def test_blocked_sufficiency_maps_block_to_process_language() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "missing": ["mcp_rows"], "next_action": "BLOCK"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    assert outcome.recommended_next_action == "Unable to proceed — additional evidence required"
    assert outcome.recommended_next_action != "BLOCK"


def test_run_status_block_precedence_maps_to_process_language() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "PARTIAL", "next_action": "CONTINUE"},
        investigation_run_status={"status": "blocked", "next_action": "BLOCK"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    assert outcome.recommended_next_action == "Unable to proceed — additional evidence required"


def test_degrade_and_clarify_map_to_process_language() -> None:
    degraded = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT", "next_action": "DEGRADE"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    clarified = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT", "next_action": "CLARIFY"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    assert degraded.recommended_next_action == "Continue with available evidence"
    assert clarified.recommended_next_action == "Clarification required"


def test_non_control_next_action_preserved() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "next_action": "request_operator_readiness"},
        investigation_run_status={"status": "blocked", "next_action": "request_operator_readiness"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        outcome_v2_enabled=True,
    )
    assert outcome.recommended_next_action == "request_operator_readiness"


def test_spl_authoring_still_suppresses_investigation_outcome_v2() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "next_action": "BLOCK"},
        resolved_query_contract={
            "intent_family": "spl_generation_only",
            "answer_goal": "spl_artifact",
            "required_capabilities": ["spl"],
        },
        outcome_v2_enabled=True,
    )
    payload = outcome.model_dump(mode="json")
    assert "investigation_status" not in payload
    assert payload.get("recommended_next_action") is None
