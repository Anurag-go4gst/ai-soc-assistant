"""Reviewer HIL uses final adjudicated state; superseded reasons stay forensic."""

from __future__ import annotations

import json
from pathlib import Path

from app.chat.debug_summary import build_debug_summary
from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace
from app.chat.trace_effective_state import build_effective_state_projection

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"


def _reviewer() -> dict:
    payload = json.loads(_FIXTURE.read_text())
    summary = build_debug_summary(payload=payload)
    forensic = assemble_forensic_bundle(
        trace_id="p2-hil",
        run={
            "metadata": {
                "debug_summary": {**summary, "effective_state": {"$ref": "run.metadata.effective_state"}},
                "effective_state": summary["effective_state"],
                "control_plane_trace": payload.get("control_plane_trace"),
                "final_output": {
                    "hil_required": True,
                    "hil_reason": "source_profile_slots_missing",
                    "message": "card",
                },
            }
        },
        events=[],
    )
    return build_reviewer_trace(forensic)


def test_reviewer_hil_uses_final_adjudicated_state() -> None:
    hil = _reviewer()["hil"]
    assert hil["baseline_hil_required"] is False
    assert hil["current_turn_hil_required"] is False
    assert hil["current_turn_hil_reason"] is None
    assert hil["artifact_review_required"] is True
    assert hil["execution_hil_required_if_requested"] is True
    assert hil["execution_hil_reason"] == "review_only_placeholder_pending_binding"
    assert hil["superseded_by_final_resolution"] is True


def test_stale_source_profile_reason_is_not_reviewer_current_turn_truth() -> None:
    reviewer = _reviewer()
    assert reviewer["hil"]["current_turn_hil_reason"] != "source_profile_slots_missing"
    assert reviewer["explainability"]["final_output"]["current_turn_hil_required"] is False
    # Legacy fields remain visible as legacy, not as current truth.
    assert reviewer["explainability"]["final_output"]["legacy_hil_reason"] == "source_profile_slots_missing"


def test_forensic_effective_state_retains_superseded_history() -> None:
    payload = json.loads(_FIXTURE.read_text())
    hil = build_effective_state_projection(payload)["hil"]
    assert hil["initial_hil_candidate_reason"] == "source_profile_slots_missing"
    assert hil["superseded_by_final_resolution"] is True
    assert hil["final_hil_reason"] is None
