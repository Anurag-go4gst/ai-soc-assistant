"""SIEM-first EC investigation model — Experience Center only."""

from __future__ import annotations

import json

import pytest

from app.demo.ec_siem import (
    SAIA_TOOL_NAMES,
    SPLUNK_MCP_AUDIT_ROWS,
    NONEXISTENT_TOOLS,
    S2_GAP_CANDIDATE_SPL,
    assert_no_saia_in_projection,
    build_s2_siem_coverage,
    ec_verified_splunk_tools_for_projection,
    s2_gap_spl_validation,
)
from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.s1.pack import S1_SCENARIO_ID
from app.demo.fixtures.s2.pack import S2_SCENARIO_ID


def test_splunk_mcp_audit_inventory_is_documented() -> None:
    assert len(SPLUNK_MCP_AUDIT_ROWS) >= 8
    find_row = next(row for row in SPLUNK_MCP_AUDIT_ROWS if row["tool"] == "find_data_source")
    assert find_row["available"] == "no"
    saia_rows = [row for row in SPLUNK_MCP_AUDIT_ROWS if row["tool"] in SAIA_TOOL_NAMES]
    assert saia_rows and all(row["available"] == "blocked" for row in saia_rows)


def test_find_data_source_not_in_environment() -> None:
    assert "find_data_source" in NONEXISTENT_TOOLS
    tools = ec_verified_splunk_tools_for_projection()
    assert "find_data_source" not in tools
    for name in SAIA_TOOL_NAMES:
        assert name not in tools


def test_s2_gap_spl_passes_validator_and_candidate_not_equal_normalized_execution() -> None:
    validation = s2_gap_spl_validation()
    assert validation["approved"] is True
    assert validation["normalized_spl"]
    assert validation["execution_eligible"] is False
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-spl").model_dump()
    assert envelope["candidate_spl"]["candidate_spl"] == S2_GAP_CANDIDATE_SPL
    assert envelope["candidate_spl"]["execution_eligible"] is False
    assert envelope["spl_validation"]["execution_eligible"] is False
    assert envelope["execution"]["candidate_spl_not_executed"] is True
    assert envelope["execution"]["executed_spl"] == validation["normalized_spl"]


def test_s2_reuse_first_partial_coverage_gap_search_only() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-reuse").model_dump()
    coverage = envelope["ec_siem_coverage"]
    assert coverage["coverage_status"] == "PARTIAL"
    existing = coverage["existing_content"][0]
    assert existing["reused"] is True
    assert existing["coverage"] == "PARTIAL"
    assert coverage["generated_searches"][0]["candidate_created"] is True
    assert coverage["generated_searches"][0]["normalized"] is True
    # detection replay should appear in source evidence before gap query
    evidence_ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert "ev-s2-detection" in evidence_ids
    assert evidence_ids.index("ev-s2-detection") < evidence_ids.index("ev-s2-tool")


def test_detection_existence_does_not_confirm_breach() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-breach").model_dump()
    outcome = envelope["ec_investigation_outcome"]
    assert "Restricted customer-data access" in outcome["unconfirmed"]
    assessment = envelope["analyst"]["assessment"].lower()
    assert "breach not confirmed" in assessment
    assert envelope["ec_attack_chain"][-1]["status"] == "not_confirmed"


def test_ec_projection_has_no_saia_tools() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-saia").model_dump()
    assert_no_saia_in_projection(envelope)
    traces = envelope.get("ec_siem_tool_traces") or []
    for trace in traces:
        assert trace["mcp_tool"] not in SAIA_TOOL_NAMES


def test_layer2_shows_verified_mcp_tools_only() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-tools").model_dump()
    allowed = set(ec_verified_splunk_tools_for_projection())
    for trace in envelope["ec_siem_tool_traces"]:
        assert trace["mcp_tool"] in allowed
    assert "SIEM coverage discovery" in envelope["ec_layer2_path"]


def test_s2_siem_coverage_card_fields_visitor_readable() -> None:
    envelope = run_experience_center_turn(S2_SCENARIO_ID, session_id="s2-siem-card").model_dump()
    rows = envelope["ec_siem_coverage"]["coverage_rows"]
    assert rows[0]["investigation_need"] == "Prompt injection"
    assert rows[0]["decision"] == "Reused"
    blob = json.dumps(rows).lower()
    assert "saia_" not in blob


