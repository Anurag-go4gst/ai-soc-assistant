"""EFFECTIVE_MCP_TOOL_CATALOG algorithm — dual catalog views, drift states,
fail-closed live-registry rule, schema compatibility.

Covers DISCOVERY 2-8 and SCHEMA 9-14 from the required test matrix.
"""

from __future__ import annotations

from app.connectors.mcp.discovery_snapshot import DiscoveredToolRecord, DiscoverySnapshot
from app.connectors.mcp.effective_catalog import compare_schema, compute_effective_catalog
from app.connectors.mcp.registry import load_mcp_registry_status


def _registry_server(monkeypatch, *, allowlist: str = "splunk_run_query,splunk_get_indexes,splunk_get_user_info"):
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", allowlist)
    return load_mcp_registry_status().servers[0]


def _ok_snapshot(tools: list[DiscoveredToolRecord], *, captured_at: float = 1_000_000.0) -> DiscoverySnapshot:
    return DiscoverySnapshot(server_name="splunk_soc", captured_at=captured_at, source="operator_refresh", status="ok", tools=tuple(tools))


# --- DISCOVERY 2-8 -----------------------------------------------------------

def test_server_only_tool_visible_but_non_executable(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="splunk_run_query")
    snapshot = _ok_snapshot([
        DiscoveredToolRecord(name="splunk_run_query", input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]}),
        DiscoveredToolRecord(name="splunk_admin_delete_index"),
    ])
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    assert result.is_executable("splunk_run_query") is True
    server_only_names = {t.name for t in result.server_discovered_catalog}
    assert "splunk_admin_delete_index" in server_only_names
    assert result.entry_for("splunk_admin_delete_index") is None  # never in the approved view


def test_locally_approved_tool_missing_server_side_blocked(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="splunk_run_query,splunk_get_indexes")
    snapshot = _ok_snapshot([
        DiscoveredToolRecord(name="splunk_run_query", input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]}),
    ])
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    entry = result.entry_for("splunk_get_indexes")
    assert entry.drift_status == "APPROVED_BUT_MISSING"
    assert entry.executable is False


def test_no_discovery_registry_live_tool_blocked(monkeypatch) -> None:
    server = _registry_server(monkeypatch)
    result = compute_effective_catalog(server, mode="registry", snapshot=None)
    for entry in result.effective_approved_catalog:
        assert entry.drift_status == "DISCOVERY_UNVERIFIED"
        assert entry.executable is False


def test_failed_discovery_blocked(monkeypatch) -> None:
    server = _registry_server(monkeypatch)
    snapshot = DiscoverySnapshot(server_name="splunk_soc", captured_at=1000.0, source="startup", status="failed", tools=(), error_reason="tls_error")
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=2000.0)
    for entry in result.effective_approved_catalog:
        assert entry.drift_status == "DISCOVERY_FAILED"
        assert entry.executable is False
    assert result.discovery_status == "failed"


def test_stale_discovery_blocks_live_execution(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="splunk_run_query")
    old_snapshot = _ok_snapshot(
        [DiscoveredToolRecord(name="splunk_run_query", input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]})],
        captured_at=0.0,
    )
    result = compute_effective_catalog(server, mode="registry", snapshot=old_snapshot, now=999_999.0)  # far beyond 24h
    entry = result.entry_for("splunk_run_query")
    assert entry.drift_status == "DISCOVERY_STALE"
    assert entry.executable is False
    assert result.discovery_status == "stale"


def test_malformed_tools_list_fails_safely_not_raised(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="splunk_get_indexes")
    snapshot = DiscoverySnapshot(server_name="splunk_soc", captured_at=1000.0, source="startup", status="failed", tools=(), error_reason="malformed_result")
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1000.0)
    assert result.entry_for("splunk_get_indexes").executable is False


def test_no_mock_fallback_mode_gates_correctly(monkeypatch) -> None:
    # mock/development mode keeps legacy behavior (no discovery gating) --
    # this proves the fail-closed rule is registry-mode specific, not a
    # blanket new requirement that would break existing mock/dev flows.
    monkeypatch.delenv("MCP_MODE", raising=False)
    status = load_mcp_registry_status()
    server = status.servers[0]
    result = compute_effective_catalog(server, mode="mock", snapshot=None)
    assert result.entry_for("splunk_run_query").executable is True
    assert result.entry_for("splunk_run_query").drift_status == "APPROVED_AND_PRESENT"


