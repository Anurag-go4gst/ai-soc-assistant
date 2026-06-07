"""Stage 3L-S3.3A: Route authority fallback harness (no production authority)."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes_chat import chat
from app.api.routes_scenarios import run_demo_scenario_fixture
from app.config import ConfigError, Settings, _validate
from app.routing.intent_operation_bridge_shadow import BRIDGE_STATUS_INCOMPATIBLE
from app.routing.route_authority_allowlist import (
    ALLOWLISTABLE_COVERAGE_IDS,
    COV_Q046_PILOT_COVERAGE_ID,
    parse_route_authority_coverage_allowlist,
    validate_allowlist_ids,
)
from app.routing.route_authority_gate import (
    BLOCKED_COVERAGE_Q007,
    FALLBACK_BRIDGE_INCOMPATIBLE,
    FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED,
    FALLBACK_GLOBAL_KILL_SWITCH_DISABLED,
    FALLBACK_MISSING_THRESHOLD_REF,
    FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW,
    FALLBACK_VALIDATOR_BLOCKED,
    FALLBACK_BLOCKED_DETECTION_DEPENDENT,
    FALLBACK_BLOCKED_PRIMARY_FIXTURE_ABSENT,
    evaluate_route_authority,
)
from app.schemas.requests import ChatRequest
from app.tests.test_route_plan_stage3k_r2 import (
    _patch_common_chat_dependencies,
    _valid_route_plan_candidate,
)


def _shadow_with_bridge(
    *,
    primary_skill: str | None = "aggregate_and_rank",
    bridge_status: str = "compatible",
    compatible: bool = True,
    normalized: bool = True,
    route_status: str = "route_ready",
    route_plan_parameters: dict[str, Any] | None = None,
    pattern_id: str = "top_failed_okta_login_users",
) -> dict[str, Any]:
    return {
        "primary_skill": primary_skill,
        "pattern_id": pattern_id,
        "normalized_plan_available": normalized,
        "candidate_available": normalized,
        "route_status": route_status,
        "validation_result": {"is_valid": normalized},
        "route_plan_parameters": route_plan_parameters or {},
        "intent_operation_bridge": {
            "bridge_status": bridge_status,
            "compatible": compatible,
            "disagreements": [] if compatible else [{"field": "intent_to_operation_bridge"}],
        },
    }


def _enable_pilot_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_authoritative_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )


@pytest.mark.parametrize(
    ("primary_skill", "coverage_id", "expected_reason"),
    [
        ("entity_context_lookup", None, FALLBACK_BLOCKED_PRIMARY_FIXTURE_ABSENT),
        ("notable_risk_lookup", None, FALLBACK_BLOCKED_PRIMARY_FIXTURE_ABSENT),
        (None, BLOCKED_COVERAGE_Q007, FALLBACK_BLOCKED_DETECTION_DEPENDENT),
    ],
)
def test_blocked_primary_and_detection_rows_not_authority_eligible(
    monkeypatch: pytest.MonkeyPatch,
    primary_skill: str | None,
    coverage_id: str | None,
    expected_reason: str,
) -> None:
    _enable_pilot_authority(monkeypatch)
    shadow = _shadow_with_bridge(
        primary_skill=primary_skill or "aggregate_and_rank",
        pattern_id="dga_dns_queries" if coverage_id else "top_failed_okta_login_users",
    )
    result = evaluate_route_authority(
        selected_skill="attack_discovery",
        route_plan_shadow=shadow,
        coverage_id=coverage_id,
    )
    assert result.authority_applied is False
    assert result.authority_fallback_reason == expected_reason


def test_allowlist_rejects_non_q046_ids() -> None:
    with pytest.raises(ValueError, match="disallowed coverage_id"):
        validate_allowlist_ids(frozenset({COV_Q046_PILOT_COVERAGE_ID, "cov.other.id"}))


def test_config_validate_rejects_disallowed_allowlist_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST", "cov.other.id")
    with pytest.raises(ConfigError, match="disallowed coverage_id"):
        _validate(Settings())


def test_a_bridge_incompatible_preserves_selected_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    candidate = _valid_route_plan_candidate()
    candidate["primary_skill"] = "metadata_discovery"
    candidate["operation_type"] = "metadata_query"
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: candidate)

    response = chat(ChatRequest(message="Top users failed logins in the last hour."))

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["authority_fallback_reason"] == FALLBACK_BRIDGE_INCOMPATIBLE
    assert compare["operation_authoritative_applied"] is False


def test_b_validator_blocks_preserves_selected_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    invalid = _valid_route_plan_candidate()
    invalid["parameters"].pop("group_by")
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: invalid)

    response = chat(ChatRequest(message="Top users failed logins in the last hour."))

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["authority_fallback_reason"] == FALLBACK_VALIDATOR_BLOCKED
    assert compare["operation_authoritative_applied"] is False


def test_c_not_on_allowlist_preserves_selected_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_coverage_allowlist",
        "",
    )
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _valid_route_plan_candidate(),
    )

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in 24h."))

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["authority_fallback_reason"] == FALLBACK_COVERAGE_ID_NOT_ALLOWLISTED
    assert compare["operation_authoritative_applied"] is False


def test_d_global_kill_switch_preserves_selected_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_authoritative_enabled",
        False,
    )
    monkeypatch.setattr(
        "app.config.settings.route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    monkeypatch.setattr(
        "app.api.routes_chat._route_plan_shadow_candidate",
        lambda query: _valid_route_plan_candidate(),
    )

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in 24h."))

    assert response.selected_skill == "attack_discovery"
    assert response.message == "Governed SPL draft ready. It has passed deterministic validation and has not been executed."
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["authority_fallback_reason"] == FALLBACK_GLOBAL_KILL_SWITCH_DISABLED
    assert compare["operation_authoritative_applied"] is False


def test_e_missing_threshold_ref_fallback_never_applies_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    _patch_common_chat_dependencies(monkeypatch, skill="attack_discovery")
    candidate = _valid_route_plan_candidate()
    monkeypatch.setattr("app.api.routes_chat._route_plan_shadow_candidate", lambda query: candidate)

    response = chat(ChatRequest(message="Find top 10 users with failed Okta logins in 24h."))

    assert response.selected_skill == "attack_discovery"
    compare = response.route_plan_shadow.route_authority_compare
    assert compare["coverage_id_resolved"] == COV_Q046_PILOT_COVERAGE_ID
    assert compare["authority_fallback_reason"] == FALLBACK_MISSING_THRESHOLD_REF
    assert compare["operation_authoritative_applied"] is False


def test_cov_q046_full_gate_pass_still_shadow_only_in_production_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_pilot_authority(monkeypatch)
    shadow = _shadow_with_bridge(
        route_plan_parameters={
            "threshold_ref": {"policy_id": "analyst_defined"},
            "time_window": "last_24_hours",
        },
    )
    result = evaluate_route_authority(
        selected_skill="attack_discovery",
        route_plan_shadow=shadow,
        coverage_id=COV_Q046_PILOT_COVERAGE_ID,
    )
    assert result.authority_applied is True
    assert result.authority_fallback_reason is None


def test_unit_bridge_incompatible_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    shadow = _shadow_with_bridge(bridge_status=BRIDGE_STATUS_INCOMPATIBLE, compatible=False)
    result = evaluate_route_authority(
        selected_skill="attack_discovery",
        route_plan_shadow=shadow,
        coverage_id=COV_Q046_PILOT_COVERAGE_ID,
    )
    assert result.authority_fallback_reason == FALLBACK_BRIDGE_INCOMPATIBLE
    assert result.authority_applied is False


def test_unit_no_validated_route_plan_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot_authority(monkeypatch)
    shadow = _shadow_with_bridge(primary_skill=None, normalized=False, route_status="no_candidate")
    shadow["normalized_plan_available"] = False
    shadow["candidate_available"] = False
    result = evaluate_route_authority(
        selected_skill="knowledge_recall",
        route_plan_shadow=shadow,
        coverage_id=COV_Q046_PILOT_COVERAGE_ID,
    )
    assert result.authority_fallback_reason == FALLBACK_NO_VALIDATED_ROUTE_PLAN_SHADOW


def test_experience_center_unchanged() -> None:
    response = run_demo_scenario_fixture("failed_login_spike_app01")
    assert response.route_plan_shadow is None


def test_default_allowlist_empty() -> None:
    assert parse_route_authority_coverage_allowlist("") == frozenset()
    assert COV_Q046_PILOT_COVERAGE_ID in ALLOWLISTABLE_COVERAGE_IDS
    assert "cov.q002.top_outbound_source_ips" in ALLOWLISTABLE_COVERAGE_IDS
    assert "cov.q007.dga_detection_binding" not in ALLOWLISTABLE_COVERAGE_IDS