def test_dlp_follow_up_journey_reuse_first_titles() -> None:
    envelope = run_experience_center_turn(
        S2_SCENARIO_ID,
        session_id="s2-siem-dlp",
        follow_up_id="check_dlp",
    )
    titles = [stage.title.lower() for stage in envelope.ec_execution_journey.stages]
    blob = " | ".join(titles)
    assert "dlp coverage" in blob
    assert "reusing" in blob or "dlp data" in blob


def test_build_s2_siem_coverage_after_dlp() -> None:
    before = build_s2_siem_coverage(dlp_obtained=False)
    after = build_s2_siem_coverage(dlp_obtained=True)
    dlp_before = next(row for row in before.coverage_rows if row.investigation_need == "DLP")
    dlp_after = next(row for row in after.coverage_rows if row.investigation_need == "DLP")
    assert dlp_before.decision == "Follow-up"
    assert dlp_after.decision == "Reused search"


def test_s1_reuse_first_gap_searches_only_after_existing_content() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-siem-reuse").model_dump()
    coverage = envelope["ec_siem_coverage"]
    assert coverage["coverage_status"] == "PARTIAL"
    assert coverage["existing_content"][0]["reused"] is True
    evidence_ids = [item["evidence_id"] for item in envelope["source_evidence"]]
    assert evidence_ids[0] == "ev-s1-existing-search"
    assert evidence_ids.index("ev-s1-existing-search") < evidence_ids.index("ev-s1-fw-search-1")
    assert envelope["ec_spl_governance"]["searches"]
    assert len(envelope["ec_spl_governance"]["searches"]) == 2


def test_s1_assessment_does_not_claim_all_communication_paths() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-scope-lang").model_dump()
    blob = envelope["analyst"]["assessment"].lower()
    assert "firewall-observed" in blob or "firewall telemetry" in blob
    assert "dns, proxy, vpn" in blob or "dns/proxy/vpn" in blob
    assert "not confirmed" in blob
    unconfirmed = " ".join(envelope["ec_investigation_outcome"]["unconfirmed"]).lower()
    assert "all communication" in unconfirmed or "dns / proxy / vpn" in unconfirmed


def test_s1_jump_host_pivot_and_scope_cards() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-pivot").model_dump()
    pivot = envelope["ec_investigation_pivot"]
    assert pivot["subject"] == "10.20.1.10"
    assert "only affected system" in pivot["summary"].lower() or "only system" in pivot["summary"].lower()
    scope = envelope["ec_investigation_scope"]
    assert scope["telemetry_queried"] == ["Firewall (pgcil_soc / pgcil:firewall)"]
    dns = next(row for row in scope["telemetry_sources"] if row["source"] == "DNS")
    assert dns["status"] == "AVAILABLE_NOT_QUERIED"


def test_s1_mitre_t1110_candidate_not_supported() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-mitre").model_dump()
    t1110 = next(item for item in envelope["ec_investigation_outcome"]["mitre"] if item["technique_id"] == "T1110.001")
    assert t1110["status"] == "candidate"
    mitre_table = envelope["analyst"]["mitre_mappings"]
    t1110_row = next(row for row in mitre_table if row["Technique"] == "T1110.001")
    assert t1110_row["Status"] == "Candidate"


def test_s1_layer2_path_has_no_empty_headings() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-layer2").model_dump()
    path = envelope["ec_layer2_path"]
    assert path
    assert all(item.strip() and item.strip() != "-" for item in path)
    assert "SIEM coverage discovery" in path


def test_s1_action_readiness_and_recommended_investigations() -> None:
    envelope = run_experience_center_turn(S1_SCENARIO_ID, session_id="s1-readiness").model_dump()
    rows = envelope["ec_action_readiness"]
    assert any(row["action"] == "Investigate jump host" and row["state"] == "RECOMMENDED" for row in rows)
    assert any(row["action"] == "Isolate jump host" and row["state"] == "NOT_RECOMMENDED_YET" for row in rows)
    investigations = envelope["ec_recommended_investigations"]
    assert investigations
    assert envelope["analyst"]["recommended_actions"]
