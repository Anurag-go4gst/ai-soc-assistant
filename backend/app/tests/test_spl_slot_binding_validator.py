from __future__ import annotations

from unittest.mock import patch

from app.chat.pipeline import _candidate_from_default_template, _candidate_spl_stage
from app.safeguards.spl_slot_binding_validator import validate_spl_slot_bindings
from app.safeguards.spl_validator import validate_spl
from app.spl.spl_slot_binding_validator import (
    escape_spl_quoted_string,
    extract_query_slots,
    load_slot_binding_policy,
    validate_slot_map,
    validate_slot_value,
    validate_template_query_slots,
)
from app.spl.spl_generation_safety import assess_post_render_spl_quality
from app.spl.template_query_bindings import customize_template_spl


VALID_24H_TSTATS = (
    "tstats summariesonly=true count as failed_login_count "
    "from datamodel=Authentication.Authentication "
    "where earliest=-24h latest=now Authentication.action=failure "
    "by Authentication.user | head 25"
)

_BASE_AUTH_TEMPLATE = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    "(action=failure OR action=success) | stats count by user | head 100"
)


def test_slot_binding_accepts_spl_with_requested_slots() -> None:
    validation = validate_spl(VALID_24H_TSTATS)
    result = validate_spl_slot_bindings(
        validation,
        user_query="Show top 25 users with failed login count in the last 24 hours",
        query_signals={"time_window_24h": True, "top_n": 25},
        template_id="sample_auth_failed_login_top_users_tstats",
    )
    assert result["approved"] is True
    assert result["normalized_spl"] == VALID_24H_TSTATS
    assert "slot_binding_validated" in result["warnings"]


def test_slot_binding_rejects_missing_last_24h() -> None:
    validation = validate_spl(
        VALID_24H_TSTATS.replace("earliest=-24h", "earliest=-60m")
    )
    result = validate_spl_slot_bindings(
        validation,
        user_query="Show top users with failed login count in the last 24 hours",
        query_signals={"time_window_24h": True},
        template_id="sample_auth_failed_login_top_users_tstats",
    )
    assert result["approved"] is False
    assert result["normalized_spl"] is None
    assert "missing_binding:last_24h" in result["reject_reasons"]


def test_slot_binding_rejects_missing_service_account_exclusion() -> None:
    validation = validate_spl(VALID_24H_TSTATS)
    result = validate_spl_slot_bindings(
        validation,
        user_query="Show top users with failed login count in the last 24 hours and exclude service accounts",
        query_signals={"time_window_24h": True, "exclude_service_accounts": True},
        template_id="sample_auth_failed_login_top_users_tstats",
    )
    assert result["approved"] is False
    assert "missing_binding:exclude_service_accounts" in result["reject_reasons"]


def test_slot_binding_rejects_missing_template_for_requested_constraints() -> None:
    validation = validate_spl(VALID_24H_TSTATS)
    result = validate_spl_slot_bindings(
        validation,
        user_query="Show top users with failed login count in the last 24 hours",
        query_signals={"time_window_24h": True},
        template_id=None,
    )
    assert result["approved"] is False
    assert "missing_template_for_slot_binding" in result["reject_reasons"]


def test_candidate_spl_stage_slot_binding_is_flag_gated() -> None:
    _, default_validation = _candidate_spl_stage(
        trace_id="slot-default",
        skill="attack_discovery",
        user_query="Show top users with failed login count in the last 24 hours",
        query_signals={"time_window_24h": True},
        template_id="sample_auth_failed_login_top_users_tstats",
        slot_binding_enabled=False,
    )
    _, gated_validation = _candidate_spl_stage(
        trace_id="slot-gated",
        skill="attack_discovery",
        user_query="Show top users with failed login count in the last 24 hours",
        query_signals={"time_window_24h": True},
        template_id="sample_auth_failed_login_top_users_tstats",
        slot_binding_enabled=True,
    )
    assert default_validation is not None
    assert gated_validation is not None
    assert default_validation["approved"] is True
    assert gated_validation["approved"] is False
    assert "missing_binding:last_24h" in gated_validation["reject_reasons"]


def test_malicious_host_slot_is_rejected() -> None:
    outcome = validate_template_query_slots(
        "auth_success_after_failure",
        'Generate SPL on host="server1\\" | delete | search *"',
    )
    assert outcome.valid is False
    assert any("slot_injection_blocked" in reason for reason in outcome.reject_reasons)


def test_malicious_user_slot_is_rejected() -> None:
    outcome = validate_slot_map({"user": 'admin" | delete | search *'})
    assert outcome.valid is False
    assert "slot_injection_blocked:user" in outcome.reject_reasons


def test_index_and_sourcetype_must_be_allowlisted() -> None:
    index_outcome = validate_slot_map({"index": "secret_index"})
    sourcetype_outcome = validate_slot_map({"sourcetype": "secret:logs"})
    assert index_outcome.valid is False
    assert "slot_index_not_allowlisted" in index_outcome.reject_reasons
    assert sourcetype_outcome.valid is False
    assert "slot_sourcetype_not_allowlisted" in sourcetype_outcome.reject_reasons


def test_allowlisted_index_and_sourcetype_pass() -> None:
    outcome = validate_slot_map(
        {"index": "pgcil_soc", "sourcetype": "pgcil:auth"},
        allowed_indexes=("pgcil_soc",),
        allowed_sourcetypes=("pgcil:auth",),
    )
    assert outcome.valid is True
    assert outcome.normalized_slots["index"] == "pgcil_soc"
    assert outcome.normalized_slots["sourcetype"] == "pgcil:auth"


