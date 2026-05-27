from __future__ import annotations

from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.safeguards.spl_validator import validate_spl


VALID_TSTATS_AUTH = (
    "tstats summariesonly=true count from datamodel=Authentication.Authentication "
    "where earliest=-24h latest=now Authentication.action=failure "
    "by Authentication.user Authentication.src | head 100"
)
VALID_TSTATS_NETWORK = (
    "tstats summariesonly=true sum(Network_Traffic.bytes) as bytes "
    "from datamodel=Network_Traffic.All_Traffic "
    "where earliest=-24h latest=now Network_Traffic.action=allowed "
    "by Network_Traffic.src Network_Traffic.dest Network_Traffic.dest_port | head 100"
)
VALID_FROM_DATAMODEL = (
    "from datamodel=Authentication.Authentication "
    "| where earliest=-24h latest=now action=\"failure\" "
    "| stats count by user src | sort 100 - count | head 100"
)


def test_existing_raw_search_valid_template_still_passes() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100")

    assert result["approved"] is True
    assert result["query_shape"] == "raw_search"
    assert result["normalized_spl"] is not None


def test_existing_raw_search_invalid_spl_still_fails() -> None:
    result = validate_spl("search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | delete")

    assert result["approved"] is False
    assert result["query_shape"] == "raw_search"
    assert "delete" in result["blocked_commands"]


def test_valid_tstats_authentication_query_passes() -> None:
    result = validate_spl(VALID_TSTATS_AUTH)

    assert result["approved"] is True
    assert result["query_shape"] == "tstats_datamodel"
    assert result["datamodel"] == "Authentication"
    assert result["dataset"] == "Authentication"
    assert result["summariesonly_required"] is True
    assert result["summariesonly_present"] is True
    assert result["time_bounds_present"] is True
    assert result["result_limit_present"] is True
    assert set(result["cim_fields_validated"]) == {"action", "src", "user"}
    assert result["validation_profile"] == "cim_tstats_datamodel_v1"


def test_valid_tstats_network_traffic_query_passes() -> None:
    result = validate_spl(VALID_TSTATS_NETWORK)

    assert result["approved"] is True
    assert result["query_shape"] == "tstats_datamodel"
    assert result["datamodel"] == "Network_Traffic"
    assert result["dataset"] == "All_Traffic"
    assert {"bytes", "src", "dest", "dest_port", "action"}.issubset(set(result["cim_fields_validated"]))


def test_tstats_unknown_datamodel_is_rejected() -> None:
    result = validate_spl(
        "tstats summariesonly=true count from datamodel=Unknown_DM.Events "
        "where earliest=-24h latest=now Unknown_DM.user=bob by Unknown_DM.user | head 100"
    )

    assert result["approved"] is False
    assert "unknown_datamodel" in result["reject_reasons"]


def test_tstats_without_summariesonly_is_rejected() -> None:
    result = validate_spl(
        "tstats count from datamodel=Authentication.Authentication "
        "where earliest=-24h latest=now Authentication.action=failure by Authentication.user | head 100"
    )

    assert result["approved"] is False
    assert "summariesonly_required" in result["reject_reasons"]


def test_tstats_without_time_bounds_is_rejected() -> None:
    result = validate_spl(
        "tstats summariesonly=true count from datamodel=Authentication.Authentication "
        "where Authentication.action=failure by Authentication.user | head 100"
    )

    assert result["approved"] is False
    assert "missing_time_bounds" in result["reject_reasons"]


def test_tstats_unknown_field_is_rejected() -> None:
    result = validate_spl(
        "tstats summariesonly=true count from datamodel=Authentication.Authentication "
        "where earliest=-24h latest=now Authentication.not_a_cim_field=value by Authentication.user | head 100"
    )

    assert result["approved"] is False
    assert "unknown_cim_field:not_a_cim_field" in result["reject_reasons"]


def test_tstats_with_blocked_command_is_rejected() -> None:
    result = validate_spl(f"{VALID_TSTATS_AUTH} | outputlookup unsafe.csv")

    assert result["approved"] is False
    assert "outputlookup" in result["blocked_commands_found"]
    assert any(reason.startswith("blocked_command") for reason in result["reject_reasons"])


def test_from_datamodel_valid_query_passes() -> None:
    result = validate_spl(VALID_FROM_DATAMODEL)

    assert result["approved"] is True
    assert result["query_shape"] == "from_datamodel"
    assert result["datamodel"] == "Authentication"
    assert result["dataset"] == "Authentication"
    assert result["time_bounds_present"] is True
    assert result["result_limit_present"] is True
    assert {"action", "user", "src"}.issubset(set(result["cim_fields_validated"]))


def test_from_datamodel_unknown_datamodel_rejected() -> None:
    result = validate_spl(
        "from datamodel=Unknown_DM.Events | where earliest=-24h latest=now user=\"bob\" | stats count by user | head 100"
    )

    assert result["approved"] is False
    assert "unknown_datamodel" in result["reject_reasons"]


def test_from_datamodel_unknown_field_rejected() -> None:
    result = validate_spl(
        "from datamodel=Authentication.Authentication "
        "| where earliest=-24h latest=now not_a_cim_field=\"x\" "
        "| stats count by user | head 100"
    )

    assert result["approved"] is False
    assert "unknown_cim_field:not_a_cim_field" in result["reject_reasons"]


def test_from_datamodel_missing_time_bound_rejected() -> None:
    result = validate_spl("from datamodel=Authentication.Authentication | stats count by user | head 100")

    assert result["approved"] is False
    assert "missing_time_bounds" in result["reject_reasons"]


def test_macro_subsearch_and_write_commands_remain_blocked() -> None:
    macro = validate_spl(f"{VALID_TSTATS_AUTH} `unsafe_macro`")
    subsearch = validate_spl(f"{VALID_TSTATS_AUTH} [ search index=pgcil_soc ]")
    write = validate_spl(f"{VALID_FROM_DATAMODEL} | collect index=summary")

    assert "macros_not_allowed" in macro["reject_reasons"]
    assert "subsearches_not_allowed" in subsearch["reject_reasons"]
    assert "collect" in write["blocked_commands_found"]


def test_savedsearch_execution_remains_blocked_by_default() -> None:
    result = validate_spl("savedsearch Enterprise Security - Access Center | head 100")

    assert result["approved"] is False
    assert "savedsearch" in result["blocked_commands"]
    assert result["normalized_spl"] is None


def test_candidate_spl_still_requires_validator_and_existing_gate(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())

    validation = validate_spl(VALID_TSTATS_AUTH)
    execution, review = evaluate_mcp_execution(
        trace_id="trace-cim-q1a",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation={**validation, "candidate_spl": f"{VALID_TSTATS_AUTH} | delete"},
    )

    assert validation["approved"] is True
    assert validation["normalized_spl"] == VALID_TSTATS_AUTH
    assert validation["execution_eligible"] is False
    assert execution["executed_spl"] is None
    assert execution["block_reason"] == "mcp_global_execution_disabled"
    assert review["required"] is True


class FakeTelemetry:
    def __init__(self) -> None:
        self.mcp_events: list[dict] = []

    def record_mcp_execution(self, trace_id: str, **fields) -> None:
        self.mcp_events.append({"trace_id": trace_id, **fields})
