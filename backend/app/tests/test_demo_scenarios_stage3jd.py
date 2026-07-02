from __future__ import annotations

import json

from app.api.routes_scenarios import list_demo_scenario_fixtures, run_demo_scenario_fixture


BANNED_VISIBLE_TERMS = (
    "synthetic",
    "demo",
    "simulated",
    "mock",
    "not executed",
    "disabled",
    "SourceEvidence",
    "StructuredContext",
    "not_started",
    "mcp_global_execution_disabled",
    "spl_generation_not_enabled",
    "final synthesis",
)

BLOCKED_REMEDIATION_TERMS = (
    "block IP",
    "disable user",
    "isolate endpoint",
    "containment",
)

INVALID_MODEL_SPL_FRAGMENTS = (
    "tstats count FROM pgcil_soc",
    "now() - 60m",
    "eval first_failure = min(_time) as first_failure WHERE",
)


def _run(scenario_id: str):
    return run_demo_scenario_fixture(scenario_id)


def _visible_text(response) -> str:
    payload = {
        "message": response.message,
        "analyst_summary": response.analyst_summary,
        "analyst_response": response.analyst_response.model_dump() if response.analyst_response else None,
    }
    return json.dumps(payload)


def _main_answer_text(response) -> str:
    governed = None
    if response.foundation_sec_governance and response.foundation_sec_governance.governed_analysis:
        analysis = response.foundation_sec_governance.governed_analysis
        governed = {
            "model_signal": analysis.model_signal,
            "vai_soc_decision": analysis.vai_soc_decision,
            "evidence_used": analysis.evidence_used,
            "missing_evidence": analysis.missing_evidence,
            "governance_overrides": [item.model_dump() for item in analysis.governance_overrides],
            "guardrail_notes": analysis.guardrail_notes,
        }
    payload = {
        "message": response.message,
        "analyst_summary": response.analyst_summary,
        "analyst_response": response.analyst_response.model_dump() if response.analyst_response else None,
        "foundation_sec_governed_analysis": governed,
    }
    return json.dumps(payload)


def _lineage_stage(response, stage_id: str):
    assert response.investigation_lineage is not None
    return next(stage for stage in response.investigation_lineage.stages if stage.stage_id == stage_id)


def test_get_demo_scenarios_returns_all_stage3jd_scenarios() -> None:
    payload = list_demo_scenario_fixtures()

    scenario_ids = {item["scenario_id"] for item in payload["scenarios"]}
    assert payload["demo_mode"] is True
    assert payload["evidence_origin"] == "coe_synthetic_fixture"
    assert payload["no_live_customer_data"] is True
    # Leadership picker (EC live-feel parity): 7 firewall incident + 3 secondary showcases.
    assert scenario_ids == {
        "firewall_deny_coordinated_attack",
        "firewall_baseline_template_spl",
        "splunk_env_asa_ti_readiness",
        "network_blast_radius_attacker_ip",
        "scada_critical_telemetry_health",
        "ir_containment_advisory_firewall_incident",
        "executive_incident_mitre_summary",
        "mitre_mapping_auth_alert",
        "cert_in_ot_reporting_obligation",
        "guided_investigation_supply_chain",
    }


def test_each_demo_scenario_marks_fixture_origin_and_no_live_data() -> None:
    for item in list_demo_scenario_fixtures()["scenarios"]:
        response = _run(item["scenario_id"])
        assert response.demo_mode is True
        assert response.evidence_origin == "coe_synthetic_fixture"
        assert response.no_live_customer_data is True
        assert response.structured_context is not None
        assert response.structured_context.synthesis_allowed is False
        assert response.analyst_response is not None


def test_firewall_incident_exposes_interactive_p1_ticket_action() -> None:
    response = _run("firewall_deny_coordinated_attack")

    assert response.analyst_response is not None
    analyst = response.analyst_response
    assert any("Open P1 incident record" in action for action in analyst.recommended_actions)
    assert len(analyst.interactive_actions) == 1
    action = analyst.interactive_actions[0]
    assert action["ui_action"] == "render_interactive_ticket"
    assert action["label"] == "Click to Execute: Open P1 Incident Ticket"
    assert action["success_label"] == "P1 Ticket created"
    assert action["status"] == "SUCCESS"
    details = action["ticket_details"]
    assert details["ticket_id"] == "INC-2026-89412"
    assert details["priority"] == "P1 - CRITICAL"
    assert details["assignment_group"] == "SOC-Incident-Response"
    assert details["incident_commander"] == "On-Duty SOC Lead"
    assert "198.51.100.42" in details["summary"]
    assert "svc_jump_ops" in details["summary"]
    assert details["auto_attached_evidence"] == ["ev-fw-deny-q1", "Splunk_Search_firewall_5_rows"]


