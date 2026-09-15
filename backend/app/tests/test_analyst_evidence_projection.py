"""Hypothesis continuity and analyst-safe missing-evidence language.

P1-A: competing hypotheses existed upstream but InvestigationOutcome reported
none. P1-B: internal control keys (rag/spl/mcp/collected_source_evidence) leaked
into analyst-visible evidence gaps, and one requirement appeared under several
names (auth / authentication / authentication logs).
"""

from __future__ import annotations

from app.chat.analyst_missing_evidence import (
    SOURCE_UNAVAILABLE_LIMITATION,
    analyst_limitations,
    project_missing_evidence,
)
from app.chat.contracts.investigation_outcome import derive_investigation_outcome

INTERNAL_KEYS = ["rag", "rag:sop", "spl", "mcp", "mcp:splunk", "collected_source_evidence"]


def test_internal_control_keys_are_not_analyst_evidence_gaps() -> None:
    concepts, source_unavailable = project_missing_evidence(INTERNAL_KEYS)
    assert concepts == []
    assert source_unavailable is True


def test_unavailable_source_reads_as_a_source_limitation_not_missing_mcp() -> None:
    concepts, source_unavailable = project_missing_evidence(["mcp"])
    lines = analyst_limitations(concepts, source_unavailable=source_unavailable)
    assert lines == [SOURCE_UNAVAILABLE_LIMITATION]
    assert not any("mcp" in line.lower() for line in lines)


def test_spl_gap_visible_only_when_an_spl_artifact_was_requested() -> None:
    hidden, _ = project_missing_evidence(["spl"])
    shown, _ = project_missing_evidence(["spl"], spl_requested=True)
    assert hidden == []
    assert shown == ["a validated SPL artifact"]


def test_rag_gap_visible_only_under_a_knowledge_contract() -> None:
    hidden, _ = project_missing_evidence(["rag:sop"])
    shown, _ = project_missing_evidence(["rag:sop"], knowledge_contract_required=True)
    assert hidden == []
    assert shown == ["approved knowledge / SOP guidance"]


def test_one_requirement_is_named_once() -> None:
    concepts, _ = project_missing_evidence(
        ["auth", "authentication", "authentication logs", "endpoint", "process_execution"]
    )
    assert concepts == ["authentication evidence", "process and endpoint evidence"]


def test_analytically_distinct_requirements_stay_distinct() -> None:
    concepts, _ = project_missing_evidence(["auth", "identity", "privilege"])
    assert concepts == [
        "authentication evidence",
        "identity context",
        "authorization / privilege-change evidence",
    ]


def test_field_level_requirements_are_not_collapsed() -> None:
    """parent_process/command_line are specific and must survive verbatim."""
    concepts, _ = project_missing_evidence(["parent_process", "command_line"])
    assert concepts == ["parent_process", "command_line"]


def test_real_evidence_gaps_are_never_hidden() -> None:
    concepts, _ = project_missing_evidence(
        ["auth", "endpoint", "network_flows", "mcp", "rag", "spl"]
    )
    assert concepts == [
        "authentication evidence",
        "process and endpoint evidence",
        "network connection records",
    ]


def _outcome(**kwargs):
    return derive_investigation_outcome(
        trace_id="t",
        evidence_state=kwargs.get("evidence_state") or {},
        evidence_sufficiency={"status": "insufficient", "missing": kwargs.get("missing") or []},
        structured_context=kwargs.get("structured_context") or {},
        investigation_plan={"hypotheses": kwargs.get("hypotheses") or []},
        resolved_query_contract={"intent_family": "guided_investigation"},
    )


def test_hypotheses_reach_the_outcome_as_unconfirmed_without_evidence() -> None:
    outcome = _outcome(hypotheses=["legitimate administration", "malicious persistence"])
    assert outcome.supported_hypotheses == []
    assert outcome.unconfirmed_hypotheses == [
        "legitimate administration",
        "malicious persistence",
    ]


def test_hypothesis_is_not_supported_merely_because_it_was_proposed() -> None:
    """No admitted environment evidence -> nothing is supported."""
    outcome = _outcome(
        hypotheses=["malicious persistence"],
        evidence_state={"obtained": ["rag", "spl", "mcp"]},
    )
    assert outcome.supported_hypotheses == []
    assert outcome.unconfirmed_hypotheses == ["malicious persistence"]


def test_support_requires_admitted_environment_evidence_and_a_grounded_finding() -> None:
    outcome = _outcome(
        hypotheses=["malicious persistence", "legitimate administration"],
        evidence_state={"obtained": ["endpoint", "persistence"]},
        structured_context={
            "structured_facts": [
                {"statement": "malicious persistence observed on the host", "source_refs": ["ev1"]}
            ]
        },
    )
    assert outcome.supported_hypotheses == ["malicious persistence"]
    assert outcome.unconfirmed_hypotheses == ["legitimate administration"]


def test_no_hypotheses_upstream_means_no_invented_hypotheses() -> None:
    outcome = _outcome(hypotheses=[])
    assert outcome.supported_hypotheses == []
    assert outcome.unconfirmed_hypotheses == []
