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


def test_lockout_demo_execution_carries_envelope() -> None:
    from app.demo.scenarios import run_demo_scenario

    payload = run_demo_scenario("account_lockouts_over_time_spl")
    assert "splunk_result_envelope" in payload["execution"]
    assert payload["execution"]["splunk_result_envelope"]["origin"] == "fixture"
    assert payload["execution"]["splunk_result_envelope"]["schema_confirmed"] is False
    assert len(payload["execution"]["results_preview"]) == 3


def test_splunk_mcp_source_evidence_normalized_via_envelope() -> None:
    from app.demo.scenarios import run_demo_scenario

    payload = run_demo_scenario("account_lockouts_over_time_spl")
    splunk = next(item for item in payload["source_evidence"] if item["source_type"] == "splunk_mcp")
    assert splunk["result_count"] == 3
    assert "_time" in splunk["fields_returned"]
    assert "schema_unconfirmed:fixture_adapter" in splunk["warnings"]
    assert splunk["preview_rows"][0]["action"] == "lockout"


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
