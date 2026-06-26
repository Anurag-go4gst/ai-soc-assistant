"""Stage 3K-Q1D deterministic template renderer tests."""

from __future__ import annotations

import pytest

from app.spl.template_registry import (
    QUERY_SHAPE_RAW_SEARCH,
    SplTemplateDefinition,
    get_spl_template,
    load_spl_templates,
)
from app.spl.template_renderer import (
    RENDER_BINDING_REGEX_FAILED,
    RENDER_MISSING_PATTERN,
    RENDER_MISSING_TIME_WINDOW,
    RENDER_NOT_SUPPORTED,
    RENDER_UNDECLARED_BINDING,
    RENDER_UNKNOWN_PLACEHOLDER,
    RENDER_VALIDATION_FAILED,
    render_template,
)


def _route_window() -> dict[str, str]:
    return {"earliest": "earliest=-24h", "latest": "latest=now"}


@pytest.mark.parametrize(
    "template_id",
    [
        "sample_auth_failed_login_top_users_tstats",
        "sample_network_top_outbound_src_tstats",
        "sample_dns_top_query_hosts_from_datamodel",
    ],
)
def test_sample_templates_render_and_pass_validator(template_id: str) -> None:
    template = get_spl_template(template_id)
    assert template is not None
    result = render_template(template, {}, route_window=_route_window())

    assert result.render_ok is True
    assert result.validator_approved is True
    assert result.rendered_spl
    assert result.execution_eligible is False
    assert result.validator_profile == template.validator_profile
    assert result.sample_only is True
    assert result.production_executable is False


def test_missing_route_window_uses_template_default() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template(template, {})

    assert result.render_ok is True
    assert result.bound_parameters["earliest"] == "earliest=-24h"
    assert result.bound_parameters["latest"] == "latest=now"


def test_missing_route_and_default_rejects() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    stripped = template.model_copy(update={"default_time_window": None})
    result = render_template(stripped, {})

    assert result.render_ok is False
    assert RENDER_MISSING_TIME_WINDOW in result.render_errors


def test_unknown_placeholder_in_pattern_rejects() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    bad = template.model_copy(update={"render_pattern": "tstats count {not_allowed} | head {result_limit}"})
    result = render_template(bad, {}, route_window=_route_window())

    assert RENDER_UNKNOWN_PLACEHOLDER in result.render_errors


def test_malicious_earliest_rejects() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    stripped = template.model_copy(update={"default_time_window": None})
    result = render_template(
        stripped,
        {"earliest": "earliest=*; rm -rf /", "latest": "latest=now", "result_limit": 10},
    )

    assert result.render_ok is False
    assert RENDER_BINDING_REGEX_FAILED in result.render_errors


def test_undeclared_binding_rejects() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    result = render_template(
        template,
        {"unexpected_key": "value"},
        route_window=_route_window(),
    )

    assert RENDER_UNDECLARED_BINDING in result.render_errors


def test_raw_search_template_renders_static_spl_and_validates() -> None:
    template = get_spl_template("auth_failed_login_spike")
    assert template is not None
    assert template.query_shape == QUERY_SHAPE_RAW_SEARCH
    result = render_template(template, {}, route_window=_route_window())

    assert result.render_ok is True
    assert result.rendered_spl == template.spl_text
    assert result.validator_approved is True
    assert result.execution_eligible is False


def test_raw_search_template_validation_uses_template_profile() -> None:
    template = SplTemplateDefinition(
        template_id="test_lookup_template",
        status="active",
        use_case_id="test_lookup_use_case",
        query_shape=QUERY_SHAPE_RAW_SEARCH,
        spl_text=(
            "search index=pgcil_soc sourcetype=pgcil:network earliest=-24h latest=now "
            "| lookup ot_asset_inventory.csv ip as dest_ip OUTPUT asset_name "
            "| stats count by asset_name | head 50"
        ),
        validation_rules={
            "allowed_lookups": ["ot_asset_inventory.csv"],
            "allowed_indexes": ["pgcil_soc"],
            "allowed_sourcetypes": ["pgcil:network"],
        },
    )

    result = render_template(template, {}, route_window=_route_window())

    assert result.render_ok is True
    assert result.validator_approved is True
    assert result.rendered_spl == template.spl_text


def test_missing_render_pattern_rejects() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    stripped = template.model_copy(update={"render_pattern": None})
    result = render_template(stripped, {}, route_window=_route_window())

    assert RENDER_MISSING_PATTERN in result.render_errors


def test_sample_only_unchanged_after_render() -> None:
    template = get_spl_template("sample_network_top_outbound_src_tstats")
    assert template is not None
    result = render_template(template, {}, route_window=_route_window())

    assert result.sample_only is True
    reloaded = get_spl_template(template.template_id)
    assert reloaded is not None
    assert reloaded.sample_only is True
    assert reloaded.is_production_executable() is False


def test_renderer_is_pure() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    first = render_template(template, {}, route_window=_route_window())
    second = render_template(template, {}, route_window=_route_window())
    assert first.model_dump() == second.model_dump()


def test_validation_failure_surfaces_reasons() -> None:
    template = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert template is not None
    broken = template.model_copy(
        update={
            "render_pattern": (
                "tstats count from datamodel=UnknownModel.Authentication "
                "where {earliest} {latest} by Authentication.user | head {result_limit}"
            )
        }
    )
    result = render_template(broken, {}, route_window=_route_window())

    assert result.render_ok is False
    assert RENDER_VALIDATION_FAILED in result.render_errors