def test_failed_login_spike_includes_t1110_and_source_refs() -> None:
    response = _run("failed_login_spike_app01")

    assert response.structured_context is not None
    assert response.source_evidence
    assert any(row.get("index") == "pgcil_soc" and row.get("sourcetype") == "pgcil:auth" for ev in response.source_evidence for row in ev.preview_rows)
    assert any(candidate.get("technique_id") in {"T1110", "T1110.001"} and candidate.get("support") == "supported" for candidate in response.structured_context.mitre_candidates)
    assert all(fact.source_refs for fact in response.structured_context.structured_facts)


def test_visible_failed_login_response_is_analyst_facing() -> None:
    response = _run("failed_login_spike_app01")
    visible = _visible_text(response)

    for term in BANNED_VISIBLE_TERMS:
        assert term.lower() not in visible.lower()
    assert response.analyst_response is not None
    assert response.analyst_response.severity_label == "P2 High"
    assert "APP-01" in visible
    assert "10.10.4.21" in visible
    assert "10.10.4.22" in visible
    assert "10.10.4.19" in visible
    assert "T1110.001" in visible
    assert "SOC-SOP-AUTH-001" in visible
    assert "Foundation-sec analysis" not in visible
    assert response.analyst_response.foundation_sec_analysis is not None
    assert "14 targeted accounts" not in visible
    assert "no privileged accounts targeted" not in visible.lower()
    assert "confirmed account compromise" not in visible.lower()
    assert "Distinct users by source" in visible
    assert "Supported" in visible
    assert "Confirmed" not in visible
    assert all(action.startswith(("P1: ", "P2: ", "P3: ", "P4: ")) for action in response.analyst_response.recommended_actions)
    assert response.analyst_response.evidence_summary is not None
    assert "42 + 31 + 28" in response.analyst_response.evidence_summary
    playbook = response.analyst_response.retrieved_playbook
    assert playbook is not None
    assert playbook.get("citation") == "SOC-SOP-AUTH-001#triage"
    assert playbook.get("retrieval_mode") == "governed_soc_kb"


def test_technical_trace_keeps_provenance_fields() -> None:
    response = _run("failed_login_spike_app01")

    assert response.evidence_origin == "coe_synthetic_fixture"
    assert response.source_evidence[0].provenance == "coe_synthetic_fixture"
    assert response.structured_context is not None
    assert response.structured_context.entity_summary["fixture"] is True
    assert response.context_sufficiency is not None
    assert any(reason.startswith("evidence_origin:") for reason in response.context_sufficiency.reasons)


def test_success_after_failures_spl_correlates_success_and_failure() -> None:
    response = _run("successful_login_after_failures")

    assert response.candidate_spl is not None
    spl = response.candidate_spl.candidate_spl
    assert 'action="failure"' in spl
    assert 'action="success"' in spl
    assert "success_count" in spl
    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "spl_review_only"
    assert response.execution is not None
    assert response.execution.executed_spl is not None
    assert response.analyst_response is not None
    assert response.analyst_response.spl_code is not None
    assert "action=failure OR action=success" in response.analyst_response.spl_code
    assert "source_ips" in response.analyst_response.spl_code
    assert "risk" in response.analyst_response.spl_code
    assert response.analyst_response.response_profile == "spl_only"
    assert response.analyst_response.splunk_results_table == []
    assert response.analyst_response.retrieved_playbook is None
    assert response.analyst_response.sop_guidance is None
    assert response.analyst_response.foundation_sec_analysis is None
    assert response.analyst_response.mitre_mappings == []
    assert response.analyst_response.recommended_actions == []
    assert response.candidate_spl.execution_eligible is False
    visible = _visible_text(response)
    for fragment in INVALID_MODEL_SPL_FRAGMENTS:
        assert fragment not in visible
    assert "execution_eligible=true" not in visible
    assert "58 failures" not in visible
    assert "svc_grid_ops" not in visible


