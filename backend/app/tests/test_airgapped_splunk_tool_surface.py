from __future__ import annotations

from app.connectors.mcp.discovery import classify_mcp_tool
from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.connectors.mcp.splunk_mcp_readiness import (
    ALLOWED_READ_TOOL,
    plan_splunk_discovery_calls,
    plan_splunk_search_call,
)
from app.planner.resource_registry import load_resource_registry


AIRGAPPED_TOOLS = (
    "splunk_run_query",
    "splunk_get_info",
    "splunk_get_indexes",
    "splunk_get_index_info",
    "splunk_get_metadata",
    "splunk_get_user_info",
    "splunk_get_knowledge_objects",
)


def test_confirmed_airgapped_tool_surface_has_expected_policy_classes() -> None:
    descriptors = {name: classify_mcp_tool(name, server_type="splunk") for name in AIRGAPPED_TOOLS}

    assert descriptors["splunk_run_query"].capability == "spl_search"
    assert descriptors["splunk_get_metadata"].capability == "metadata_lookup"
    assert descriptors["splunk_get_knowledge_objects"].capability == "knowledge_object_discovery"
    # splunk_get_user_info returns the current authenticated user (self) only —
    # read-only identity, enabled in air-gapped and governed by RBAC, NOT blocked.
    assert descriptors["splunk_get_user_info"].capability == "identity_lookup"
    assert descriptors["splunk_get_user_info"].blocked is False
    assert descriptors["splunk_get_user_info"].rbac_gated is True
    # splunk_run_query stays execution-gated but is also RBAC-scoped.
    assert descriptors["splunk_run_query"].rbac_gated is True


def test_user_list_and_saia_stay_blocked() -> None:
    # Enumerating all users (recon/PII) stays hard-blocked, unlike self-identity.
    user_list = classify_mcp_tool("splunk_get_user_list", server_type="splunk")
    assert user_list.blocked is True
    assert user_list.blocked_reason == "admin_or_sensitive_tool"
    # SAIA generative tools are conditional (app-dependent) and stay blocked.
    for name in ("saia_generate_spl", "saia_optimize_spl", "saia_explain_spl", "saia_ask_splunk_question"):
        descriptor = classify_mcp_tool(name, server_type="splunk")
        assert descriptor.blocked is True
        assert descriptor.blocked_reason == "saia_conditional_blocked"


def test_canonical_search_plan_uses_splunk_run_query(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    record = plan_splunk_search_call(
        trace_id="airgap-search",
        spl_validation={
            "approved": True,
            "normalized_spl": "search index=security earliest=-15m latest=now | head 20",
        },
        evidence_plan={"needs_mcp": True, "mcp_allowed": True},
    )

    assert ALLOWED_READ_TOOL == "splunk_run_query"
    assert record.tool_name == "splunk_run_query"
    assert record.kind == "planned_tool_call"
    assert record.failure_mode == "execution_disabled"


def test_discovery_plan_is_ordered_planned_only_and_never_selects_user_info(monkeypatch) -> None:
    monkeypatch.delenv("MCP_GLOBAL_EXECUTION_ENABLED", raising=False)
    records = plan_splunk_discovery_calls(target_index="security")

    assert [record.tool_name for record in records] == [
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_get_index_info",
        "splunk_get_knowledge_objects",
    ]
    assert "splunk_get_user_info" not in {record.tool_name for record in records}
    assert all(record.kind == "planned_tool_call" for record in records)
    assert all(record.failure_mode == "execution_disabled" for record in records)
    assert all(record.policy_checks == ("read_only_discovery", "mcp_execution_gate") for record in records)


def test_resource_registry_contains_all_seven_canonical_entries() -> None:
    registry = load_resource_registry(reload=True)
    canonical = {f"mcp_tool:{name}" for name in AIRGAPPED_TOOLS}

    assert canonical <= {item.resource_id for item in registry.resources}
    # user_info is no longer hard-blocked: RBAC-gated read-only self identity.
    user_info = registry.by_id("mcp_tool:splunk_get_user_info")
    assert user_info.availability != "blocked"
    assert user_info.policy_tier == 2
    assert "rbac_gated" in user_info.capabilities


def test_live_readiness_accepts_confirmed_search_and_metadata_names_but_keeps_other_gates() -> None:
    server = McpServerStatus(
        name="splunk_soc",
        type="splunk",
        enabled=True,
        implemented=True,
        configured=True,
        available=True,
        transport="streamable_http",
        url_configured=True,
        command_configured=False,
        auth_mode="bearer",
        auth_configured=True,
        execution_enabled=False,
        discovered_tools_count=len(AIRGAPPED_TOOLS),
        discovered_tools_safe_names=list(AIRGAPPED_TOOLS),
        discovered_tools=[],
        blocked_tools_count=1,
        blocked_tools_safe_names=["splunk_get_user_info"],
        search_execution_allowed=False,
    )
    registry = McpRegistryStatus(
        mode="registry",
        default_server="splunk_soc",
        global_execution_enabled=False,
        servers=[server],
    )

    report = evaluate_splunk_mcp_live_readiness(registry=registry, coe_contract_approved=False)

    assert "safe_splunk_search_tool_required" not in report["blockers"]
    assert "safe_splunk_metadata_tool_required" not in report["blockers"]
    assert "mcp_global_execution_enabled_required" in report["blockers"]
    assert "splunk_mcp_server_execution_enabled_required" in report["blockers"]
    assert "coe_contract_approval_required" in report["blockers"]
    assert report["ready_for_live_splunk_mcp"] is False
    assert report["mcp_called"] is False
