"""Stage 3K-Q1B template schema/registry tests.

These tests cover only the template schema/registry surface. They do not execute
SPL, do not call MCP, do not change MCP/SPL execution gates, and do not enable
live LLM routing, final synthesis, or the Answer Guard. Q1A remains the safety
boundary for the validator itself.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.safeguards.spl_validator import validate_spl
from app.spl.template_registry import (
    QUERY_SHAPE_FROM_DATAMODEL,
    QUERY_SHAPE_RAW_SEARCH,
    QUERY_SHAPE_TSTATS_DATAMODEL,
    SplTemplateDefinition,
    disabled_templates,
    enabled_templates,
    get_spl_template,
    load_spl_templates,
    registry_metadata,
    supported_query_shapes,
    template_summary,
    templates_by_datamodel,
    templates_by_query_shape,
)


def _base_tstats(**overrides):
    payload = {
        "template_id": "t_test",
        "status": "sample",
        "use_case_id": "uc_test",
        "query_shape": QUERY_SHAPE_TSTATS_DATAMODEL,
        "datamodel": "Authentication",
        "dataset": "Authentication",
        "cim_fields": ["user", "action"],
        "group_by_fields": ["user"],
        "metric_fields": ["count"],
        "time_bound_required": True,
        "result_limit_required": True,
        "summariesonly_required": True,
        "validator_profile": "cim_tstats_datamodel_v1",
        "enabled": False,
        "production_ready": False,
        "sample_only": True,
    }
    payload.update(overrides)
    return payload


def _base_from(**overrides):
    payload = {
        "template_id": "t_from_test",
        "status": "sample",
        "use_case_id": "uc_from_test",
        "query_shape": QUERY_SHAPE_FROM_DATAMODEL,
        "datamodel": "Network_Resolution",
        "dataset": "DNS",
        "cim_fields": ["host"],
        "group_by_fields": ["host"],
        "metric_fields": ["count"],
        "time_bound_required": True,
        "result_limit_required": True,
        "validator_profile": "cim_from_datamodel_v1",
        "enabled": False,
        "production_ready": False,
        "sample_only": True,
    }
    payload.update(overrides)
    return payload


# A. Existing raw-search templates still load.
def test_existing_raw_search_templates_still_load() -> None:
    templates = load_spl_templates()
    template_ids = {t.template_id for t in templates}
    assert "auth_failed_login_spike" in template_ids
    assert "auth_success_after_failure" in template_ids
    raw = get_spl_template("auth_failed_login_spike")
    assert raw is not None
    assert raw.query_shape == QUERY_SHAPE_RAW_SEARCH


# B. Existing raw-search template schema remains backward compatible.
def test_existing_raw_search_schema_backward_compatible() -> None:
    raw = get_spl_template("auth_failed_login_spike")
    assert raw is not None
    assert raw.status == "active"
    assert raw.validation_rules["allowed_indexes"] == ["pgcil_soc"]
    assert raw.validation_rules["allowed_sourcetypes"] == ["pgcil:auth"]
    assert raw.returned_fields == [
        "host", "src", "failed_logins", "distinct_users",
        "first_seen", "last_seen", "action",
    ]
    # Q1B additions default safely for legacy entries.
    assert raw.datamodel is None
    assert raw.validator_profile is None
    assert raw.evidence_output_contract is None
    assert raw.sample_only is False


# C. CIM/tstats sample template loads as disabled/sample-only.
def test_tstats_sample_template_loads_disabled_sample_only() -> None:
    sample = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert sample is not None
    assert sample.query_shape == QUERY_SHAPE_TSTATS_DATAMODEL
    assert sample.datamodel == "Authentication"
    assert sample.dataset == "Authentication"
    assert sample.summariesonly_required is True
    assert sample.time_bound_required is True
    assert sample.result_limit_required is True
    assert sample.validator_profile == "cim_tstats_datamodel_v1"
    assert sample.enabled is False
    assert sample.production_ready is False
    assert sample.sample_only is True
    assert sample.is_production_executable() is False


# D. from_datamodel sample template loads as disabled/sample-only.
def test_from_datamodel_sample_template_loads_disabled_sample_only() -> None:
    sample = get_spl_template("sample_dns_top_query_hosts_from_datamodel")
    assert sample is not None
    assert sample.query_shape == QUERY_SHAPE_FROM_DATAMODEL
    assert sample.datamodel == "Network_Resolution"
    assert sample.validator_profile == "cim_from_datamodel_v1"
    assert sample.sample_only is True
    assert sample.is_production_executable() is False


# E. tstats template without datamodel is rejected.
def test_tstats_without_datamodel_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(datamodel=None))


# F. tstats template with unknown datamodel is rejected.
def test_tstats_with_unknown_datamodel_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(datamodel="MadeUpModel"))


# G. tstats template with unknown CIM field is rejected.
def test_tstats_with_unknown_cim_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(cim_fields=["user", "definitely_not_a_field"]))


# H. tstats template missing validator_profile is rejected.
def test_tstats_missing_validator_profile_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(validator_profile=None))
    # Wrong validator_profile name is also rejected.
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(validator_profile="raw_search_v1"))


# I. tstats template missing required safety flags is rejected.
def test_tstats_missing_safety_flags_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(summariesonly_required=False))
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(time_bound_required=False))
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(result_limit_required=False))


def test_tstats_missing_groupby_and_metric_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_tstats(group_by_fields=[], metric_fields=[]))


# J. from_datamodel template missing datamodel rejected.
def test_from_datamodel_missing_datamodel_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_from(datamodel=None))


# K. from_datamodel template with unknown field rejected.
def test_from_datamodel_with_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(**_base_from(cim_fields=["not_a_real_field"]))


def test_from_datamodel_missing_declared_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        SplTemplateDefinition(
            **_base_from(cim_fields=[], group_by_fields=[], metric_fields=[])
        )


# L. Disabled/sample templates are not production executable.
def test_disabled_and_sample_templates_not_production_executable() -> None:
    sample_ids = {
        "sample_auth_failed_login_top_users_tstats",
        "sample_network_top_outbound_src_tstats",
        "sample_dns_top_query_hosts_from_datamodel",
    }
    enabled_ids = {t.template_id for t in enabled_templates()}
    disabled_ids = {t.template_id for t in disabled_templates()}
    assert sample_ids.isdisjoint(enabled_ids)
    assert sample_ids.issubset(disabled_ids)
    # firewall_deny_spike was promoted (WS-B) from planned to an active governed
    # template once pgcil:firewall joined the allowlist — now production-executable.
    assert "firewall_deny_spike" in enabled_ids
    assert "firewall_deny_spike" not in disabled_ids


# M. Template metadata aligns with Q1A validator query_shape.
def test_template_metadata_aligns_with_validator_query_shape() -> None:
    # Raw-search template SPL validates as raw_search.
    raw = get_spl_template("auth_failed_login_spike")
    assert raw is not None and raw.spl_text
    raw_result = validate_spl(raw.spl_text)
    assert raw_result["query_shape"] == raw.query_shape

    # Constructing a valid tstats SPL string that matches the sample template's
    # declared datamodel/fields validates as tstats_datamodel with the same
    # validation_profile the template advertises.
    sample = get_spl_template("sample_auth_failed_login_top_users_tstats")
    assert sample is not None
    tstats_spl = (
        "tstats summariesonly=true count "
        "from datamodel=Authentication.Authentication "
        "where earliest=-24h latest=now Authentication.action=failure "
        "by Authentication.user | head 100"
    )
    result = validate_spl(tstats_spl)
    assert result["query_shape"] == sample.query_shape
    assert result["query_shape"] == QUERY_SHAPE_TSTATS_DATAMODEL
    assert result["validation_profile"] == sample.validator_profile


# N. evidence_output_contract exists for aggregate sample templates.
def test_evidence_output_contract_present_for_aggregate_samples() -> None:
    for tid in (
        "sample_auth_failed_login_top_users_tstats",
        "sample_network_top_outbound_src_tstats",
        "sample_dns_top_query_hosts_from_datamodel",
    ):
        sample = get_spl_template(tid)
        assert sample is not None
        assert sample.evidence_output_contract is not None
        contract = sample.evidence_output_contract
        assert contract.output_type == "ranked_entities"
        # Stage 3K.1A aggregate safety: per-source counts must not be implicitly
        # summed into a global aggregate, and model-consumed packages must only
        # receive precomputed safe aggregates.
        assert contract.supports_global_aggregates is False
        assert contract.model_safe_aggregates_only is True


# Registry helper surface.
def test_registry_helper_surface() -> None:
    assert supported_query_shapes() == [
        QUERY_SHAPE_RAW_SEARCH,
        QUERY_SHAPE_TSTATS_DATAMODEL,
        QUERY_SHAPE_FROM_DATAMODEL,
    ]
    auth_templates = templates_by_datamodel("Authentication")
    auth_ids = {t.template_id for t in auth_templates}
    assert "sample_auth_failed_login_top_users_tstats" in auth_ids
    tstats_templates = templates_by_query_shape(QUERY_SHAPE_TSTATS_DATAMODEL)
    assert {t.template_id for t in tstats_templates} == {
        "sample_auth_failed_login_top_users_tstats",
        "sample_network_top_outbound_src_tstats",
    }
    metadata = registry_metadata()
    assert metadata["supported_query_shapes"] == supported_query_shapes()
    assert "sample_auth_failed_login_top_users_tstats" in metadata["sample_only_template_ids"]
    assert "auth_failed_login_spike" not in metadata["sample_only_template_ids"]
    assert metadata["templates_by_query_shape"][QUERY_SHAPE_FROM_DATAMODEL] == [
        "sample_dns_top_query_hosts_from_datamodel",
    ]


def test_template_summary_exposes_q1b_metadata() -> None:
    summary = template_summary("sample_auth_failed_login_top_users_tstats")
    assert summary is not None
    assert summary["query_shape"] == QUERY_SHAPE_TSTATS_DATAMODEL
    assert summary["datamodel"] == "Authentication"
    assert summary["validator_profile"] == "cim_tstats_datamodel_v1"

    legacy_summary = template_summary("auth_failed_login_spike")
    assert legacy_summary is not None
    assert legacy_summary["query_shape"] == QUERY_SHAPE_RAW_SEARCH
    assert legacy_summary["datamodel"] is None


def test_aws_security_group_modifications_template_is_raw_pgcil_and_validates(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")
    template = get_spl_template("aws_security_group_modifications")

    assert template is not None
    assert template.query_shape == QUERY_SHAPE_RAW_SEARCH
    assert template.is_production_executable() is True
    assert template.spl_text is not None
    assert "index=pgcil_soc" in template.spl_text
    assert "sourcetype=aws:cloudtrail" in template.spl_text
    assert "datamodel=" not in template.spl_text
    assert "tstats" not in template.spl_text
    assert "AuthorizeSecurityGroupIngress" in template.spl_text
    assert "RevokeSecurityGroupEgress" in template.spl_text

    result = validate_spl(template.spl_text)
    assert result["approved"] is True, result["reject_reasons"]
