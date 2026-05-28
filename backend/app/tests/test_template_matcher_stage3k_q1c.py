"""Stage 3K-Q1C deterministic template matcher tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.spl.template_matcher import (
    MISMATCH_AMBIGUOUS,
    MISMATCH_CANNOT_RESOLVE_DATAMODEL,
    MISMATCH_DATAMODEL_MISMATCH,
    MISMATCH_NO_TEMPLATE_FOR_SKILL,
    MISMATCH_UNKNOWN_DATAMODEL,
    MISMATCH_UNSUPPORTED_GROUP_BY,
    _extract_match_context,
    _score_template,
    match_route_plan_to_template,
)
from app.spl.template_registry import SplTemplateDefinition, get_spl_template, load_spl_templates


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
    base = next(t for t in load_spl_templates() if t.template_id == "sample_auth_failed_login_top_users_tstats")
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
    assert MISMATCH_AMBIGUOUS in result.mismatch_reasons
    assert len(result.candidate_template_ids) >= 2
