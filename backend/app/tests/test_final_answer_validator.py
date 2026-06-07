"""Commit 4 — final-answer validator fails closed on contract conflicts.

One synthetic malformed answer per rule must be blocked and routed to analyst
review. A well-formed answer must pass.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.final_answer_validator import validate_final_answer


def _answer(**kwargs):
    base = {
        "mitre_mappings": [],
        "spl_code": None,
        "response_profile": None,
        "recommended_actions": [],
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _contract(**kwargs):
    base = {
        "answer_goal": ["mitre_mapping"],
        "answer_mode": "live_investigation",
        "mitre_answer_visible": True,
        "not_claimed_technique_ids": [],
    }
    base.update(kwargs)
    return base


def test_well_formed_answer_passes() -> None:
    result = validate_final_answer(
        analyst_response=_answer(mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate"}]),
        answer_contract=_contract(),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"registry_candidates": ["T1110.001"], "answer_visible": True},
    )
    assert result.guard_status == "passed"
    assert result.analyst_review_required is False


def test_blocked_finding_shown_as_claim_fails_closed() -> None:
    result = validate_final_answer(
        analyst_response=_answer(mitre_mappings=[{"Technique": "T1078", "Status": "Candidate"}]),
        answer_contract=_contract(not_claimed_technique_ids=["T1078"]),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"registry_candidates": ["T1078"], "answer_visible": True},
    )
    assert result.guard_status == "blocked"
    assert result.analyst_review_required is True
    assert "final.blocked_finding_claimed" in result.failed_checks


def test_mitre_visible_when_suppressed_blocks() -> None:
    result = validate_final_answer(
        analyst_response=_answer(mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate"}]),
        answer_contract=_contract(mitre_answer_visible=False),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"registry_candidates": ["T1110.001"], "answer_visible": False},
    )
    assert result.guard_status == "blocked"
    assert "final.mitre_visible_when_suppressed" in result.failed_checks


def test_rag_injected_technique_blocks() -> None:
    result = validate_final_answer(
        analyst_response=_answer(mitre_mappings=[{"Technique": "T1566", "Status": "Candidate"}]),
        answer_contract=_contract(),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"registry_candidates": ["T1110.001"], "answer_visible": True},
    )
    assert result.guard_status == "blocked"
    assert "final.rag_override_mitre" in result.failed_checks


def test_spl_on_rag_only_blocks() -> None:
    result = validate_final_answer(
        analyst_response=_answer(spl_code="index=x | stats count"),
        answer_contract=_contract(answer_mode="rag_only", mitre_answer_visible=False),
        evidence_plan={"answer_mode": "rag_only"},
        mitre_decision={},
    )
    assert result.guard_status == "blocked"
    assert "final.spl_on_rag_only" in result.failed_checks


def test_candidate_described_as_confirmed_blocks() -> None:
    result = validate_final_answer(
        analyst_response=_answer(mitre_mappings=[{"Technique": "T1110.001", "Status": "Confirmed"}]),
        answer_contract=_contract(),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={"registry_candidates": ["T1110.001"], "answer_visible": True},
    )
    assert result.guard_status == "blocked"
    assert "final.candidate_described_as_confirmed" in result.failed_checks


def test_spl_only_when_action_guidance_requested_blocks() -> None:
    result = validate_final_answer(
        analyst_response=_answer(spl_code="index=x", response_profile="spl_only", recommended_actions=[]),
        answer_contract=_contract(answer_goal=["analyst_action_guidance"], mitre_answer_visible=False),
        evidence_plan={"answer_mode": "live_investigation"},
        mitre_decision={},
    )
    assert result.guard_status == "blocked"
    assert "final.spl_only_missing_action_guidance" in result.failed_checks


def test_missing_inputs_skip() -> None:
    result = validate_final_answer(
        analyst_response=None,
        answer_contract=None,
        evidence_plan=None,
        mitre_decision=None,
    )
    assert result.guard_status == "skipped"
