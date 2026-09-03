"""Artifact refs on the STANDARD reviewer export resolve against the forensic bundle."""

from __future__ import annotations

import json
from pathlib import Path

from app.chat.debug_summary import build_debug_summary
from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace
from app.chat.trace_artifacts import resolve_all_refs, resolve_artifact_ref

_FIXTURE = Path(__file__).parent / "fixtures" / "trace_consistency" / "p2_review_only_spl_payload.json"


def _bundle() -> dict:
    payload = json.loads(_FIXTURE.read_text())
    summary = build_debug_summary(payload=payload)
    effective = summary["effective_state"]
    forensic = assemble_forensic_bundle(
        trace_id="t-ref",
        run={
            "trace_id": "t-ref",
            "metadata": {
                "debug_summary": {**summary, "effective_state": {"$ref": "run.metadata.effective_state"}},
                "effective_state": effective,
                "control_plane_trace": payload.get("control_plane_trace"),
                "final_output": {"message": "analyst card", "answer_mode": payload.get("answer_mode")},
            },
        },
        events=[],
    )
    return forensic


def test_every_reviewer_artifact_ref_resolves() -> None:
    forensic = _bundle()
    reviewer = build_reviewer_trace(forensic)
    resolved = resolve_all_refs(forensic, reviewer["artifacts"])
    assert resolved["final_answer_ref"]["message"] == "analyst card"
    assert resolved["effective_state_ref"]["schema_version"] == "trace_effective_state_v1"
    assert resolved["control_plane_trace_ref"]
    assert resolved["full_debug_bundle_ref"]["trace_id"] == "t-ref"
    evidence = resolved.get("evidence_plan_ref")
    assert evidence is None or isinstance(evidence, dict)


def test_unknown_ref_raises() -> None:
    forensic = _bundle()
    try:
        resolve_artifact_ref(forensic, "artifact:not_a_real_object")
    except KeyError:
        return
    raise AssertionError("expected KeyError")
