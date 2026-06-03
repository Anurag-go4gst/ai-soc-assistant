from __future__ import annotations

from app.chat.pipeline import _candidate_spl_stage
from app.safeguards.spl_slot_binding_validator import validate_spl_slot_bindings
from app.safeguards.spl_validator import validate_spl


VALID_24H_TSTATS = (
    "tstats summariesonly=true count as failed_login_count "
    "from datamodel=Authentication.Authentication "
    "where earliest=-24h latest=now Authentication.action=failure "
    "by Authentication.user | head 25"
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
