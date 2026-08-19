"""S4 SIEM-first zero-day — Experience Center only."""

from __future__ import annotations

from app.demo.ec_siem_s4 import (
    S4_GAP_CANDIDATE_SPL,
    build_s4_detection_opportunity,
    build_s4_investigation_scope,
    build_s4_siem_coverage,
    s4_gap_spl_validation,
)
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s4.pack import S4_SCENARIO_ID


def test_s4_initial_siem_coverage_no_detection_valid_outcome() -> None:
    """S4 opens with no existing detection, a validated-but-inert gap SPL, Splunk != CMDB.

    The agent UI (`use_agent_ui`) deliberately ships `ec_siem_coverage`,
    `ec_detection_opportunity` and `ec_investigation_scope` as None — the agent
    workflow lane replaces those panels. The facts they carried are still
    authoritative, so assert them on the builders that produce them plus the
    envelope fields the agent UI still ships.
    """
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-siem").model_dump()
    evidence_ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert "ev-s4-siem-check" in evidence_ids
    assert "ev-s4-advisory" in evidence_ids
    assert envelope["candidate_spl"]["execution_eligible"] is False

    coverage = build_s4_siem_coverage().model_dump()
    assert coverage["coverage_status"] == "PARTIAL"
    assert coverage["existing_content"][0]["status"] == "none"
    assert build_s4_detection_opportunity().model_dump()["deploy_status"] == "not_deployed"
    scope = build_s4_investigation_scope().model_dump()
    assert scope["telemetry_sources"][1]["status"] == "SEPARATE_RESOURCE"


def test_s4_gap_spl_passes_validator() -> None:
    validation = s4_gap_spl_validation()
    assert validation["approved"] is True
    assert validation["execution_eligible"] is False
    assert S4_GAP_CANDIDATE_SPL in envelope_candidate_spl()


def envelope_candidate_spl() -> str:
    envelope = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-spl").model_dump()
    return envelope["candidate_spl"]["candidate_spl"]


def test_s4_hunt_follow_up_uses_gap_evidence() -> None:
    """The IOC hunt is now reached through the `run_splunk_ioc_hunt` chip.

    `search_exploitation_indicators` survives only as an internal expansion id
    (`_s4_expand_applied`) and is no longer user-selectable, so driving it
    directly raises UnknownFollowUpError. Drive the real chip instead; the
    coverage assertion moves to the builder because the agent UI does not ship
    `ec_siem_coverage`, and `ec_action_readiness` is empty in agent mode (the
    readiness rows are rendered by the agent lane), so the inertness of the
    generated search is asserted on the validator instead.
    """
    envelope = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id="s4-hunt",
        follow_up_id="run_splunk_ioc_hunt",
    ).model_dump()
    ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert "ev-s4-ioc-hunt" in ids

    coverage = build_s4_siem_coverage(hunt_obtained=True).model_dump()
    assert coverage["generated_searches"][0]["validator_status"] == "PASS"

    validation = s4_gap_spl_validation()
    assert validation["approved"] is True
    assert validation["execution_eligible"] is False


def test_s4_policy_chips_surface_distinct_source_evidence() -> None:
    """Advisory and hardening evidence stay distinct and each clears its own gap.

    Neither is a standalone chip any more. `show_advisory` is pre-applied at
    turn 0 (`S4_PLAN_PREREAD`) and `show_hardening_guidance` is reached by
    applying the temporary control (`_s4_expand_applied`), so both are driven
    the way a user actually reaches them.
    """
    opening = run_experience_center_turn(S4_SCENARIO_ID, session_id="s4-policy-advisory").model_dump()
    opening_ids = {item["evidence_id"] for item in opening["source_evidence"]}
    assert "ev-s4-advisory" in opening_ids
    assert not any(
        "advisory" in item.lower()
        for item in opening["ec_investigation_outcome"]["missing_evidence"]
    )

    hardening = run_experience_center_turn(
        S4_SCENARIO_ID,
        session_id="s4-policy-hardening",
        follow_up_id="apply_temporary_control",
    ).model_dump()
    hardening_ids = {item["evidence_id"] for item in hardening["source_evidence"]}
    assert "ev-s4-hardening" in hardening_ids
    assert not any(
        "hardening" in item.lower()
        for item in hardening["ec_investigation_outcome"]["missing_evidence"]
    )
    assert hardening_ids != opening_ids


def test_build_s4_coverage_after_hunt() -> None:
    after = build_s4_siem_coverage(hunt_obtained=True)
    assert after.generated_searches[0].source_evidence_ids == ["ev-s4-ioc-hunt"]
    opp = build_s4_detection_opportunity()
    assert "not_deployed" in opp.deploy_status
