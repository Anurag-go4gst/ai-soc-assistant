"""Runtime RAG vs enrichment, and executed vs source evidence, on the reviewer timeline."""

from __future__ import annotations

import json
from pathlib import Path

from app.chat.debug_summary import build_debug_summary
from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace, compact_timeline_event

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"


def test_p2_reviewer_classifies_source_profile_lookup_as_enrichment() -> None:
    payload = json.loads(_FIXTURE.read_text())
    summary = build_debug_summary(payload=payload)
    forensic = assemble_forensic_bundle(
        trace_id="p2-rag",
        run={
            "metadata": {
                "debug_summary": {**summary, "effective_state": {"$ref": "run.metadata.effective_state"}},
                "effective_state": summary["effective_state"],
                "control_plane_trace": payload.get("control_plane_trace"),
            }
        },
        events=[
            {
                "kind": "rag_retrieval",
                "event": {
                    "evidence_origin": "stub_rag",
                    "retrieval_workflow_stage": "spl_source_resolve",
                    "status": "retrieved",
                    "result_count": 5,
                },
            }
        ],
    )
    reviewer = build_reviewer_trace(forensic)
    enrichment = reviewer["enrichment"]
    assert enrichment["runtime_rag_used"] is False
    assert enrichment["optional_enrichment_used"] is True
    assert enrichment["enrichment_type"] == "source_profile_hint"
    assert enrichment["enrichment_stage"] == "spl_source_resolve"
    assert enrichment["allowed_to_ground_final_analytic_answer"] is False
    event = reviewer["timeline"][0]["event"]
    assert event["runtime_rag"] is False
    assert event["enrichment"] is True
    assert event["purpose"] == "source_profile_hint"
    assert event["authoritative_for_live_findings"] is False
    assert event["evidence_origin"] == "stub_rag"


def test_executed_evidence_on_a_non_executed_turn_is_relabelled() -> None:
    classified = compact_timeline_event(
        {
            "kind": "step",
            "event": {
                "fact_kind": "executed_evidence",
                "evidence_class": "rag",
            },
        },
        effective={"execution": {"execution_performed": False}},
    )
    assert classified["event"]["legacy_fact_kind"] == "executed_evidence"
    assert classified["event"]["effective_fact_kind"] == "source_evidence"
    assert classified["event"]["live_execution"] is False


def test_canonical_facts_kinds_inventory_is_not_live_executed_evidence() -> None:
    """Live P2 stamps executed_evidence in kinds[], not fact_kind."""
    classified = compact_timeline_event(
        {
            "kind": "step",
            "event": {
                "step_name": "canonical_facts_snapshot",
                "kinds": ["entity", "executed_evidence", "mitre_decision", "negative_evidence"],
                "fact_count": 41,
            },
        },
        effective={"execution": {"execution_performed": False}},
    )
    assert classified["event"]["legacy_fact_kind"] == "executed_evidence"
    assert classified["event"]["effective_fact_kind"] == "source_evidence"
    assert classified["event"]["live_execution"] is False


def test_finalize_step_name_on_inner_body_rewrites_legacy_hil() -> None:
    """Live finalize events put step_name on the body; envelope step_name is null."""
    classified = compact_timeline_event(
        {
            "kind": "step",
            "step_name": None,
            "event": {
                "status": "human_review",
                "step_name": "node.finalize_response",
                "answer_mode": "spl_utility_authoring",
                "hil_required": True,
                "message_preview": "Review-only SPL draft",
            },
        },
        effective={"hil": {"current_turn_hil_required": False}},
    )
    assert classified["step_name"] == "node.finalize_response"
    assert classified["event"]["hil_required_legacy"] is True
    assert classified["event"]["current_turn_hil_required"] is False
    assert "hil_required" not in classified["event"]
    assert classified["event"]["final_answer_ref"] == "artifact:final_answer"
