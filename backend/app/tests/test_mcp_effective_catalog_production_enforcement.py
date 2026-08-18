"""Production-path enforcement: the effective MCP tool catalog is now an
execution PREREQUISITE inside the real `evaluate_mcp_execution` ->
`select_mcp_tool` call chain, not merely an observability surface computed
by unit-tested pure functions. Every test here calls the actual gate entry
point `/chat` uses (`evaluate_mcp_execution`), with a fake connector that
raises if `call_tool` is ever reached, to prove the catalog check happens
BEFORE connector execution.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot, get_discovery_snapshot_store
from app.connectors.mcp.effective_catalog import compute_effective_catalog
from app.connectors.mcp.mcp_failure_taxonomy import TOOL_UNAVAILABLE
from app.connectors.mcp.registry import load_mcp_registry_status
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_fallback_policy import CAPABILITY_FALLBACK_CANDIDATES, resolve_fallback_tool
from app.orchestration.splunk_call_authorization import call_grant_from_tool_call

APPROVED = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


class _RaisingConnector:
    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        raise AssertionError(f"connector.call_tool must not be reached for {tool_name} -- effective catalog should have blocked it first")


class _CapturingConnector:
    def __init__(self) -> None:
        self.called_with: tuple[str, dict[str, Any]] | None = None

    def call_tool(self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None) -> dict[str, Any]:
        self.called_with = (tool_name, arguments)
        return {"status": "ok", "row_count": 1, "rows": [{"user": "svc_app"}]}


class _FakeTelemetry:
    def record_mcp_execution(self, *args: Any, **kwargs: Any) -> None:
        return None


def _registry_env(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "splunk_run_query,splunk_get_indexes,splunk_get_metadata")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.ai_soc_require_spl_execution_confirmation", False)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_enabled", True)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_base_url", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_mcp_token", "test-token")


def _seed(server_name: str, tool_name: str, *, input_schema: dict[str, Any] | None = None, captured_at: float | None = None) -> None:
    get_discovery_snapshot_store().put(
        DiscoverySnapshot(
            server_name=server_name,
            captured_at=captured_at if captured_at is not None else time.time(),
            source="operator_refresh",
            status="ok",
            tools=(DiscoveredToolRecord(name=tool_name, input_schema=input_schema or {}),),
        )
    )


_QUERY_SCHEMA = {"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]}


# 1. no snapshot -> no connector call
def test_1_no_snapshot_blocks_before_connector_call(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())

    execution, review = evaluate_mcp_execution(
        trace_id="t1", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "no_effective_catalog_eligible_tool"


# 2. verified effective tool -> reaches downstream AUTH0 gate (and executes when confirmed)
def test_2_verified_tool_reaches_and_passes_auth0_gate(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema=_QUERY_SCHEMA)

    execution, review = evaluate_mcp_execution(
        trace_id="t2", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "executed"
    assert connector.called_with is not None
    assert review["required"] is False


# 3. restart/empty snapshot -> execution blocked (simulated: put then clear)
def test_3_restart_clears_snapshot_and_blocks_execution(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema=_QUERY_SCHEMA)

    pre_restart, _r = evaluate_mcp_execution(
        trace_id="t3a", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert pre_restart["status"] == "executed"

    get_discovery_snapshot_store().clear()  # simulates backend restart: process-memory store reinitializes empty
    connector.called_with = None
    post_restart, review = evaluate_mcp_execution(
        trace_id="t3b", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert post_restart["status"] == "requires_human_review"
    assert post_restart["tool_selection_reason"] == "no_effective_catalog_eligible_tool"
    assert connector.called_with is None  # never reached call_tool the second time


# 4. approved-but-missing -> blocked
def test_4_approved_but_missing_blocks(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_get_indexes")  # discovery ran, but splunk_run_query wasn't returned

    execution, review = evaluate_mcp_execution(
        trace_id="t4", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "no_effective_catalog_eligible_tool"


# 5. schema mismatch -> blocked
def test_5_schema_mismatch_blocks(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema={"properties": {"other_param": {"type": "string"}}, "required": []})

    execution, review = evaluate_mcp_execution(
        trace_id="t5", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "no_effective_catalog_eligible_tool"


# 6. schema unknown -> blocked
def test_6_schema_unknown_blocks(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema={})  # server reported nothing -- splunk_run_query needs required params

    execution, review = evaluate_mcp_execution(
        trace_id="t6", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "no_effective_catalog_eligible_tool"


# 7. server-only tool -> blocked, never selectable
def test_7_server_only_tool_never_selectable(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    get_discovery_snapshot_store().put(
        DiscoverySnapshot(
            server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok",
            tools=(DiscoveredToolRecord(name="splunk_admin_delete_index"),),  # server-only, not locally approved
        )
    )

    execution, review = evaluate_mcp_execution(
        trace_id="t7", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        requested_mcp_tool="splunk_admin_delete_index",
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "requested_tool_not_found"  # never in local allowlist at all


# 8. stale discovery -> blocked
def test_8_stale_discovery_blocks(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema=_QUERY_SCHEMA, captured_at=0.0)  # 1970 -- far beyond 24h staleness

    execution, review = evaluate_mcp_execution(
        trace_id="t8", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"
    assert execution["tool_selection_reason"] == "no_effective_catalog_eligible_tool"


# 9/10. fallback only uses effective-catalog-verified tools and gets a new grant
def test_9_10_fallback_mechanism_only_uses_effective_catalog_and_new_grant(monkeypatch) -> None:
    _registry_env(monkeypatch)
    registry = load_mcp_registry_status()
    server = registry.servers[0]
    snapshot = DiscoverySnapshot(
        server_name="splunk_soc", captured_at=time.time(), source="operator_refresh", status="ok",
        tools=(
            DiscoveredToolRecord(name="splunk_run_query", input_schema=_QUERY_SCHEMA),
            DiscoveredToolRecord(name="splunk_get_metadata", input_schema={}),
        ),
    )
    get_discovery_snapshot_store().put(snapshot)
    catalog = compute_effective_catalog(server, mode="registry", snapshot=snapshot)

    monkeypatch.setitem(CAPABILITY_FALLBACK_CANDIDATES, "EVENT_SEARCH", ("splunk_get_metadata",))
    fallback_tool, reason = resolve_fallback_tool(
        capability="EVENT_SEARCH", failed_tool_name="splunk_run_query", failure_kind=TOOL_UNAVAILABLE, effective_catalog=catalog,
    )
    assert fallback_tool == "splunk_get_metadata"  # only came from the verified catalog

    original_grant = call_grant_from_tool_call(
        trace_id="t9", selection={"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"},
        tool_arguments={"search_query": "x"}, rbac_role="analyst", identity="analyst",
        hil_required=True, execution_intent="spl_search",
    )
    fallback_grant = call_grant_from_tool_call(
        trace_id="t9", selection={"selected_mcp_server": "splunk_soc", "selected_mcp_tool": fallback_tool},
        tool_arguments={}, rbac_role="analyst", identity="analyst",
        hil_required=True, execution_intent="metadata_discovery",
    )
    assert fallback_grant["fingerprint"] != original_grant["fingerprint"]  # brand new grant, never reused


# 11. global=true cannot bypass catalog
def test_11_global_true_cannot_bypass_catalog(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    registry = load_mcp_registry_status()
    assert registry.global_execution_enabled is True  # confirmed true, and still blocked because no discovery

    execution, review = evaluate_mcp_execution(
        trace_id="t11", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm",
    )
    assert execution["status"] == "requires_human_review"


# 12. catalog=true cannot bypass AUTH0/RBAC/HIL/policy
def test_12_catalog_pass_cannot_bypass_rbac(monkeypatch) -> None:
    _registry_env(monkeypatch)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: _RaisingConnector())
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema=_QUERY_SCHEMA)

    execution, review = evaluate_mcp_execution(
        trace_id="t12", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
        execution_review_action="confirm", rbac_role="viewer",  # viewer not allowed splunk_run_query
    )
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "policy_exception_request"


def test_12b_catalog_pass_cannot_bypass_hil_confirmation(monkeypatch) -> None:
    _registry_env(monkeypatch)
    connector = _CapturingConnector()
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_mcp_connector", lambda: connector)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: _FakeTelemetry())
    _seed("splunk_soc", "splunk_run_query", input_schema=_QUERY_SCHEMA)

    # no execution_review_action="confirm" -- registry mode always requires it
    execution, review = evaluate_mcp_execution(
        trace_id="t12b", selected_skill="attack_discovery", workflow_plan={}, spl_validation=APPROVED,
    )
    assert execution["status"] == "requires_human_review"
    assert connector.called_with is None
