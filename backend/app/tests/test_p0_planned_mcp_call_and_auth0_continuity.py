"""P0 — planned MCP arguments hash through AUTH0 exact-call continuity."""

from __future__ import annotations

from app.chat.contracts.investigation_plan import InvestigationCapabilityBinding
from app.chat.planned_mcp_call import enrich_capability_binding, planned_arguments_hash
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments
from app.orchestration.splunk_call_authorization import (
    build_splunk_call_grant,
    call_grant_from_validation,
    grants_match,
)

CAPABILITY_ID = "mcp:splunk_soc:splunk_run_query"
APPROVED_A = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now "
    "| stats count by user | head 100"
)
APPROVED_B = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now "
    "| stats count by src | head 50"
)
APPROVED_USER_B = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now user=bob "
    "| stats count by user | head 100"
)
VALIDATION_A = {
    "approved": True,
    "normalized_spl": APPROVED_A,
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}
SELECTION = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"}


def _base_binding() -> InvestigationCapabilityBinding:
    return InvestigationCapabilityBinding(
        capability_id=CAPABILITY_ID,
        capability_need="required",
        availability="available",
        access_mode="read_only",
    )


def test_binding_without_spl_has_purpose_template_and_unresolved() -> None:
    enriched = enrich_capability_binding(_base_binding())
    assert enriched.purpose
    assert enriched.purpose != "required"
    assert enriched.argument_template is not None
    assert "search_query" in enriched.argument_template
    assert enriched.planned_arguments is None
    assert "search_query" in enriched.unresolved_arguments
    assert "normalized_spl" in enriched.unresolved_arguments
    assert enriched.read_write_classification == "execution_gated"
    assert enriched.authorization_posture == "exact_call_auth0_grant_required"


def test_binding_with_normalized_spl_matches_search_tool_arguments_and_hash() -> None:
    enriched = enrich_capability_binding(
        _base_binding(),
        normalized_spl=APPROVED_A,
        trace_id="p0-planned",
    )
    expected = splunk_search_tool_arguments(normalized_spl=APPROVED_A, trace_id="p0-planned")
    assert enriched.planned_arguments == expected
    assert enriched.unresolved_arguments == []

    grant = call_grant_from_validation(
        trace_id="p0-planned",
        selection=SELECTION,
        spl_validation=VALIDATION_A,
        hil_required=True,
    )
    assert grant["canonical_arguments_hash"] == planned_arguments_hash(enriched.planned_arguments)


def test_planned_hash_matches_executed_grant_happy_path() -> None:
    enriched = enrich_capability_binding(
        _base_binding(),
        normalized_spl=APPROVED_A,
        trace_id="p0-happy",
    )
    grant = call_grant_from_validation(
        trace_id="p0-happy",
        selection=SELECTION,
        spl_validation=VALIDATION_A,
        hil_required=True,
    )
    assert planned_arguments_hash(enriched.planned_arguments) == grant["canonical_arguments_hash"]
    assert grants_match({"call_grant": grant}, grant) is True


def test_grant_fingerprint_invalidated_on_tool_server_argument_spl_time_entity_changes() -> None:
    base_grant = call_grant_from_validation(
        trace_id="p0-neg",
        selection=SELECTION,
        spl_validation=VALIDATION_A,
        hil_required=True,
    )

    tool_grant = build_splunk_call_grant(
        trace_id="p0-neg",
        selected_mcp_server=SELECTION["selected_mcp_server"],
        selected_mcp_tool="splunk_run_saved_search",
        normalized_spl=APPROVED_A,
        tool_arguments=splunk_search_tool_arguments(normalized_spl=APPROVED_A, trace_id="p0-neg"),
    )
    assert grants_match({"call_grant": base_grant}, tool_grant) is False

    server_grant = build_splunk_call_grant(
        trace_id="p0-neg",
        selected_mcp_server="other_soc",
        selected_mcp_tool=SELECTION["selected_mcp_tool"],
        normalized_spl=APPROVED_A,
        tool_arguments=splunk_search_tool_arguments(normalized_spl=APPROVED_A, trace_id="p0-neg"),
    )
    assert grants_match({"call_grant": base_grant}, server_grant) is False

    mutated_args = dict(splunk_search_tool_arguments(normalized_spl=APPROVED_A, trace_id="p0-neg"))
    mutated_args["max_results"] = 10
    args_grant = build_splunk_call_grant(
        trace_id="p0-neg",
        selected_mcp_server=SELECTION["selected_mcp_server"],
        selected_mcp_tool=SELECTION["selected_mcp_tool"],
        normalized_spl=APPROVED_A,
        tool_arguments=mutated_args,
    )
    assert grants_match({"call_grant": base_grant}, args_grant) is False

    spl_grant = call_grant_from_validation(
        trace_id="p0-neg",
        selection=SELECTION,
        spl_validation={**VALIDATION_A, "normalized_spl": APPROVED_B},
        hil_required=True,
    )
    assert grants_match({"call_grant": base_grant}, spl_grant) is False

    time_grant = build_splunk_call_grant(
        trace_id="p0-neg",
        selected_mcp_server=SELECTION["selected_mcp_server"],
        selected_mcp_tool=SELECTION["selected_mcp_tool"],
        normalized_spl=APPROVED_B,
        tool_arguments=splunk_search_tool_arguments(normalized_spl=APPROVED_B, trace_id="p0-neg"),
    )
    assert grants_match({"call_grant": base_grant}, time_grant) is False

    entity_grant = call_grant_from_validation(
        trace_id="p0-neg",
        selection=SELECTION,
        spl_validation={**VALIDATION_A, "normalized_spl": APPROVED_USER_B},
        hil_required=True,
    )
    assert grants_match({"call_grant": base_grant}, entity_grant) is False


def test_repeated_material_call_requires_distinct_grant_and_consumed_rejects_replay() -> None:
    first_args = splunk_search_tool_arguments(normalized_spl=APPROVED_A, trace_id="p0-repeat")
    second_args = splunk_search_tool_arguments(normalized_spl=APPROVED_B, trace_id="p0-repeat")
    assert planned_arguments_hash(first_args) != planned_arguments_hash(second_args)

    grant_a = call_grant_from_validation(
        trace_id="p0-repeat",
        selection=SELECTION,
        spl_validation=VALIDATION_A,
        hil_required=True,
    )
    grant_b = call_grant_from_validation(
        trace_id="p0-repeat",
        selection=SELECTION,
        spl_validation={**VALIDATION_A, "normalized_spl": APPROVED_B},
        hil_required=True,
    )
    assert grant_a["fingerprint"] != grant_b["fingerprint"]

    consumed = {**grant_a, "consumed": True}
    assert grants_match({"call_grant": consumed, "consumed": True}, grant_a) is False
