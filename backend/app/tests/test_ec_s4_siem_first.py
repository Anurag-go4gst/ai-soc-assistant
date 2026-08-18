"""S4 SIEM-first zero-day — Experience Center only."""

from __future__ import annotations

from app.demo.ec_siem_s4 import (
    S4_GAP_CANDIDATE_SPL,
    build_s4_detection_opportunity,
    build_s4_siem_coverage,
    s4_gap_spl_validation,
)
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s4.pack import S4_SCENARIO_ID


def test_s4_initial_siem_coverage_no_detection_valid_outcome() -> None:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-siem").model_dump()
    coverage = envelope["ec_siem_coverage"]
    assert coverage["coverage_status"] == "PARTIAL"
    assert coverage["existing_content"][0]["status"] == "none"
    evidence_ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert "ev-s4-siem-check" in evidence_ids
    assert "ev-s4-advisory" in evidence_ids
    assert envelope["ec_detection_opportunity"]["deploy_status"] == "not_deployed"
    assert envelope["candidate_spl"]["execution_eligible"] is False
    assert envelope["ec_investigation_scope"]["telemetry_sources"][1]["status"] == "SEPARATE_RESOURCE"


def test_s4_gap_spl_passes_validator() -> None:
    validation = s4_gap_spl_validation()
    assert validation["approved"] is True
    assert validation["execution_eligible"] is False
    assert S4_GAP_CANDIDATE_SPL in envelope_candidate_spl()


def envelope_candidate_spl() -> str:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-spl").model_dump()
    return envelope["candidate_spl"]["candidate_spl"]


def test_s4_hunt_follow_up_uses_gap_evidence() -> None:
    envelope = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id="s4-hunt",
        follow_up_id="search_exploitation_indicators",
    ).model_dump()
    ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert "ev-s4-ioc-hunt" in ids
    assert envelope["ec_siem_coverage"]["generated_searches"][0]["validator_status"] == "PASS"
    readiness = envelope["ec_action_readiness"]
    assert any("compromised" in row["action"].lower() and row["state"] == "NOT_RECOMMENDED_YET" for row in readiness)


def test_s4_policy_chips_surface_distinct_source_evidence() -> None:
    session_id = "s4-policy-chips"
    for follow_up_id, expected_id, missing_token in (
        ("show_advisory", "ev-s4-advisory", "advisory"),
        ("show_hardening_guidance", "ev-s4-hardening", "hardening"),
    ):
        envelope = run_experience_center_turn(
            S4_SCENARIO_ID,
            session_id=f"{session_id}-{follow_up_id}",
            follow_up_id=follow_up_id,
        ).model_dump()
        ids = {item["evidence_id"] for item in envelope["source_evidence"]}
        assert expected_id in ids
        assert not any(missing_token in item.lower() for item in envelope["ec_investigation_outcome"]["missing_evidence"])


def test_build_s4_coverage_after_hunt() -> None:
    after = build_s4_siem_coverage(hunt_obtained=True)
    assert after.generated_searches[0].source_evidence_ids == ["ev-s4-ioc-hunt"]
    opp = build_s4_detection_opportunity()
    assert "not_deployed" in opp.deploy_status
