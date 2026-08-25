"""Plan 8 D0 — EVIDENCE sufficiency compares final RQC to E0A EvidenceState."""

from __future__ import annotations

from app.chat.contracts.staged_sufficiency import from_evidence_state
from app.evidence.evidence_sufficiency import attach_evidence_sufficiency
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state
from app.graph.resource_planner_graph import rp_node_context_sufficiency
from app.schemas.requests import ChatRequest


def test_node_never_emits_pending_finalize() -> None:
    state = rp_node_context_sufficiency({"request": ChatRequest(message="what is MITRE T1059?")})
    sufficiency = state.get("context_sufficiency") or {}
    staged = state.get("evidence_sufficiency") or {}
    assert sufficiency.get("status") != "pending_finalize"
    assert staged.get("status") in {"SUFFICIENT", "PARTIAL", "INSUFFICIENT", "BLOCKED"}
    assert staged.get("stage") == "EVIDENCE"
    assert staged.get("next_action") != "CALL_T4"


def test_sufficient_when_required_evidence_is_obtained() -> None:
    evidence = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "ev1",
                "source_type": "splunk_mcp",
                "source_name": "splunk_soc",
                "collection_status": "collected",
                "result_count": 1,
                "fields_returned": ["user"],
            }
        ],
        resolved_query_contract={"evidence_requirements": ["user"], "required_capabilities": ["mcp"]},
        evidence_plan={"required_evidence_keys": ["user"], "needs_mcp": True, "mcp_allowed": True},
    )
    result = from_evidence_state(
        evidence,
        resolved_query_contract={"evidence_requirements": ["user"], "required_capabilities": ["mcp"]},
    )
    assert result.status == "SUFFICIENT"
    assert result.next_action == "CONTINUE"
    assert result.missing == []


def test_partial_and_insufficient_and_blocked() -> None:
    partial = from_evidence_state(
        {
            "required": ["user", "host"],
            "obtained": ["user"],
            "missing": ["host"],
            "stale": [],
            "invalidated": [],
            "blocked": [],
        }
    )
    assert partial.status == "PARTIAL"
    assert partial.next_action == "CONTINUE"
    assert "host" in partial.missing

    insufficient = from_evidence_state(
        {
            "required": ["user"],
            "obtained": [],
            "missing": ["user"],
            "stale": [],
            "invalidated": [],
            "blocked": [],
        }
    )
    assert insufficient.status == "INSUFFICIENT"
    assert insufficient.next_action == "DEGRADE"

    blocked = from_evidence_state(
        {
            "required": ["mcp"],
            "obtained": [],
            "missing": ["mcp"],
            "stale": [],
            "invalidated": [],
            "blocked": ["mcp"],
        }
    )
    assert blocked.status == "BLOCKED"
    assert blocked.next_action == "BLOCK"


def test_attach_preserves_stage3j_envelope() -> None:
    updated = attach_evidence_sufficiency(
        {
            "context_sufficiency": {
                "status": "knowledge_only_answer",
                "synthesis_allowed": False,
                "synthesis_readiness": True,
                "reasons": ["policy_context_required"],
                "missing_evidence": [],
            },
            "resolved_query_contract": {"evidence_requirements": []},
        }
    )
    assert updated["context_sufficiency"]["status"] == "knowledge_only_answer"
    assert updated["evidence_sufficiency"]["status"] in {"SUFFICIENT", "PARTIAL", "INSUFFICIENT", "BLOCKED"}
    assert updated["evidence_sufficiency"]["next_action"] != "CALL_T4"
    assert "pending_finalize" not in str(updated["evidence_sufficiency"])