def test_firewall_baseline_template_is_environment_grounded_and_explained() -> None:
    response = _run("firewall_baseline_template_spl")

    assert response.candidate_spl is not None
    spl = response.candidate_spl.candidate_spl
    assert "index=pgcil_soc" in spl
    assert "sourcetype=pgcil:firewall" in spl
    assert "earliest=-7d" in spl
    assert "| bucket _time span=1h" in spl
    assert 'count(eval(action="deny")) as deny_count' in spl
    assert "deny_upper_bound" in spl
    assert "port_upper_bound" in spl
    assert "sort -deny_count" not in spl

    assert response.analyst_response is not None
    analyst = response.analyst_response
    assert analyst.response_profile == "spl_only"
    assert analyst.spl_code == spl
    assert analyst.spl_status_detail is not None
    assert analyst.spl_status_detail["template_status"] == "active"
    assert analyst.spl_status_detail["generation_status"] == "generated / grounded to environment knowledge"
    assert "index=pgcil_soc" in analyst.spl_status_detail["environment_fields_used"]
    assert "sourcetype=pgcil:firewall" in analyst.spl_status_detail["environment_fields_used"]
    assert "no subsearches" in analyst.spl_status_detail["query_complexity"]
    assert analyst.direct_answer_summary is not None
    assert "7-day statistical profile" in analyst.direct_answer_summary
    assert "downstream detections" in analyst.direct_answer_summary
    assert any("outputlookup firewall_baseline.csv" in item for item in analyst.analyst_checklist)
    assert any("deny_upper_bound" in item for item in analyst.key_fields)


def test_scada_telemetry_health_explains_unresolved_environment_mapping() -> None:
    response = _run("scada_critical_telemetry_health")

    assert response.analyst_response is not None
    analyst = response.analyst_response
    assert analyst.spl_status_detail is not None
    assert analyst.spl_status_detail["generation_status"] == "blocked"
    assert "unresolved index slot: <scada_index>" in analyst.spl_status_detail["environment_fields_used"]
    assert analyst.direct_answer_summary is not None
    assert "source-health check" in analyst.direct_answer_summary
    assert "Environment Knowledge Base" in analyst.direct_answer_summary
    assert any("rtu_id" in item for item in analyst.key_fields)
    assert any("OT engineering" in item for item in analyst.analyst_checklist)


def test_sop_demo_does_not_generate_spl() -> None:
    response = _run("brute_force_sop_guidance")

    assert response.selected_skill == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "knowledge_only_answer"
    assert response.analyst_response is not None
    visible = _visible_text(response)
    assert "Triage steps" not in visible
    assert response.analyst_response.sop_guidance is not None
    playbook = response.analyst_response.retrieved_playbook
    assert playbook is not None
    assert playbook["title"] == "Brute-force Authentication Investigation"
    assert playbook["id"] == "SOC-SOP-AUTH-001"
    assert playbook["version"] == "v2026.04"
    assert playbook["retrieval_mode"] == "governed_soc_kb"
    assert playbook["citation"] == "SOC-SOP-AUTH-001#triage"
    guidance = json.dumps(response.analyst_response.sop_guidance)
    assert "SOC-SPL-LIB" not in guidance
    assert "IRP-AUTH" not in visible
    assert response.analyst_response.escalation_criteria
    assert response.analyst_response.closure_conditions
    assert response.analyst_response.spl_code is None


def test_mitre_visible_response_has_mapping_table_without_internal_labels() -> None:
    response = _run("mitre_mapping_auth_alert")
    visible = _visible_text(response)

    assert response.analyst_response is not None
    assert response.analyst_response.mitre_mappings
    assert "T1110.001" in visible
    assert "T1078" in visible
    assert "Supported" in visible
    assert "Requires validation" in visible
    assert "T1078 Valid Accounts is confirmed" not in visible
    for term in ("workflow", "routing", "SourceEvidence", "StructuredContext", "not_started"):
        assert term.lower() not in visible.lower()


def test_curated_spl_scenario_carries_capability_profile() -> None:
    # The air-gapped/no-SAIA demo was removed in the 2026-06-24 curation; the
    # capability-profile governance contract is still exercised on a retained SPL scenario.
    response = _run("successful_login_after_failures")

    assert response.saia_available is True
    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.spl_validation.capability_profile is not None
    assert response.spl_validation.capability_profile["mcp_available"] is True


