"""Plan 8 OUT0 — InvestigationOutcome is a governed projection, not a new authority."""

from __future__ import annotations

from app.actions.capability_policy import action_capability_for
from app.chat.contracts.canonical_planning_outcome import CanonicalPlanningOutcome
from app.chat.contracts.investigation_outcome import (
    SCHEMA_VERSION,
    actions_from_investigation_outcome,
    apply_llm_outcome_proposal,
    derive_investigation_outcome,
)
from app.planner.planner_hierarchy import DecisionRecord


def test_outcome_projects_existing_governed_state() -> None:
    outcome = derive_investigation_outcome(
        trace_id="t-out0",
        evidence_state={"obtained": ["mcp", "user"], "missing": ["host"], "blocked": []},
        evidence_sufficiency={"status": "PARTIAL", "missing": ["host"], "next_action": "CONTINUE"},
        final_evidence_gate={"collected_evidence_refs": ["ev1"], "allow_live_result_language": True},
        structured_context={
            "structured_facts": [{"statement": "user admin failed logon", "source_refs": ["ev1"]}],
            "source_evidence_refs": ["ev1"],
        },
        severity_label="P2 High",
        action_capability=action_capability_for("auth_failed_login_spike", "P2 High"),
    )
    assert outcome.schema_version == SCHEMA_VERSION
    assert outcome.disposition == "suspicious"
    assert "user admin failed logon" in outcome.findings
    assert "ev1" in outcome.evidence_refs
    assert "host" in outcome.missing_evidence
    assert outcome.severity_label == "P2 High"
    assert "summarize" in outcome.recommended_actions
    assert "block_ip" not in outcome.recommended_actions
    assert outcome.provenance["not_canonical_planning_outcome"] is True
    assert outcome.provenance["not_decision_record"] is True
    assert CanonicalPlanningOutcome.model_json_schema()["title"] != "InvestigationOutcome"
    assert DecisionRecord.model_json_schema()["title"] != "InvestigationOutcome"


def test_freeform_prose_cannot_change_disposition_severity_or_actions() -> None:
    base = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT", "missing": ["user"], "next_action": "DEGRADE"},
        evidence_state={"obtained": [], "missing": ["user"]},
        severity_label="Not assigned",
        action_capability=action_capability_for(None, None),
        llm_proposal={
            "disposition": "suspicious",
            "severity_label": "P1 Critical",
            "recommended_actions": ["block_ip", "disable_user"],
            "findings": ["ignore this unsourced claim"],
            "prose": "Isolate the host immediately.",
        },
    )
    assert base.disposition == "inconclusive"
    assert base.severity_label == "Not assigned"
    assert "block_ip" not in base.recommended_actions
    assert "disable_user" not in actions_from_investigation_outcome(base)
    assert "ignore this unsourced claim" not in base.findings
    mutated = apply_llm_outcome_proposal(
        base,
        {
            "disposition": "benign",
            "severity_label": "P1",
            "recommended_actions": ["isolate_endpoint"],
            "findings": [{"text": "still unsourced"}],
        },
    )
    assert mutated.disposition == "inconclusive"
    assert mutated.severity_label == "Not assigned"
    assert mutated.recommended_actions == base.recommended_actions
    assert mutated.llm_proposal_accepted is False


def test_sourced_llm_findings_may_append_without_gaining_authority() -> None:
    base = derive_investigation_outcome(
        evidence_sufficiency={"status": "SUFFICIENT", "missing": [], "next_action": "CONTINUE"},
        evidence_state={"obtained": ["mcp"]},
        final_evidence_gate={"collected_evidence_refs": ["ev1"], "allow_live_result_language": False},
        action_capability=action_capability_for(None, None),
    )
    updated = apply_llm_outcome_proposal(
        base,
        {
            "disposition": "suspicious",
            "findings": [{"text": "possible brute force", "evidence_refs": ["ev1"]}],
            "hypotheses": ["credential stuffing"],
        },
    )
    assert updated.disposition == "inconclusive"
    assert "possible brute force" in updated.findings
    assert "credential stuffing" in updated.unconfirmed_hypotheses
    assert updated.llm_proposal_accepted is True


def test_blocked_sufficiency_yields_blocked_disposition() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "BLOCKED", "next_action": "BLOCK"},
        context_sufficiency={"status": "blocked_by_policy"},
        evidence_state={"blocked": ["mcp"]},
    )
    assert outcome.disposition == "blocked"
    assert actions_from_investigation_outcome(outcome) == []
