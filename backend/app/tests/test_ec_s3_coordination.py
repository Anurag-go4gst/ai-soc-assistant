"""S3 team-coordination projections — Experience Center only."""

from __future__ import annotations

from app.demo.ec_coordination_s3 import (
    build_s3_action_readiness,
    build_s3_evidence_reuse,
    build_s3_recommended_coordination,
)
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s3.pack import S3_SCENARIO_ID


def test_build_s3_evidence_reuse_rows_mark_reused() -> None:
    rows = build_s3_evidence_reuse()
    assert len(rows) >= 2
    assert all(row.status == "REUSED" for row in rows)


def test_build_s3_action_readiness_before_and_after_reply() -> None:
    before = build_s3_action_readiness([], [], {"disposition": "suspicious"})
    after = build_s3_action_readiness(["ingest_firewall_reply"], [], {"disposition": "needs_reassessment"})
    assert any(item.state == "NOT_RECOMMENDED_YET" for item in before if "immediately" in item.action.lower())
    assert any(item.state == "NOT_RECOMMENDED_YET" for item in after if "benign" in item.action.lower())
    assert any(item.state == "RECOMMENDED" for item in after if "whitelist" in item.action.lower())


def test_build_s3_recommended_coordination_mentions_no_spl() -> None:
    initial = build_s3_recommended_coordination([])
    assert any("no new splunk" in step.lower() or "reuse" in step.lower() for step in initial)
    after = build_s3_recommended_coordination(["ingest_firewall_reply"])
    assert any("not automatic" in step.lower() or "not close" in step.lower() for step in after)


def test_s3_initial_envelope_has_coordination_fields() -> None:
    envelope = run_experience_center_turn(S3_SCENARIO_ID, session_id="s3-coord").model_dump()
    assert envelope["ec_coordination_policy"]["spl_generated"] is False
    assert envelope["ec_evidence_reuse"]
    assert envelope["ec_action_readiness"]
    assert envelope["ec_status_summary"]
