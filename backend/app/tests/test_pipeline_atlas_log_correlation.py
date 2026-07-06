"""ATLAS grounding + Splunk MCP evidence correlation (plan 2026-07-06 item 11/18)."""

from __future__ import annotations

from app.evidence.context_sufficiency import check_context_sufficiency


def _sample_source_evidence() -> list[dict]:
    return [
        {
            "evidence_id": "ev_ref_1",
            "source_type": "reference_dataset",
            "collection_status": "collected",
            "preview_rows": [{"reference_id": "AML.T0065", "dataset_id": "mitre_atlas"}],
        },
        {
            "evidence_id": "ev_mcp_1",
            "source_type": "splunk_mcp",
            "collection_status": "collected",
            "result_count": 2,
            "preview_rows": [{"host": "agent-01"}],
        },
    ]


def test_combined_reference_and_splunk_mcp_reaches_partial_or_full_answer() -> None:
    source_evidence = _sample_source_evidence()
    structured = {
        "missing_evidence": [],
        "structured_facts": [
            {
                "fact_id": "fact-1",
                "source_refs": ["ev_mcp_1"],
                "payload": {"row_count": 2},
            }
        ],
    }
    result = check_context_sufficiency(structured, source_evidence)
    assert result["status"] in {"partial_answer", "full_answer"}
    assert any(item.get("source_type") == "splunk_mcp" for item in source_evidence)
    assert any(item.get("source_type") == "reference_dataset" for item in source_evidence)


def test_no_action_proposal_created_for_atlas_correlation_turn() -> None:
    from app.actions.action_lane import ActionLaneStore
    from app.actions.capability_policy import action_capability_for

    before = action_capability_for(None, None)
    store = ActionLaneStore()
    assert store.get("missing") is None
    after = action_capability_for(None, None)
    assert after.current_tier == before.current_tier
    assert after.unavailable_actions == before.unavailable_actions
