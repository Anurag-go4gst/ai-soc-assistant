"""EvidencePlan planning snapshot vs final SPL projection drift."""

from __future__ import annotations

from app.spl.slot_constraint_projection import merge_evidence_plan_spl_drift


def test_drift_true_when_planning_and_final_differ() -> None:
    plan = {
        "normalized_slot_summary": {
            "planning_snapshot": True,
            "normalized_slots": {"index": "pgcil_soc"},
        },
        "slot_constraint_projection_summary": {
            "planning_snapshot": True,
            "normalized_slots": {"index": "pgcil_soc"},
        },
    }
    final = {
        "projection_id": "final-1",
        "normalized_slots": {"index": "wineventlog"},
        "semantic_constraints": [],
    }
    merged = merge_evidence_plan_spl_drift(plan, final)
    assert merged["handoff_drift_from_final_spl"] is True
    assert "normalized_slots.index" in merged["handoff_drift_details"]


def test_drift_false_when_aligned() -> None:
    slots = {"index": "scada_perf", "time_window": "earliest=-24h latest=now"}
    plan = {
        "normalized_slot_summary": {"planning_snapshot": True, "normalized_slots": slots},
        "slot_constraint_projection_summary": {"planning_snapshot": True, "normalized_slots": slots},
    }
    final = {"projection_id": "f", "normalized_slots": slots, "semantic_constraints": []}
    merged = merge_evidence_plan_spl_drift(plan, final)
    assert merged["handoff_drift_from_final_spl"] is False
