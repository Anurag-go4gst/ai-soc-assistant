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


def test_drift_merge_keeps_planning_and_final_summaries_separate() -> None:
    plan = {
        "slot_constraint_projection_summary": {
            "planning_snapshot": True,
            "normalized_slots": {"index": "pgcil_soc"},
            "projection_id": "plan-1",
        },
    }
    final = {
        "projection_id": "final-1",
        "normalized_slots": {"index": "wineventlog"},
        "semantic_constraints": [],
    }
    merged = merge_evidence_plan_spl_drift(plan, final)
    planning = merged["slot_constraint_projection_summary"]
    assert planning.get("planning_snapshot") is True
    assert planning.get("normalized_slots") == {"index": "pgcil_soc"}
    assert "drift_from_final_spl" not in planning
    final_summary = merged["final_spl_projection_summary"]
    assert final_summary.get("planning_snapshot") is False
    assert final_summary.get("normalized_slots") == {"index": "wineventlog"}
    handoff = merged["slot_handoff_summary"]
    assert handoff["drift_from_final_spl"] is True
    assert handoff["planning_snapshot"]["projection_id"] == "plan-1"
    assert handoff["final_spl_projection"]["projection_id"] == "final-1"