def test_mitre_mapping_uses_alert_fixture_not_empty_guess() -> None:
    response = _run("mitre_mapping_auth_alert")

    assert response.user_query is not None
    assert "brute-force" in response.user_query.lower() or "mitre" in response.user_query.lower()
    assert response.candidate_spl is None
    assert response.structured_context is not None
    mitre = response.structured_context.mitre_candidates
    assert any(item.get("technique_id") == "T1110" and item.get("support") == "supported" for item in mitre)
    assert any(item.get("technique_id") == "T1078" and item.get("support") == "analyst_review" for item in mitre)
    assert response.structured_context.structured_facts


def test_stage3jj_visible_answers_apply_guard_lessons() -> None:
    for item in list_demo_scenario_fixtures()["scenarios"]:
        response = _run(item["scenario_id"])
        visible = _visible_text(response)

        for term in BLOCKED_REMEDIATION_TERMS:
            assert term.lower() not in visible.lower()
        for term in BANNED_VISIBLE_TERMS:
            assert term.lower() not in visible.lower()
        assert "execution_eligible=true" not in visible
        assert "High priority" not in visible
        assert "Medium priority" not in visible
        assert "Low priority" not in visible


def test_stage3jj_failed_login_answer_uses_governed_foundation_sec_posture() -> None:
    response = _run("failed_login_spike_app01")

    assert response.analyst_response is not None
    answer = response.analyst_response
    visible = _visible_text(response)
    assert answer.severity_label == "P2 High"
    assert answer.finding_title == "Brute-force authentication spike detected on APP-01"
    assert "101 failed logins across three source IPs" in visible
    assert "global distinct user count is not confirmed" in visible
    assert "T1110.001" in visible
    assert "Supported" in visible
    assert "Confirmed" not in visible
    assert "14 targeted accounts" not in visible
    assert "no privileged accounts targeted" not in visible.lower()
    assert "APP-01 is critical" not in visible
    assert any(row.get("Distinct users by source") == 7 for row in answer.splunk_results_table)
    assert all(action.startswith(("P1: ", "P2: ", "P3: ", "P4: ")) for action in answer.recommended_actions)


def test_stage3jj_spl_answers_are_template_generated_and_not_execution_eligible() -> None:
    for scenario_id in ("successful_login_after_failures",):
        response = _run(scenario_id)
        visible = _visible_text(response)

        assert response.candidate_spl is not None
        assert response.candidate_spl.execution_eligible is False
        assert "Template-generated SPL - validator-ready" in visible
        for fragment in INVALID_MODEL_SPL_FRAGMENTS:
            assert fragment not in visible
        assert "execution_eligible=true" not in visible


# The mock-execution "+ run" demo variants were removed in the 2026-06-24 curation
# (curated set is intentionally execution-disabled). Mock MCP execution remains
# covered by app/tests/test_demo_splunk_envelope_stage3m_s3.py via the envelope path.


def test_stage3jj3_foundation_sec_governance_serializes_for_experience_center() -> None:
    # Retained curated scenarios that carry a Foundation-sec governance fixture.
    scenario_ids = (
        "failed_login_spike_app01",
        "mitre_mapping_auth_alert",
        "mitre_mapping_requires_context",
    )

    for scenario_id in scenario_ids:
        response = _run(scenario_id)
        governance = response.foundation_sec_governance

        # SPL-only scenarios intentionally carry no governed-model analysis block
        # (scenarios.py forces foundation_sec_governance=None for response_profile
        # "spl_only"); governed-answer scenarios still serialize the block.
        if response.analyst_response is not None and response.analyst_response.response_profile == "spl_only":
            assert governance is None
            continue

        assert governance is not None
        assert governance.live_llm_called is False
        assert governance.final_answer_source == "governed_fixture"
        assert governance.display_mode == "main_answer_governed_model"
        assert governance.captured_outputs
        assert governance.governed_analysis is not None


def test_stage3jj3_failed_login_governance_records_guarded_corrections() -> None:
    response = _run("failed_login_spike_app01")
    text = _main_answer_text(response)

    assert "Foundation-sec model signal" in text
    assert "password-guessing" in text
    assert "T1110.001" in text
    assert "Global distinct-user count is not claimed" in text
    assert "Privileged-account status is not yet available" in text
    assert "14 targeted accounts" not in text
    assert "no privileged accounts targeted" not in text.lower()
    assert "confirmed compromise" not in text.lower()


