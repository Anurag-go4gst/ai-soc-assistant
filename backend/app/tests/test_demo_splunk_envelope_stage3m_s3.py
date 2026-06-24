"""Stage 3M-S3: Experience Center demo SplunkResultEnvelope wiring."""

from __future__ import annotations

import json

from app.api.routes_scenarios import run_demo_scenario_fixture
from app.demo.mcp_result_envelope import demo_envelope_from_rows
from app.demo.scenarios import _mock_rows_for


def test_demo_envelope_from_rows_fixture_origin() -> None:
    rows = _mock_rows_for("fixture")
    envelope = demo_envelope_from_rows(rows, trace_id="demo-trace")
    assert envelope.origin == "fixture"
    assert envelope.schema_confirmed is False
    assert envelope.schema_confirmed_reason == "fixture_adapter"
    assert envelope.row_count == 3


# The mock-execution lockout demo (account_lockouts_over_time_spl) was removed in the
# 2026-06-24 EC curation (curated set is execution-disabled). The fixture-envelope
# mechanism it exercised is verified directly below from the same `_mock_rows_for` source.


def test_lockout_fixture_rows_carry_envelope() -> None:
    from app.demo.mcp_result_envelope import execution_fields_from_envelope

    rows = _mock_rows_for("fixture")
    envelope = demo_envelope_from_rows(
        rows, trace_id="demo-trace", normalized_spl="index=pgcil_soc action=lockout"
    )
    result_count, results_preview, envelope_dict = execution_fields_from_envelope(envelope)
    assert envelope_dict["origin"] == "fixture"
    assert envelope_dict["schema_confirmed"] is False
    assert result_count == 3
    assert len(results_preview) == 3
    assert results_preview[0]["action"] == "lockout"


def test_failed_login_visible_analyst_text_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    visible = json.dumps(
        {
            "message": response.message,
            "analyst_summary": response.analyst_summary,
            "finding_title": response.analyst_response.finding_title if response.analyst_response else None,
            "one_sentence_finding": response.analyst_response.one_sentence_finding if response.analyst_response else None,
            "splunk_results_table": response.analyst_response.splunk_results_table if response.analyst_response else [],
        }
    )
    assert "Brute-force authentication spike detected on APP-01" in visible
    assert "101 failed logins" in visible
    assert "T1110.001" in visible
    assert "10.10.4.21" in visible


def test_demo_response_has_no_route_plan_shadow() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.route_plan_shadow is None
