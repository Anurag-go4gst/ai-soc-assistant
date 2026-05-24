from __future__ import annotations

from app.api.routes_scenarios import list_demo_scenario_fixtures, run_demo_scenario_fixture


def _run(scenario_id: str):
    return run_demo_scenario_fixture(scenario_id)


def test_get_demo_scenarios_returns_all_stage3jd_scenarios() -> None:
    payload = list_demo_scenario_fixtures()

    scenario_ids = {item["scenario_id"] for item in payload["scenarios"]}
    assert payload["demo_mode"] is True
    assert payload["evidence_origin"] == "coe_synthetic_fixture"
    assert payload["no_live_customer_data"] is True
    assert scenario_ids == {
        "failed_login_spike_app01",
        "successful_login_after_failures",
        "brute_force_sop_guidance",
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


def test_failed_login_spike_includes_t1110_and_source_refs() -> None:
    response = _run("failed_login_spike_app01")

    assert response.structured_context is not None
    assert response.source_evidence
    assert any(row.get("index") == "pgcil_soc" and row.get("sourcetype") == "pgcil:auth" for ev in response.source_evidence for row in ev.preview_rows)
    assert any(candidate.get("technique_id") == "T1110" and candidate.get("support") == "supported" for candidate in response.structured_context.mitre_candidates)
    assert all(fact.source_refs for fact in response.structured_context.structured_facts)


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


def test_sop_demo_does_not_generate_spl() -> None:
    response = _run("brute_force_sop_guidance")

    assert response.selected_skill == "knowledge_recall"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "knowledge_only_answer"


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
