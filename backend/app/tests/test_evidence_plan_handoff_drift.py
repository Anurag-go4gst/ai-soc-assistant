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


from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
import pytest


_SCADA_DRIFT_QUERY = (
    "Provide a complete review-only SPL query for index=scada_perf using earliest=-30d to "
    "compute an eventstats stdev baseline by rtu_id and filter anomalies in the last 24h "
    "using transmission_error_count."
)


def test_chat_path_records_slot_handoff_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    payload = build_live_chat_response(ChatRequest(message=_SCADA_DRIFT_QUERY)).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    assert plan.get("slot_constraint_projection_summary") is not None
    if "handoff_drift_from_final_spl" in plan:
        assert isinstance(plan["handoff_drift_from_final_spl"], bool)
    handoff = plan.get("slot_handoff_summary") or {}
    if handoff:
        assert "planning_snapshot" in handoff or "final_spl_projection" in handoff


def test_ws2_drift_e2e_merge_preserves_route_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    payload = build_live_chat_response(ChatRequest(message=_SCADA_DRIFT_QUERY)).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    routing = (payload.get("run_contract") or {}).get("routing") or {}
    skill_before = routing.get("canonical_skill")
    assert skill_before
    if plan.get("handoff_drift_from_final_spl"):
        drift = plan.get("slot_handoff_summary") or {}
        assert drift.get("drift_from_final_spl") is True
    assert routing.get("canonical_skill") == skill_before
    assert payload.get("selected_skill") == skill_before
