from __future__ import annotations

from copy import deepcopy

from app.routing.route_plan_models import (
    ROUTE_PLAN_GENERATOR_MODEL_FAMILY,
    ROUTE_PLAN_REASONING_MODEL_ALLOWED,
    PreflightContext,
    RouteStatus,
)
from app.routing.route_plan_preflight import preflight_route_plan
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.routing.runtime_skill_catalog import get_runtime_skill_catalog


def test_clean_route_ready_aggregate_plan_passes() -> None:
    candidate = _base_plan(
        primary_skill="aggregate_and_rank",
        pattern_id="top_failed_okta_login_users",
        operation_type="top_n",
        source_class="okta_authentication_logs",
        parameters={
            "event_filter": {"event_type": "failed_login"},
            "group_by": {"field": "user", "source_class": "okta_authentication_logs"},
            "metric": {"type": "count", "field": "failed_login_count"},
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last 24 hours",
            "exclude_entities": "service_accounts",
            "enrichments": ["notable_risk"],
        },
        post_enrichment=["notable_risk_lookup"],
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is True
    plan = result.normalized_route_plan
    assert plan is not None
    assert plan["route_status"] == "route_ready"
    assert plan["primary_skill"] == "aggregate_and_rank"
    assert plan["parameters"]["group_by"]["field"] == "user"
    assert plan["parameters"]["metric"]["field"] == "failed_login_count"
    assert plan["parameters"]["metric"]["type"] == "count"
    assert plan["parameters"]["time_window"] == "last_24_hours"
    assert plan["parameters"]["exclusions"] == [
        {
            "type": "lookup",
            "lookup_name": "service_accounts",
            "lookup_status": "approved",
            "match_field": "user",
        }
    ]
    assert plan["post_enrichment"] == [{"skill": "notable_risk_lookup", "input": "ranked_users"}]
    assert "enrichments" not in plan["parameters"]
    assert "candidate_spl" not in plan
    assert "mcp" not in str(plan).lower()


def test_underspecified_question_preflight_requires_clarification() -> None:
    result = preflight_route_plan("Show me suspicious Okta users.")

    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED
    assert result.is_blocked is True
    assert {"detection_ref", "metric", "time_window"}.issubset(set(result.missing_slots))


def test_missing_notable_context_preflight_requires_notable_id() -> None:
    result = preflight_route_plan("What happened for this notable?")

    assert result.route_status == RouteStatus.CLARIFICATION_REQUIRED
    assert "notable_id" in result.missing_slots
    assert not any("lookup" in finding for finding in result.blocking_findings)


def test_missing_ioc_lookup_blocks_route() -> None:
    result = preflight_route_plan(
        "Which hosts contacted known malicious IPs today?",
        PreflightContext(configured_lookups=set()),
    )

    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP
    assert "lookup_ref" in result.missing_slots


def test_missing_dga_detection_blocks_route() -> None:
    result = preflight_route_plan(
        "Which DNS queries look like DGA activity?",
        PreflightContext(configured_detections=set()),
    )

    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION
    assert "detection_ref" in result.missing_slots


def test_multi_signal_valid_composition_passes() -> None:
    candidate = _base_plan(
        primary_skill="multi_signal_correlation",
        pattern_id="correlate_threshold_and_behavioral_detection",
        operation_type="correlate_signals",
        source_class="identity_and_endpoint",
        parameters={},
        sub_invocations=[
            {"primary_skill": "threshold_anomaly", "parameters": {"metric": {"type": "count", "field": "failed_login_count"}}},
            {"primary_skill": "behavioral_detection_binding", "parameters": {"detection_ref": "soc.impossible_travel.v1"}},
        ],
        post_enrichment=[{"skill": "entity_context_lookup", "input": "sub_results"}],
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is True
    plan = result.normalized_route_plan
    assert plan is not None
    assert len(plan["sub_invocations"]) == 2
    assert not any("sub_invocations" in sub for sub in plan["sub_invocations"])


def test_invalid_nested_composition_is_blocked() -> None:
    candidate = _base_plan(
        primary_skill="multi_signal_correlation",
        operation_type="correlate_signals",
        parameters={},
        sub_invocations=[
            {
                "primary_skill": "multi_signal_correlation",
                "sub_invocations": [{"primary_skill": "threshold_anomaly"}],
            }
        ],
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert result.normalized_route_plan is not None
    assert result.normalized_route_plan["route_status"] == "blocked_invalid_composition"
    assert "nested_multi_signal_correlation_rejected" in result.blocking_findings
    assert "nested_sub_invocations_rejected" in result.blocking_findings


def test_sub_invocations_under_non_multi_signal_are_blocked() -> None:
    candidate = _valid_aggregate_plan()
    candidate["sub_invocations"] = [{"primary_skill": "threshold_anomaly"}]

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert result.normalized_route_plan is not None
    assert result.normalized_route_plan["route_status"] == "blocked_invalid_composition"
    assert "sub_invocations_not_allowed_for_skill:aggregate_and_rank" in result.blocking_findings


def test_sequence_detection_primary_route_plan_passes() -> None:
    """Stage 3L-S1 exit gate: first primary route plan for sequence_detection (success-after-failure class)."""
    candidate = _base_plan(
        primary_skill="sequence_detection",
        pattern_id="auth_success_after_failure",
        operation_type="sequence_match",
        source_class="okta_authentication_logs",
        parameters={
            "detection_ref": "soc.impossible_travel.v1",
            "time_window": "last_24_hours",
        },
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is True
    plan = result.normalized_route_plan
    assert plan is not None
    assert plan["primary_skill"] == "sequence_detection"
    assert plan["operation_type"] == "sequence_match"


def test_operation_type_not_allowed_for_skill_is_blocked() -> None:
    candidate = _valid_aggregate_plan()
    candidate["operation_type"] = "ioc_correlation"

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert "operation_type_not_allowed_for_skill:aggregate_and_rank:ioc_correlation" in result.blocking_findings


def test_metadata_discovery_post_enrichment_blocked() -> None:
    candidate = _base_plan(
        primary_skill="metadata_discovery",
        pattern_id="discover_okta_fields",
        operation_type="field_discovery",
        source_class="okta_authentication_logs",
        parameters={},
        post_enrichment=[{"skill": "behavioral_detection_binding", "input": "fields"}],
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert result.normalized_route_plan is not None
    assert result.normalized_route_plan["route_status"] == "blocked_invalid_composition"
    assert "post_enrichment_not_allowed:metadata_discovery->behavioral_detection_binding" in result.blocking_findings


def test_confidence_ignored_for_invalid_plan() -> None:
    candidate = _valid_aggregate_plan()
    candidate["primary_skill"] = "llm_action_chain"
    candidate["model_advisory_metadata"] = {"model_self_reported_confidence": "high"}

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert any(
        finding in result.blocking_findings
        for finding in (
            "unknown_primary_skill:llm_action_chain",
            "open_operation_forbidden_marker:llm_",
            "open_operation_forbidden_marker:action_chain",
        )
    )
    assert "model_self_reported_confidence_ignored_for_validation" in result.validation_findings
    assert "model_self_reported_confidence_is_advisory_only" in result.warnings


def test_group_by_metric_confusion_blocked() -> None:
    candidate = _base_plan(
        primary_skill="aggregate_and_rank",
        pattern_id="top_source_ips",
        operation_type="top_n",
        parameters={
            "metric": {"type": "distinct_count", "field": "src_ip"},
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last hour",
        },
    )

    result = validate_route_plan_candidate(candidate)

    assert result.is_valid is False
    assert result.normalized_route_plan is not None
    assert result.normalized_route_plan["route_status"] == "blocked_invalid_parameters"
    assert "missing_required_slot:group_by" in result.blocking_findings
    assert "aggregate_and_rank_requires_group_by" in result.blocking_findings
    assert "metric_field_must_not_be_grouping_only_descriptor" in result.blocking_findings


def test_route_plan_generator_defaults_to_instruct_not_reasoning() -> None:
    assert ROUTE_PLAN_GENERATOR_MODEL_FAMILY == "instruct"
    assert ROUTE_PLAN_REASONING_MODEL_ALLOWED is False


def test_compact_runtime_skill_catalog_contract_contains_ten_skills() -> None:
    catalog = get_runtime_skill_catalog()

    assert set(catalog) == {
        "aggregate_and_rank",
        "threshold_anomaly",
        "sequence_detection",
        "lookup_correlation",
        "behavioral_detection_binding",
        "metadata_discovery",
        "entity_context_lookup",
        "notable_risk_lookup",
        "multi_signal_correlation",
        "entity_timeline",
    }
    for contract in catalog.values():
        assert {
            "skill_id",
            "purpose",
            "allowed_operation_types",
            "required_slots",
            "optional_slots",
            "hard_preconditions",
            "allowed_post_enrichments",
            "allows_sub_invocations",
            "governance_constraints",
            "examples",
            "non_examples",
        }.issubset(contract)


def _valid_aggregate_plan() -> dict:
    return _base_plan(
        primary_skill="aggregate_and_rank",
        pattern_id="top_failed_okta_login_users",
        operation_type="top_n",
        source_class="okta_authentication_logs",
        parameters={
            "group_by": {"field": "user", "source_class": "okta_authentication_logs"},
            "metric": {"type": "count", "field": "failed_login_count"},
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
    )


def _base_plan(
    *,
    primary_skill: str,
    pattern_id: str = "test_pattern",
    operation_type: str = "top_n",
    domain: str = "soc",
    source_class: str = "okta_authentication_logs",
    parameters: dict | None = None,
    sub_invocations: list[dict] | None = None,
    post_enrichment: list | None = None,
) -> dict:
    plan = {
        "route_plan_id": "rp_test_001",
        "route_status": "route_ready",
        "primary_skill": primary_skill,
        "pattern_id": pattern_id,
        "operation_type": operation_type,
        "domain": domain,
        "source_class": source_class,
        "entities": ["user"],
        "time_window": "last 24 hours",
        "parameters": deepcopy(parameters or {}),
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {"validator": "stage3k_r1"},
        "post_enrichment": deepcopy(post_enrichment or []),
    }
    if sub_invocations is not None:
        plan["sub_invocations"] = deepcopy(sub_invocations)
    return plan
