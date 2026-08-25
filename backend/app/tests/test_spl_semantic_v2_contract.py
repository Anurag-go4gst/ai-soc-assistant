"""S1 — SPL semantic V2 contract evolution around build_spl_intent_spec()."""

from __future__ import annotations

from app.spl.spl_intent_spec import (
    SPL_SEMANTIC_CONTRACT_VERSION,
    SUPPORTED_ANALYSIS_SHAPES,
    UNSUPPORTED_ANALYSIS_SHAPES,
    build_spl_intent_spec,
    spl_intent_spec_for_prompt,
)


def test_contract_version_and_supported_shapes() -> None:
    spec = build_spl_intent_spec("show all firewall events")
    assert spec["contract_version"] == SPL_SEMANTIC_CONTRACT_VERSION
    assert spec["contract_version"] == "spl_semantic_v2"
    assert spec["analysis_shape"] in SUPPORTED_ANALYSIS_SHAPES
    assert "comparison" in UNSUPPORTED_ANALYSIS_SHAPES


def test_rolling_distinct_accounts_shape() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    assert spec["analysis_shape"] == "rolling"
    assert spec["analytical_window"] == {
        "kind": "rolling",
        "size": "10m",
        "provenance": "query_token",
    }
    assert spec["search_horizon"] is None  # do not invent implicit 24h
    assert spec["entity_roles"]["subject"] == ["src_ip"]
    assert spec["distinct_by"] == ["user"]
    assert any(item.get("type") == "distinct_count" for item in spec["relationships"])
    assert "arbitrary_head_100" in spec["prohibitions"]
    assert "rolling_window_loss" in spec["prohibitions"]
    assert spec["support_status"] == "supported"


def test_rolling_shape_adjacent_unseen_variant() -> None:
    spec = build_spl_intent_spec(
        "find hosts spraying unique usernames inside a 15 minute rolling window"
    )
    assert spec["analysis_shape"] == "rolling"
    assert spec["analytical_window"]["size"] == "15m"
    assert "user" in spec["distinct_by"]
    assert spec["search_horizon"] is None


def test_hourly_failed_login_trend_shape() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    assert spec["analysis_shape"] == "trend"
    assert spec["temporal_grain"] == "1h"
    assert spec["search_horizon"] == "earliest=-24h latest=now"
    assert spec["time_window"] == spec["search_horizon"]
    assert "failed_login" in spec["required_event_sets"]
    assert spec["output_shape"] == "time_series"
    assert "temporal_grain_loss" in spec["prohibitions"]
    assert "implicit_default_24h_overwrite" in spec["prohibitions"]


def test_trend_shape_adjacent_unseen_variant() -> None:
    spec = build_spl_intent_spec(
        "plot a daily vpn connection-failure time series for the past 7 days"
    )
    assert spec["analysis_shape"] == "trend"
    assert spec["temporal_grain"] == "1d"
    assert spec["search_horizon"] == "earliest=-7d latest=now"
    assert spec["event_domain"] == "vpn"


def test_password_change_then_login_sequence_shape() -> None:
    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    assert spec["analysis_shape"] == "sequence"
    assert spec["ordered_sequence"] == ["password_change", "successful_login"]
    assert spec["sequence_max_gap"] == "5m"
    assert set(spec["required_event_sets"]) == {"password_change", "successful_login"}
    assert spec["analytical_window"]["kind"] == "sequence"
    assert spec["analytical_window"]["size"] == "5m"
    assert "sequence_ordering_loss" in spec["prohibitions"]
    assert "sequence_gap_loss" in spec["prohibitions"]


def test_sequence_shape_adjacent_unseen_variant() -> None:
    spec = build_spl_intent_spec(
        "privilege group change then successful login within 2 minutes"
    )
    assert spec["analysis_shape"] == "sequence"
    assert spec["ordered_sequence"] == ["privilege_change", "successful_login"]
    assert spec["sequence_max_gap"] == "2m"


def test_ranking_and_raw_shapes_preserved() -> None:
    ranked = build_spl_intent_spec(
        "Give me an SPL query to show the top source IPs generating denied firewall "
        "traffic in the last 24 hours."
    )
    assert ranked["analysis_shape"] == "ranking"
    assert ranked["ranking"] == {"direction": "desc", "metric": "count"}
    assert "src_ip" in ranked["group_by"]

    raw = build_spl_intent_spec("give me a spl command to get all the firewall logs for last 30 days")
    assert raw["analysis_shape"] == "raw"
    assert raw["output_shape"] == "events"
    assert raw["result_limit"] is None
    assert "mandatory_aggregation" in raw["prohibitions"]


def test_comparison_shape_fails_closed() -> None:
    spec = build_spl_intent_spec("is this the same campaign as last month")
    assert spec["analysis_shape"] == "comparison"
    assert spec["support_status"] == "unsupported"
    assert spec["degrade_reason"] == "unsupported_comparison_semantics"
    prompt = spl_intent_spec_for_prompt(spec)
    assert "unsupported_comparison_semantics" in prompt
    assert "MITRE" not in prompt or "Do not apply unrelated MITRE" in prompt


def test_locked_rqc_time_scope_wins_over_query_window() -> None:
    spec = build_spl_intent_spec(
        "hourly failed-login trend over the last 24 hours",
        resolved_query_contract={
            "normalized_goal": "hourly failed authentication trend",
            "time_scope": "last 12 hours",
            "locked_fields": {"time_scope": "last 12 hours"},
            "entities": {},
        },
    )
    assert spec["search_horizon"] == "earliest=-12h latest=now"
    assert spec["field_provenance"]["search_horizon"] in {"rqc_locked", "rqc"}
    assert spec["objective"] == "hourly failed authentication trend"
    assert spec["rqc_locked_fields"]["time_scope"] == "last 12 hours"


def test_source_mappings_fill_blanks_only() -> None:
    spec = build_spl_intent_spec(
        "top source IPs last 24 hours index=user_named_index",
        source_mappings={"index": "profile_index", "sourcetype": "auth:sourcetype"},
    )
    assert spec["source_constraints"]["index"] == "user_named_index"
    assert spec["source_constraints"]["sourcetype"] == "auth:sourcetype"
    assert spec["field_provenance"]["source_constraints.sourcetype"] == "source_mapping"


def test_normalization_aliases_declared_when_user_or_src_grouped() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    aliases = {item["alias"] for item in spec["normalization_requirements"]}
    assert "src_ip_norm" in aliases
    assert "user_norm" in aliases
    assert "grouping" in spec["normalization_consumers"]
    assert "distinct" in spec["normalization_consumers"]
    prompt = spl_intent_spec_for_prompt(spec)
    assert "user_norm" in prompt
    assert "MUST be consumed" in prompt
    assert "alert-template" in prompt.lower() or "alert-template" in prompt


def test_prompt_omits_unrelated_authority() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    prompt = spl_intent_spec_for_prompt(spec)
    assert "routing" not in prompt.lower() or "Do not apply unrelated" in prompt
    assert "MCP" in prompt  # prohibition line mentions MCP so the model is told not to use it
    assert "Do not apply unrelated MITRE, remediation, routing, MCP" in prompt
    assert "temporal_grain: 1h" in prompt
    assert "search_horizon: earliest=-24h latest=now" in prompt


def test_no_threshold_invented_when_absent() -> None:
    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    assert spec["explicit_threshold_present"] is False
    assert "unexpected_threshold_invention" in spec["prohibitions"]
    assert not any("threshold" in str(item).lower() for item in spec["measures"])
