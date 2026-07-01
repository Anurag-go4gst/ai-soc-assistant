"""S4 — MITRE evidence precondition expansion beyond pilots."""

from __future__ import annotations

from app.threat.mitre_evidence_preconditions import (
    evaluate_pilot_mitre_evidence_status,
    get_precondition,
    precondition_negated,
)


def test_expanded_preconditions_registered() -> None:
    for tid in ("T1190", "T1046"):
        assert get_precondition(tid) is not None


def test_pilot_techniques_preserve_candidate_without_pilot_evidence() -> None:
    result = evaluate_pilot_mitre_evidence_status(
        use_case_id="edr_powershell_suspicious_command",
        technique_id="T1059.001",
        present_evidence=set(),
    )
    assert result["status"] == "candidate"


def test_spray_breadth_pilot_preserves_candidate_without_evidence() -> None:
    result = evaluate_pilot_mitre_evidence_status(
        use_case_id="auth_failed_login_spike",
        technique_id="T1110.003",
        present_evidence=set(),
    )
    assert result["status"] == "candidate"


def test_missing_evidence_not_claimed_for_extended_precondition() -> None:
    assert precondition_negated("T1190", set()) is True
    assert precondition_negated("T1190", {"initial_access_evidence"}) is False


def test_non_pilot_unclear_case_fails_closed() -> None:
    result = evaluate_pilot_mitre_evidence_status(
        use_case_id="unknown_use_case",
        technique_id="T1190",
        present_evidence=set(),
    )
    assert result["status"] in {"candidate", "not_claimed", "requires_validation"}
