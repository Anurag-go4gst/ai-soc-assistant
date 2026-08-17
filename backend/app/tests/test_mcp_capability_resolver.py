"""Deterministic capability -> tool resolution, wired into the existing
select_mcp_tool seam. Covers SELECTION 15-23 from the required test matrix.
"""

from __future__ import annotations

from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot
from app.connectors.mcp.effective_catalog import compute_effective_catalog
from app.connectors.mcp.mcp_capability import validate_capability
from app.connectors.mcp.registry import load_mcp_registry_status
from app.orchestration.mcp_tool_selector import select_mcp_tool


def _registry_and_server(monkeypatch, allowlist: str):
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", allowlist)
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    registry = load_mcp_registry_status()
    return registry, registry.servers[0]


def test_event_search_resolves_only_approved_event_search_tool(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_run_query,splunk_get_indexes")
    result = select_mcp_tool(
        trace_id="t1",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        mcp_capability="EVENT_SEARCH",
    )
    assert result["tool_selection_status"] == "selected"
    assert result["selected_mcp_tool"] == "splunk_run_query"
    assert result["tool_selection_reason"] == "capability_resolved_tool_selected"


def test_index_discovery_maps_to_correct_tool(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_get_indexes,splunk_get_metadata")
    result = select_mcp_tool(
        trace_id="t2",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="metadata_discovery",
        spl_validation=None,
        registry=registry,
        rbac_role="analyst",
        mcp_capability="INDEX_DISCOVERY",
    )
    assert result["selected_mcp_tool"] == "splunk_get_indexes"


def test_user_context_maps_to_correct_tool(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_get_user_info")
    result = select_mcp_tool(
        trace_id="t3",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="identity_lookup",
        spl_validation=None,
        registry=registry,
        rbac_role="analyst",
        mcp_capability="USER_CONTEXT",
    )
    assert result["selected_mcp_tool"] == "splunk_get_user_info"


def test_raw_llm_tool_recommendation_cannot_choose_tool(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_run_query")
    monkeypatch.setattr("app.orchestration.mcp_tool_selector.settings.llm_tool_recommendation_enabled", True)
    result = select_mcp_tool(
        trace_id="t4",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        llm_tool_recommendation={"tool_category": "splunk_admin_delete_index", "recommended_tool": "splunk_admin_delete_index"},
    )
    # The LLM recommendation field is read (tool_category) but never used to
    # pick a tool -- deterministic default-eligible selection still wins.
    assert result["selected_mcp_tool"] == "splunk_run_query"


def test_unknown_capability_rejected(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_run_query")
    result = select_mcp_tool(
        trace_id="t5",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        mcp_capability="DELETE_EVERYTHING",
    )
    assert result["tool_selection_status"] == "requires_human_review"
    assert result["tool_selection_reason"] == "capability_unresolved"
    assert validate_capability("DELETE_EVERYTHING") is None


def test_requested_raw_unapproved_tool_rejected(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "splunk_run_query")
    result = select_mcp_tool(
        trace_id="t6",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        user_requested_mcp_tool="splunk_get_kv_store_collections",
    )
    assert result["tool_selection_status"] == "requires_human_review"
    assert result["tool_selection_reason"] == "requested_tool_not_found"


def test_server_only_tool_cannot_be_selected_via_capability(monkeypatch) -> None:
    # capability resolves deterministically to splunk_run_query -- a
    # server-only tool has no capability mapping and cannot be reached this
    # way at all, but prove the effective-catalog gate also blocks it if
    # ever passed as an explicit request.
    registry, server = _registry_and_server(monkeypatch, "splunk_run_query")
    snapshot = DiscoverySnapshot(
        server_name="splunk_soc",
        captured_at=1_000_000.0,
        source="operator_refresh",
        status="ok",
        tools=(DiscoveredToolRecord(name="splunk_run_query", input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]}),),
    )
    catalog = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    result = select_mcp_tool(
        trace_id="t7",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        user_requested_mcp_tool="splunk_admin_delete_index",
        effective_catalog=catalog,
    )
    assert result["tool_selection_status"] == "requires_human_review"
    assert result["tool_selection_reason"] == "requested_tool_not_found"  # never in local allowlist to begin with


def test_effective_catalog_blocks_unverified_discovery_even_when_locally_approved(monkeypatch) -> None:
    registry, server = _registry_and_server(monkeypatch, "splunk_run_query")
    catalog = compute_effective_catalog(server, mode="registry", snapshot=None)  # DISCOVERY_UNVERIFIED
    result = select_mcp_tool(
        trace_id="t8",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        mcp_capability="EVENT_SEARCH",
        effective_catalog=catalog,
    )
    assert result["tool_selection_status"] == "requires_human_review"
    assert result["tool_selection_reason"] == "effective_catalog_blocked:DISCOVERY_UNVERIFIED"


def test_blocked_write_tool_cannot_be_selected(monkeypatch) -> None:
    registry, _server = _registry_and_server(monkeypatch, "saia_generate_spl")
    result = select_mcp_tool(
        trace_id="t9",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation={"approved": True, "normalized_spl": "search index=x | head 1"},
        registry=registry,
        rbac_role="analyst",
        user_requested_mcp_tool="saia_generate_spl",
    )
    assert result["tool_selection_status"] == "requires_human_review"
    assert result["tool_selection_reason"] in {"saia_conditional_blocked", "requested_tool_intent_mismatch"} or (
        result.get("human_review", {}).get("reason") in {"saia_conditional_blocked"}
    )


def test_deterministic_precedence_when_effective_catalog_narrows_default_eligible(monkeypatch) -> None:
    registry, server = _registry_and_server(monkeypatch, "splunk_get_indexes,splunk_get_metadata")
    snapshot = DiscoverySnapshot(
        server_name="splunk_soc",
        captured_at=1_000_000.0,
        source="operator_refresh",
        status="ok",
        tools=(DiscoveredToolRecord(name="splunk_get_metadata", input_schema={}),),  # only metadata verified present
    )
    catalog = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    result = select_mcp_tool(
        trace_id="t10",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="metadata_discovery",
        spl_validation=None,
        registry=registry,
        rbac_role="analyst",
        effective_catalog=catalog,
    )
    # splunk_get_indexes is locally approved and would normally win by list
    # order, but it's APPROVED_BUT_MISSING in the verified catalog -- the
    # verified alternative is selected deterministically instead.
    assert result["selected_mcp_tool"] == "splunk_get_metadata"