def test_ip_and_cidr_slots_must_parse() -> None:
    valid = validate_slot_map({"src_ip": "10.1.2.3", "cidr": "10.0.0.0/8"})
    invalid = validate_slot_map({"dest_ip": "not-an-ip", "cidr": "bad-cidr"})
    assert valid.valid is True
    assert invalid.valid is False
    assert "slot_ip_invalid:dest_ip" in invalid.reject_reasons
    assert any(reason.startswith("slot_cidr_invalid") for reason in invalid.reject_reasons)


def test_numeric_threshold_must_parse_as_numeric() -> None:
    valid = validate_slot_map({"threshold": "25", "result_limit": "100"})
    invalid = validate_slot_map({"threshold": "many"})
    assert valid.valid is True
    assert invalid.valid is False
    assert "slot_threshold_not_numeric" in invalid.reject_reasons


def test_time_window_must_be_bounded() -> None:
    valid = validate_slot_map({"time_window": "earliest=-24h latest=now"})
    invalid = validate_slot_map({"time_window": "all time"})
    assert valid.valid is True
    assert invalid.valid is False
    assert "slot_time_window_unbounded" in invalid.reject_reasons


def test_llm_generated_malicious_slot_is_rejected() -> None:
    outcome = validate_slot_map(
        {"host": 'evil" | delete | search *'},
        slot_source="llm",
    )
    assert outcome.valid is False
    assert "llm_slot_rejected" in outcome.reject_reasons


def test_valid_slots_render_expected_spl() -> None:
    query = "Generate SPL for successful login after failures on host=APP-01"
    outcome = validate_template_query_slots("auth_success_after_failure", query)
    assert outcome.valid is True
    spl = customize_template_spl(
        "auth_success_after_failure",
        _BASE_AUTH_TEMPLATE,
        query,
        normalized_slots=outcome.normalized_slots,
    )
    assert 'host="APP-01"' in spl
    assert "index=pgcil_soc" in spl


def test_failed_slot_validation_produces_clarification_not_candidate_spl() -> None:
    candidate, validation = _candidate_spl_stage(
        trace_id="slot-injection",
        skill="attack_discovery",
        user_query='Generate SPL on host="server1\\" | delete | search *"',
        template_id="auth_success_after_failure",
        use_case_id="auth_success_after_failure",
    )
    assert candidate is not None
    assert validation is not None
    assert candidate["generation_mode"] == "clarification_required"
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert "slot_validation_failed" in validation["reject_reasons"]


def test_escape_spl_quoted_string_doubles_quotes_and_backslashes() -> None:
    assert escape_spl_quoted_string('app"01') == 'app\\"01'
    assert escape_spl_quoted_string("app\\01") == "app\\\\01"


def test_extract_query_slots_finds_host_user_and_time_window() -> None:
    slots = extract_query_slots(
        "Show failed logins for user=jdoe on host=APP-01 in the last 24 hours top 25"
    )
    assert slots["user"] == "jdoe"
    assert slots["host"] == "APP-01"
    assert slots["time_window"] == "earliest=-24h latest=now"
    assert slots["result_limit"] == "25"


def test_validate_slot_value_rejects_injection_fragments() -> None:
    policy = load_slot_binding_policy()
    value, errors = validate_slot_value(
        "host",
        "server1 | delete",
        allowed_indexes=("pgcil_soc",),
        allowed_sourcetypes=("pgcil:auth",),
        policy=policy,
    )
    assert value is None
    assert "slot_injection_blocked:host" in errors


def test_slot_rejects_backtick_and_subsearch_injection() -> None:
    for payload in (
        {"host": "srv`whoami"},
        {"user": "admin[search index=*]"},
    ):
        outcome = validate_slot_map(payload)
        assert outcome.valid is False
        assert any("slot_injection_blocked" in reason for reason in outcome.reject_reasons)


def test_invalid_slot_blocks_rendering_before_validate_spl() -> None:
    with patch("app.chat.pipeline.validate_spl") as mock_validate_spl:
        result = _candidate_from_default_template(
            trace_id="pre-render-block",
            skill="attack_discovery",
            user_query='Generate SPL on host="server1\\" | delete | search *"',
            template_id="auth_success_after_failure",
        )
    assert result is not None
    candidate, validation = result
    assert candidate["generation_mode"] == "clarification_required"
    assert candidate["candidate_spl"] == ""
    rendered_calls = [
        call.args[0]
        for call in mock_validate_spl.call_args_list
        if call.args and str(call.args[0]).strip()
    ]
    assert rendered_calls == []
    assert validation["approved"] is False


def test_tstats_without_summariesonly_is_blocked_by_validator() -> None:
    spl = (
        "tstats count from datamodel=Authentication.Authentication "
        "where earliest=-24h latest=now by Authentication.user | head 25"
    )
    validation = validate_spl(spl)
    assert validation["approved"] is False
    assert "summariesonly_required" in validation["reject_reasons"]


def test_tstats_without_summariesonly_marks_review_required_in_quality_lint() -> None:
    spl = (
        "tstats count from datamodel=Authentication.Authentication "
        "where earliest=-24h latest=now by Authentication.user | head 25"
    )
    quality = assess_post_render_spl_quality(spl)
    assert "tstats_summariesonly_missing" in quality["quality_review_reasons"]


def test_valid_template_render_includes_mcp_rbac_readiness_metadata() -> None:
    candidate, validation = _candidate_from_default_template(
        trace_id="readiness-meta",
        skill="attack_discovery",
        user_query="Generate SPL for successful login after failures on host=APP-01",
        template_id="auth_success_after_failure",
    )
    assert candidate is not None
    assert validation is not None
    assert validation["requires_mcp_identity_rbac_check"] is True
    assert validation["mcp_execution_enabled"] is False
    assert validation["execution_eligible"] is False
    assert candidate["execution_eligible"] is False
