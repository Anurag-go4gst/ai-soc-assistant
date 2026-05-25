from __future__ import annotations

import json

from app.api.routes_scenarios import list_demo_scenario_fixtures, run_demo_scenario_fixture


BANNED_VISIBLE_TERMS = (
    "fixture",
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


def _run(scenario_id: str):
    return run_demo_scenario_fixture(scenario_id)


def _visible_text(response) -> str:
    payload = {
        "message": response.message,
        "analyst_summary": response.analyst_summary,
        "analyst_response": response.analyst_response.model_dump() if response.analyst_response else None,
    }
    return json.dumps(payload)


def test_get_demo_scenarios_returns_all_stage3jd_scenarios() -> None:
    payload = list_demo_scenario_fixtures()

    scenario_ids = {item["scenario_id"] for item in payload["scenarios"]}
    assert payload["demo_mode"] is True
    assert payload["evidence_origin"] == "coe_synthetic_fixture"
    assert payload["no_live_customer_data"] is True
    assert scenario_ids == {
        "failed_login_spike_app01",
        "new_source_ip_logins",
        "successful_login_after_failures",
        "brute_force_sop_guidance",
        "failed_login_playbook",
        "account_lockouts_over_time_spl",
        "mitre_mapping_auth_alert",
        "airgapped_no_saia_success_after_failures",
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


def test_failed_login_spike_includes_t1110_and_source_refs() -> None:
    response = _run("failed_login_spike_app01")

    assert response.structured_context is not None
    assert response.source_evidence
    assert any(row.get("index") == "pgcil_soc" and row.get("sourcetype") == "pgcil:auth" for ev in response.source_evidence for row in ev.preview_rows)
    assert any(candidate.get("technique_id") == "T1110" and candidate.get("support") == "supported" for candidate in response.structured_context.mitre_candidates)
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
    assert response.execution.executed_spl is None
    assert response.analyst_response is not None
    assert response.analyst_response.spl_code is not None
    assert "match(_raw, \"action=failure\")" in response.analyst_response.spl_code
    assert "match(_raw, \"action=success\")" in response.analyst_response.spl_code


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
    for term in ("workflow", "routing", "SourceEvidence", "StructuredContext", "not_started"):
        assert term.lower() not in visible.lower()


def test_airgapped_demo_has_no_saia_and_fallback_active() -> None:
    response = _run("airgapped_no_saia_success_after_failures")

    assert response.saia_available is False
    assert response.fallback_active is True
    assert response.candidate_spl is not None
    assert response.candidate_spl.fallback_required is True
    assert response.structured_context is not None
    assert response.structured_context.fallback_mode is True
    assert response.spl_validation is not None
    assert response.spl_validation.capability_profile is not None
    assert response.spl_validation.capability_profile["mcp_available"] is True


def test_mitre_mapping_uses_alert_fixture_not_empty_guess() -> None:
    response = _run("mitre_mapping_auth_alert")

    assert response.user_query is not None
    assert "signature=brute_force_success_after_failures" in response.user_query
    assert response.candidate_spl is None
    assert response.structured_context is not None
    mitre = response.structured_context.mitre_candidates
    assert any(item.get("technique_id") == "T1110" and item.get("support") == "supported" for item in mitre)
    assert any(item.get("technique_id") == "T1078" and item.get("support") == "analyst_review" for item in mitre)
    assert response.structured_context.structured_facts
