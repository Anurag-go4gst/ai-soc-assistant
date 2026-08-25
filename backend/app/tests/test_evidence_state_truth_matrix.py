"""P1 T2: EvidenceState contains accepted factual evidence only."""

from __future__ import annotations

import pytest

from app.chat.canonical_facts_spine import harvest_canonical_facts_from_state
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state


def _source(source_type: str, status: str, *, result_count: int = 0) -> dict:
    return {
        "evidence_id": f"{source_type}-{status}",
        "source_type": source_type,
        "source_name": "truth-matrix",
        "collection_status": status,
        "result_count": result_count,
        "preview_rows": [{"value": "accepted"}] if result_count else [],
    }


@pytest.mark.parametrize("status", ["planned", "requested", "attempted"])
def test_plan_only_never_becomes_obtained(status: str) -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[_source("splunk_mcp", status)],
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
        canonical_facts={
            "facts": [
                {
                    "kind": "plan_step_outcome",
                    "payload": {"status": status},
                    "provenance": {"node": "resource_plan", "evidence_class": "plan"},
                }
            ]
        },
    )
    assert state.obtained == []
    assert "mcp" in state.missing
    assert "plan_step_outcome" in state.diagnostic


def test_execution_metadata_only_never_becomes_obtained() -> None:
    state = derive_minimal_evidence_state(
        evidence_plan={"needs_spl": True, "needs_mcp": True, "mcp_allowed": True},
        execution={"status": "executed", "result_count": 10},
    )
    assert state.obtained == []
    assert set(state.missing) == {"spl", "mcp"}
    assert state.diagnostic == ["execution_status"]


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_failed_or_unavailable_source_never_becomes_obtained(status: str) -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[_source("splunk_mcp", status)],
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
    )
    assert "mcp" not in state.obtained
    assert "mcp" in state.missing


def test_empty_result_is_factual_empty_not_positive_evidence() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            {
                **_source("splunk_mcp", "collected"),
                "fields_returned": ["user"],
            }
        ],
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
    )
    assert state.obtained == []
    assert state.empty == ["mcp"]
    assert "mcp" in state.missing
    assert next(item for item in state.items if item.key == "mcp").status == "empty"


@pytest.mark.parametrize("source_type, expected", [("rag", "rag"), ("splunk_mcp", "mcp")])
def test_accepted_source_evidence_is_obtained(source_type: str, expected: str) -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[_source(source_type, "collected", result_count=1)]
    )
    assert state.obtained == [expected]
    assert next(item for item in state.items if item.key == expected).status == "obtained"


def test_mixed_accepted_and_failed_only_accepts_factual_source() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            _source("rag", "collected", result_count=1),
            _source("splunk_mcp", "failed"),
        ],
        evidence_plan={"needs_rag": True, "needs_mcp": True, "mcp_allowed": True},
    )
    assert state.obtained == ["rag"]
    assert "mcp" in state.missing


def test_skipped_rag_creates_no_citation_or_empty_negative_fact() -> None:
    facts = harvest_canonical_facts_from_state(
        {
            "soc_kb_retrieval": {
                "retrieval_status": "skipped",
                "rag_skipped_for_spl_utility_authoring": True,
                "citations": [],
            }
        }
    )
    assert "rag_citation" not in facts.kinds()
    assert "negative_evidence" not in facts.kinds()