def test_unsafe_blocked_tool_never_executable_regardless_of_discovery(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="saia_generate_spl")
    snapshot = _ok_snapshot([DiscoveredToolRecord(name="saia_generate_spl")])
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    entry = result.entry_for("saia_generate_spl")
    assert entry.drift_status == "UNSAFE_OR_BLOCKED"
    assert entry.executable is False


# --- SCHEMA 9-14 --------------------------------------------------------------

def test_compatible_schema_accepted() -> None:
    status = compare_schema(
        "splunk_run_query",
        server_input_schema={"properties": {"search_query": {"type": "string"}}, "required": ["search_query"]},
        server_input_schema_malformed=False,
    )
    assert status == "SCHEMA_COMPATIBLE"


def test_required_arg_removed_rejected() -> None:
    status = compare_schema(
        "splunk_run_query",
        server_input_schema={"properties": {"other_field": {"type": "string"}}, "required": []},
        server_input_schema_malformed=False,
    )
    assert status == "SCHEMA_INCOMPATIBLE"


def test_dangerous_required_arg_addition_rejected() -> None:
    status = compare_schema(
        "splunk_run_query",
        server_input_schema={
            "properties": {"search_query": {"type": "string"}, "admin_override": {"type": "boolean"}},
            "required": ["search_query", "admin_override"],
        },
        server_input_schema_malformed=False,
    )
    assert status == "SCHEMA_INCOMPATIBLE"


def test_type_mismatch_rejected() -> None:
    status = compare_schema(
        "splunk_run_query",
        server_input_schema={"properties": {"search_query": {"type": "integer"}}, "required": ["search_query"]},
        server_input_schema_malformed=False,
    )
    assert status == "SCHEMA_INCOMPATIBLE"


def test_unknown_schema_blocked_in_live_registry(monkeypatch) -> None:
    server = _registry_server(monkeypatch, allowlist="splunk_run_query")
    # server advertises the tool but with no inputSchema at all -- and this
    # tool DOES have required params locally, so absence is UNKNOWN not
    # compatible.
    snapshot = _ok_snapshot([DiscoveredToolRecord(name="splunk_run_query", input_schema={})])
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    entry = result.entry_for("splunk_run_query")
    assert entry.schema_status == "SCHEMA_UNKNOWN"
    assert entry.drift_status == "SCHEMA_UNKNOWN"
    assert entry.executable is False


def test_no_required_params_tool_compatible_with_empty_schema(monkeypatch) -> None:
    # splunk_get_indexes has an explicit local "no required params" contract
    # -- server reporting no schema is legitimately compatible for it, not
    # unknown.
    server = _registry_server(monkeypatch, allowlist="splunk_get_indexes")
    snapshot = _ok_snapshot([DiscoveredToolRecord(name="splunk_get_indexes", input_schema={})])
    result = compute_effective_catalog(server, mode="registry", snapshot=snapshot, now=1_000_010.0)
    entry = result.entry_for("splunk_get_indexes")
    assert entry.schema_status == "SCHEMA_COMPATIBLE"
    assert entry.executable is True


def test_schema_fingerprint_stable_and_canonical() -> None:
    from app.connectors.mcp.effective_catalog import schema_fingerprint

    a = schema_fingerprint({"type": "object", "properties": {"x": {"type": "string"}}})
    b = schema_fingerprint({"properties": {"x": {"type": "string"}}, "type": "object"})  # different key order
    c = schema_fingerprint({"type": "object", "properties": {"y": {"type": "string"}}})
    assert a == b  # canonical (sorted-key) hashing -- key order doesn't matter
    assert a != c


def test_malformed_input_schema_is_incompatible() -> None:
    status = compare_schema("splunk_run_query", server_input_schema={}, server_input_schema_malformed=True)
    assert status == "SCHEMA_INCOMPATIBLE"


def test_no_local_contract_defined_is_unknown() -> None:
    status = compare_schema("totally_unmapped_tool", server_input_schema={"properties": {}}, server_input_schema_malformed=False)
    assert status == "SCHEMA_UNKNOWN"
