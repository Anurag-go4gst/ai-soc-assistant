"""Stage 3K-Q1C deterministic template matcher tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.spl.template_matcher import (
    MISMATCH_AMBIGUOUS,
    MISMATCH_CANNOT_RESOLVE_DATAMODEL,
    MISMATCH_DATAMODEL_MISMATCH,
    MISMATCH_NO_TEMPLATE_FOR_SKILL,
    MISMATCH_RESULT_LIMIT,
    MISMATCH_TIME_WINDOW,
    MISMATCH_UNKNOWN_DATAMODEL,
    MISMATCH_UNSUPPORTED_GROUP_BY,
    MISMATCH_VALIDATOR_PROFILE,
    _extract_match_context,
    _score_template,
    dry_run_matches,
    match_route_plan_to_template,
)
from app.spl.template_registry import SplTemplateDefinition, get_spl_template, load_spl_templates


def _auth_sample_template() -> SplTemplateDefinition:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    return template


def _aggregate_plan_without_time_and_limit(
    *,
    datamodel: str = "Authentication",
    group_by: str = "user",
) -> dict:
    plan = _aggregate_plan(datamodel=datamodel, group_by=group_by)
    plan.pop("time_window", None)
    plan["parameters"].pop("time_window", None)
    plan["parameters"].pop("limit", None)
    return plan


def _aggregate_plan(
    *,
    datamodel: str,
    group_by: str,
    metric_type: str = "count",
    metric_field: str | None = None,
    source_class: str | None = None,
    dataset: str | None = None,
    primary_skill: str = "aggregate_and_rank",
) -> dict:
    metric: dict = {"type": metric_type}
    if metric_field:
        metric["field"] = metric_field
    plan = {
        "route_plan_id": "rp_q1c_test",
        "route_status": "route_ready",
        "primary_skill": primary_skill,
        "pattern_id": "test_pattern",
        "operation_type": "top_n",
        "domain": "soc",
        "source_class": source_class or "okta_authentication_logs",
        "entities": [group_by],
        "time_window": "last_24_hours",
        "parameters": {
            "group_by": {"field": group_by, "source_class": source_class or "okta_authentication_logs"},
            "metric": metric,
            "sort": {"field": "metric_value", "direction": "desc"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
        "evidence_needs": {
            "datamodel": datamodel,
            "group_by": [group_by],
            "metric": metric,
        },
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {"validator": "stage3k_q1c_test"},
        "post_enrichment": [],
        "coe_synthetic_fixture": True,
        "captured_live_run": False,
        "production_execution": False,
    }
    if dataset:
        plan["evidence_needs"]["dataset"] = dataset
    return plan


def test_auth_aggregate_matches_sample_tstats_template() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user", source_class="okta_authentication_logs")
    result = match_route_plan_to_template(plan)

    assert result.matched is True
    assert result.matched_template_id == "sample_auth_failed_login_top_users_tstats"
    assert result.production_executable is False
    assert result.sample_only is True
    assert result.execution_authorized is False
    assert "exact_datamodel_match" in result.match_reasons


def test_explicit_raw_template_id_prefers_active_pgcil_over_cim_sample() -> None:
    plan = _aggregate_plan(datamodel=None, group_by="userIdentity.arn", source_class="aws_cloudtrail")
    plan["pattern_id"] = "aws_security_group_modifications"
    plan["source_class"] = "aws_cloudtrail"
    plan["domain"] = "cloud"
    plan["parameters"]["group_by"] = {"field": "userIdentity.arn"}
    plan["parameters"]["metric"] = {"type": "count", "field": "change_count"}
    plan["evidence_needs"] = {
        "template_id": "aws_security_group_modifications",
        "query_shape": "raw_search",
        "group_by": ["userIdentity.arn"],
        "metric": {"type": "count", "field": "change_count"},
    }
    result = match_route_plan_to_template(plan)

    assert result.matched is True
    assert result.matched_template_id == "aws_security_group_modifications"
    assert result.production_executable is True
    assert result.sample_only is False
    assert "raw_search_template" in result.match_reasons


def test_network_aggregate_matches_sample_tstats_template() -> None:
    plan = _aggregate_plan(
        datamodel="Network_Traffic",
        group_by="src_ip",
        source_class="network_traffic",
        dataset="All_Traffic",
    )
    result = match_route_plan_to_template(plan)

    assert result.matched is True
    assert result.matched_template_id == "sample_network_top_outbound_src_tstats"
    assert result.production_executable is False


def test_dns_aggregate_matches_sample_from_datamodel_template() -> None:
    plan = _aggregate_plan(
        datamodel="Network_Resolution",
        group_by="host",
        source_class="dns_logs",
        dataset="DNS",
    )
    result = match_route_plan_to_template(plan)

    assert result.matched is True
    assert result.matched_template_id == "sample_dns_top_query_hosts_from_datamodel"


def test_unknown_source_without_datamodel_cannot_resolve() -> None:
    plan = {
        "route_plan_id": "rp_q1c_cannot_resolve",
        "route_status": "route_ready",
        "primary_skill": "aggregate_and_rank",
        "pattern_id": "test_pattern",
        "operation_type": "top_n",
        "domain": "soc",
        "source_class": "unknown_source_xyz",
        "entities": ["user"],
        "time_window": "last_24_hours",
        "parameters": {
            "group_by": {"field": "user"},
            "metric": {"type": "count"},
            "limit": 10,
            "time_window": "last_24_hours",
        },
        "evidence_needs": {},
        "missing_slots": [],
        "hard_preconditions": [],
        "model_advisory_metadata": {},
        "deterministic_validation": {"validator": "stage3k_q1c_test"},
        "post_enrichment": [],
    }
    result = match_route_plan_to_template(plan)

    assert result.matched is False
    assert result.mismatch_reasons
    assert MISMATCH_CANNOT_RESOLVE_DATAMODEL in result.mismatch_reasons


def test_datamodel_mismatch_when_template_datamodel_differs() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    ctx = _extract_match_context(plan)
    network_template = get_spl_template("sample_network_top_outbound_src_tstats")
    assert network_template is not None
    _, _, mismatches = _score_template(network_template, ctx)
    assert MISMATCH_DATAMODEL_MISMATCH in mismatches
    assert MISMATCH_UNKNOWN_DATAMODEL not in mismatches


def test_unknown_datamodel_returns_no_match() -> None:
    plan = _aggregate_plan(datamodel="MadeUp", group_by="user")
    result = match_route_plan_to_template(plan)

    assert result.matched is False
    assert result.matched_template_id is None
    assert MISMATCH_UNKNOWN_DATAMODEL in result.mismatch_reasons


def test_unknown_group_by_returns_no_match() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="not_a_cim_field")
    result = match_route_plan_to_template(plan)

    assert result.matched is False
    assert MISMATCH_UNSUPPORTED_GROUP_BY in result.mismatch_reasons


def test_entity_timeline_skill_returns_no_match() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user", primary_skill="entity_timeline")
    result = match_route_plan_to_template(plan)

    assert result.matched is False
    assert MISMATCH_NO_TEMPLATE_FOR_SKILL in result.mismatch_reasons


def test_disabled_sample_is_matchable_but_not_production_executable() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    result = match_route_plan_to_template(plan, include_disabled=True)

    assert result.matched is True
    assert result.production_executable is False
    template = next(t for t in load_spl_templates() if t.template_id == result.matched_template_id)
    assert template.enabled is False
    assert template.sample_only is True


def test_matcher_is_pure() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    first = match_route_plan_to_template(deepcopy(plan))
    second = match_route_plan_to_template(deepcopy(plan))
    assert first.model_dump() == second.model_dump()


@pytest.mark.parametrize(
    "plan",
    [
        pytest.param(
            {
                "route_plan_id": "rp_no_match_reasons_1",
                "route_status": "route_ready",
                "primary_skill": "aggregate_and_rank",
                "pattern_id": "test",
                "operation_type": "top_n",
                "domain": "soc",
                "source_class": "unknown_source_xyz",
                "entities": ["user"],
                "time_window": "last_24_hours",
                "parameters": {
                    "group_by": {"field": "user"},
                    "metric": {"type": "count"},
                    "limit": 10,
                },
                "evidence_needs": {},
                "missing_slots": [],
                "hard_preconditions": [],
                "model_advisory_metadata": {},
                "deterministic_validation": {},
                "post_enrichment": [],
            },
            id="cannot_resolve_datamodel",
        ),
        pytest.param(
            _aggregate_plan(datamodel="MadeUp", group_by="user"),
            id="unknown_datamodel",
        ),
        pytest.param(
            _aggregate_plan(
                datamodel="Authentication",
                group_by="user",
                primary_skill="entity_timeline",
            ),
            id="no_template_for_skill",
        ),
        pytest.param(
            _aggregate_plan(datamodel="Authentication", group_by="not_a_cim_field"),
            id="unsupported_group_by",
        ),
    ],
)
def test_no_match_always_includes_mismatch_reason(plan: dict) -> None:
    result = match_route_plan_to_template(plan)
    assert result.matched is False
    assert result.mismatch_reasons


def test_ambiguous_match_returns_explicit_reason() -> None:
    base = _auth_sample_template()
    duplicate = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_ambiguous_twin_q1c",
            "use_case_id": "sample_auth_ambiguous_twin",
        }
    )
    catalog = load_spl_templates() + [duplicate]
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    result = match_route_plan_to_template(plan, templates=catalog)

    assert result.matched is False
    assert result.matched_template_id is None
    assert MISMATCH_AMBIGUOUS in result.mismatch_reasons
    assert len(result.candidate_template_ids) >= 2


def test_time_window_not_satisfiable_emitted() -> None:
    plan = _aggregate_plan_without_time_and_limit()
    ctx = _extract_match_context(plan)
    template = _auth_sample_template()
    _, _, mismatches = _score_template(template, ctx)
    assert MISMATCH_TIME_WINDOW in mismatches

    result = match_route_plan_to_template(plan, templates=[template])
    assert result.matched is False
    assert MISMATCH_TIME_WINDOW in result.mismatch_reasons


def test_result_limit_not_satisfiable_emitted() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    plan["parameters"].pop("limit", None)
    ctx = _extract_match_context(plan)
    template = _auth_sample_template()
    _, _, mismatches = _score_template(template, ctx)
    assert MISMATCH_RESULT_LIMIT in mismatches

    result = match_route_plan_to_template(plan, templates=[template])
    assert result.matched is False
    assert MISMATCH_RESULT_LIMIT in result.mismatch_reasons


def test_validator_profile_mismatch_emitted() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    plan["evidence_needs"]["validator_profile"] = "wrong_validator_profile_q1c"
    ctx = _extract_match_context(plan)
    template = _auth_sample_template()
    _, _, mismatches = _score_template(template, ctx)
    assert MISMATCH_VALIDATOR_PROFILE in mismatches

    result = match_route_plan_to_template(plan, templates=[template])
    assert result.matched is False
    assert MISMATCH_VALIDATOR_PROFILE in result.mismatch_reasons


def test_tie_break_prefers_matching_aggregation_shape() -> None:
    base = _auth_sample_template()
    ranked_twin = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_ranked_twin_q1c_fixb",
            "use_case_id": "sample_auth_ranked_twin",
            "aggregation_shape": "ranked_entities",
        }
    )
    non_aggregate_twin = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_non_aggregate_twin_q1c_fixb",
            "use_case_id": "sample_auth_non_aggregate_twin",
            "aggregation_shape": "non_aggregate",
        }
    )
    catalog = [ranked_twin, non_aggregate_twin]
    plan = _aggregate_plan(
        datamodel="Authentication",
        group_by="user",
        primary_skill="threshold_anomaly",
    )
    plan["operation_type"] = "field_discovery"
    result = match_route_plan_to_template(plan, templates=catalog)

    assert result.matched is True
    assert result.matched_template_id == "sample_auth_non_aggregate_twin_q1c_fixb"
    assert "exact_aggregation_shape_match" in result.match_reasons


def test_tie_break_prefers_production_executable_over_sample_only() -> None:
    base = _auth_sample_template()
    sample_twin = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_sample_twin_q1c_fixb",
            "use_case_id": "sample_auth_sample_twin",
        }
    )
    production_twin = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_production_twin_q1c_fixb",
            "use_case_id": "sample_auth_production_twin",
            "status": "active",
            "enabled": True,
            "production_ready": True,
            "sample_only": False,
        }
    )
    catalog = [sample_twin, production_twin]
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    result = match_route_plan_to_template(plan, templates=catalog)

    assert result.matched is True
    assert result.matched_template_id == "sample_auth_production_twin_q1c_fixb"
    assert result.production_executable is True


def test_equal_score_twins_return_ambiguous_not_arbitrary_winner() -> None:
    base = _auth_sample_template()
    twin_a = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_equal_a_q1c_fixb",
            "use_case_id": "sample_auth_equal_a",
        }
    )
    twin_b = SplTemplateDefinition(
        **{
            **base.model_dump(),
            "template_id": "sample_auth_equal_b_q1c_fixb",
            "use_case_id": "sample_auth_equal_b",
        }
    )
    catalog = [twin_a, twin_b]
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    candidates = dry_run_matches(plan, templates=catalog)
    viable = [item for item in candidates if not item.mismatch_reasons and item.match_score > 0]
    assert len(viable) >= 2
    assert viable[0].match_score == viable[1].match_score

    result = match_route_plan_to_template(plan, templates=catalog)
    assert result.matched is False
    assert result.matched_template_id is None
    assert MISMATCH_AMBIGUOUS in result.mismatch_reasons
    assert set(result.candidate_template_ids) >= {
        "sample_auth_equal_a_q1c_fixb",
        "sample_auth_equal_b_q1c_fixb",
    }


def test_include_disabled_false_when_only_sample_cim_templates() -> None:
    plan = _aggregate_plan(datamodel="Authentication", group_by="user")
    sample_cim_only = [
        t
        for t in load_spl_templates()
        if t.datamodel == "Authentication" and t.query_shape in {"tstats_datamodel", "from_datamodel"}
    ]
    assert sample_cim_only
    assert all(not t.is_production_executable() for t in sample_cim_only)

    result = match_route_plan_to_template(
        plan,
        include_disabled=False,
        templates=sample_cim_only,
    )

    assert result.matched is False
    assert result.matched_template_id is None
    assert result.mismatch_reasons
    assert MISMATCH_NO_TEMPLATE_FOR_SKILL in result.mismatch_reasons