def test_stage3jj3_success_after_failure_generate_only_has_no_foundation_sec_governance() -> None:
    response = _run("successful_login_after_failures")
    assert response.foundation_sec_governance is None
    visible = _visible_text(response)
    assert "58 failures" not in visible
    assert "materially higher-risk credential-access signal" not in visible


def test_stage3jj3_success_after_failure_governance_keeps_t1078_validation_required() -> None:
    # The "+ run" demo was removed in the 2026-06-24 curation; the governance property
    # (T1078 stays validation-required / candidate, never confirmed) is exercised on the
    # retained provided-context MITRE mapping scenario.
    response = _run("mitre_mapping_auth_alert")
    text = _main_answer_text(response)

    assert "T1078" in text
    assert response.structured_context is not None
    mitre = response.structured_context.mitre_candidates
    assert any(
        item.get("technique_id") == "T1078" and item.get("support") == "analyst_review"
        for item in mitre
    )
    assert "T1078 confirmed" not in text
    assert "post-login malicious activity occurred" not in text


def test_stage3jj3_mitre_clarification_overrides_model_attempt() -> None:
    response = _run("mitre_mapping_requires_context")
    text = _main_answer_text(response)

    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert "Please provide the alert title" in text
    assert "clarification_needed=false" in text
    assert "clarification_required" in text
    assert "No MITRE technique is selected without event evidence" in text


# test_stage3jj3_mcp_discovery_* removed with the mcp_metadata_discovery_app01 demo
# (2026-06-24 curation). Deterministic tool-mapping/discovery governance is covered by
# the MCP tool-plan-shadow and resource-planner tests on retained scenarios.


def test_stage3jj3_spl_governance_forces_model_spl_candidate_only() -> None:
    # Retargeted from the removed air-gapped demo to a retained SPL scenario; the
    # guarantee (candidate SPL is never executable) is identical.
    response = _run("successful_login_after_failures")
    text = _main_answer_text(response)

    # Governed guarantee for SPL-only scenarios: the candidate SPL is never
    # executable. Carried on the candidate envelope, not as inline answer text.
    assert response.candidate_spl is not None
    assert response.candidate_spl.execution_eligible is False
    assert "execution_eligible=true" not in text
    for fragment in INVALID_MODEL_SPL_FRAGMENTS:
        assert fragment not in text


def test_stage3jj3_trace_matches_governed_failed_login_answer() -> None:
    response = _run("failed_login_spike_app01")

    assert response.analyst_response is not None
    assert response.analyst_response.severity_label == "P2 High"
    assert response.severity_decision is not None
    assert response.severity_decision.severity_label == "P2 High"
    severity_stage = _lineage_stage(response, "severity")
    assert severity_stage.explanation == "P2 High"
    assert severity_stage.technical_output["severity_label"] == "P2 High"


def test_stage3jj3_success_after_failure_trace_uses_success_template() -> None:
    response = _run("successful_login_after_failures")

    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "auth_success_after_failure"
    assert response.spl_template is not None
    assert response.spl_template["template_id"] == "auth_success_after_failure"
    assert response.severity_decision is not None
    assert response.severity_decision.severity_label == "P2 High"
    template_stage = _lineage_stage(response, "spl_template")
    assert template_stage.status == "complete"
    assert template_stage.technical_output["template_id"] == "auth_success_after_failure"


def test_stage3jj3_clarification_and_discovery_do_not_show_unrelated_sop() -> None:
    for scenario_id in ("mitre_mapping_requires_context",):
        response = _run(scenario_id)

        assert response.analyst_response is not None
        assert response.analyst_response.retrieved_playbook is None
        assert response.analyst_response.sop_guidance is None


# test_stage3jj3_mcp_discovery_trace_is_not_unknown_or_clarification removed with the
# mcp_metadata_discovery_app01 demo (2026-06-24 curation).


def test_stage3jj3_trace_wording_mentions_captured_foundation_sec_without_enabling_synthesis() -> None:
    response = _run("failed_login_spike_app01")

    assert response.synthesis_status is not None
    assert response.answer_guard is not None
    assert response.synthesis_status.enabled is False
    assert response.answer_guard.enabled is False
    assert "captured Hugging Face/Foundation-sec output governed by deterministic policy" in response.synthesis_status.reason
    assert "no live final synthesis is run" in response.synthesis_status.reason
    assert "captured Hugging Face/Foundation-sec output" in response.answer_guard.reason
    assert "live Answer Guard execution is not run" in response.answer_guard.reason
