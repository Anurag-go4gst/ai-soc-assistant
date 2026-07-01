"""Commit 1 — general negative-evidence engine and MITRE candidate demotion.

Proves the per-use-case `_not_claimed_for_context` hardcoding is replaced by a
tactic-general precondition rule: a candidate technique lacking its required
evidence is demoted from visible to Not Claimed, for auth and non-auth alike.
"""

from __future__ import annotations

from app.chat.negative_evidence_extractor import (
    extract_negative_evidence,
    present_evidence_keys,
)
from app.threat.mitre_evidence_preconditions import (
    not_claimed_reason,
    precondition_negated,
)
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_schema import MitreRegistryMetadata


def _meta(*, candidate: list[str], blocked: list[str]) -> MitreRegistryMetadata:
    return MitreRegistryMetadata(
        mitre_permitted=[],
        mitre_candidate=candidate,
        mitre_blocked=blocked,
    )


def _intent() -> dict[str, object]:
    return {
        "intent_family": "mitre_mapping",
        "answer_goal": ["mitre_mapping"],
        "requires_clarification": False,
    }


# --- extractor -------------------------------------------------------------


def test_failed_login_only_marks_no_successful_login_present() -> None:
    neg = extract_negative_evidence(query_signals={"failed_login": True})
    present = present_evidence_keys(neg)
    assert "failed_login_pattern" in present
    assert "successful_login" not in present


def test_success_after_failure_marks_successful_login_present() -> None:
    neg = extract_negative_evidence(
        query_signals={"failed_login": True, "positive_successful_login": True, "success_after_failure": True}
    )
    assert "successful_login" in present_evidence_keys(neg)


def test_explicit_negation_overrides_weak_presence() -> None:
    neg = extract_negative_evidence(
        query_signals={"positive_successful_login": True, "negative_successful_login": True}
    )
    assert "successful_login" not in present_evidence_keys(neg)
    assert "successful_login" in neg["explicit_negations"]


def test_rag_prohibited_conclusions_collected() -> None:
    neg = extract_negative_evidence(
        query_signals=None,
        source_evidence=[
            {"source_type": "rag", "prohibited_conclusions": ["valid account abuse confirmed"]},
            {"source_type": "splunk", "prohibited_conclusions": ["ignored non-rag"]},
        ],
        structured_context={"prohibited_conclusions": ["account takeover confirmed"]},
    )
    assert "account takeover confirmed" in neg["rag_prohibited_conclusions"]
    assert "valid account abuse confirmed" in neg["rag_prohibited_conclusions"]
    assert "ignored non-rag" not in neg["rag_prohibited_conclusions"]


# --- precondition table ----------------------------------------------------


def test_precondition_negated_for_absent_evidence() -> None:
    assert precondition_negated("T1078", set()) is True
    assert precondition_negated("T1078", {"successful_login"}) is False
    # technique with no precondition entry is never demoted by this rule
    assert precondition_negated("T1110.001", set()) is False
    assert precondition_negated("T1190", set()) is True
    assert precondition_negated("T1190", {"initial_access_evidence"}) is False
    assert "outbound" in not_claimed_reason("T1041").lower()


# --- MITRE decision parity (auth) ------------------------------------------


def test_failed_login_blocked_techniques_drive_not_claimed_rows() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_meta(candidate=["T1110.001"], blocked=["T1562.001", "T1003", "T1078"]),
        intent_classification=_intent(),
        evidence_plan={"answer_mode": "live_investigation"},
        negative_evidence=extract_negative_evidence(query_signals={"failed_login": True}),
    )
    visible = {item["technique_id"] for item in decision.techniques}
    assert visible == {"T1110.001"}
    assert set(decision.rejected_techniques) == {"T1562.001", "T1003", "T1078"}


def test_success_after_failure_keeps_t1078_visible() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_meta(candidate=["T1110.001", "T1078"], blocked=["T1562.001", "T1003"]),
        intent_classification=_intent(),
        evidence_plan={"answer_mode": "live_investigation"},
        negative_evidence=extract_negative_evidence(
            query_signals={"failed_login": True, "positive_successful_login": True, "success_after_failure": True}
        ),
    )
    visible = {item["technique_id"] for item in decision.techniques}
    assert visible == {"T1110.001", "T1078"}
    assert "T1078" not in decision.not_claimed
    assert set(decision.rejected_techniques) == {"T1562.001", "T1003"}


# --- generalization beyond auth (the whole point) --------------------------


def test_candidate_without_evidence_is_demoted_not_claimed() -> None:
    """T1078 is a candidate but evidence (successful login) is absent -> Not Claimed.

    No use_case_id literal: the same rule that governs auth governs any tactic.
    """
    decision = resolve_mitre_decision(
        registry_metadata=_meta(candidate=["T1110.001", "T1078"], blocked=[]),
        intent_classification=_intent(),
        evidence_plan={"answer_mode": "live_investigation"},
        negative_evidence=extract_negative_evidence(query_signals={"failed_login": True}),
    )
    visible = {item["technique_id"] for item in decision.techniques}
    assert visible == {"T1110.001"}
    assert "T1078" in decision.not_claimed  # demoted by absent successful_login
    assert "T1078" not in decision.rejected_techniques  # not registry-blocked


def test_t1048_and_t1071_004_preconditions_present_and_negate():
    """WS-C: the two candidate-tier bundle adds have data-driven preconditions.

    Both are evidence-negated when their required positive evidence is absent, and
    cleared once it is present — same pattern as the parent/sibling techniques.
    """
    from app.threat.mitre_evidence_preconditions import (
        PRECONDITION_BY_ID,
        not_claimed_reason,
        precondition_negated,
    )

    assert {"T1048", "T1071.004"} <= set(PRECONDITION_BY_ID)
    # Negated with no evidence; cleared with the established positive-evidence key.
    assert precondition_negated("T1048", set()) is True
    assert precondition_negated("T1048", {"outbound_transfer"}) is False
    assert precondition_negated("T1071.004", set()) is True
    assert precondition_negated("T1071.004", {"network_telemetry"}) is False
    assert "alternative protocol" in not_claimed_reason("T1048")
    assert "DNS" in not_claimed_reason("T1071.004")
