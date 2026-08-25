"""Tests for SPL intent spec and semantic fidelity validation."""

from __future__ import annotations

from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity


def test_case1_intent_spec_firewall_30d() -> None:
    query = "give me a spl command to get all the firewall logs for last 30 days"
    spec = build_spl_intent_spec(query)
    assert spec["event_domain"] == "firewall"
    assert "all_events_no_action_filter" in spec["filters"]
    assert spec["time_window"] == "earliest=-30d latest=now"
    assert spec["result_limit"] is None


def test_case2_intent_spec_denied_top_src_ip_24h() -> None:
    query = (
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    )
    spec = build_spl_intent_spec(query)
    assert spec["event_domain"] == "firewall"
    assert "denied_traffic" in spec["filters"]
    assert "src_ip" in spec["group_by"]
    assert "count" in spec["aggregations"]
    assert spec["time_window"] == "earliest=-24h latest=now"


def test_semantic_fidelity_detects_missing_denied_and_aggregation() -> None:
    query = (
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    )
    spec = build_spl_intent_spec(query)
    spl = (
        "search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now "
        "| table _time src_ip | head 100"
    )
    result = validate_semantic_fidelity(spec, spl)
    assert result["passed"] is False
    assert "denied_traffic" in result["losses"]
    assert "aggregation" in result["losses"]


def test_semantic_fidelity_passes_denied_top_query() -> None:
    query = (
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    )
    spec = build_spl_intent_spec(query)
    spl = """
search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now
(action=denied OR action=blocked)
| stats count as event_count by src_ip
| sort - event_count
| head 10
"""
    result = validate_semantic_fidelity(spec, spl)
    assert result["passed"] is True


def test_semantic_fidelity_flags_arbitrary_head_on_all_logs() -> None:
    query = "give me a spl command to get all the firewall logs for last 30 days"
    spec = build_spl_intent_spec(query)
    spl = "search index=fw earliest=-30d latest=now | head 100"
    result = validate_semantic_fidelity(spec, spl)
    assert "arbitrary_head_100" in result["losses"]
