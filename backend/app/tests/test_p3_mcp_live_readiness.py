from __future__ import annotations

from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness


def test_live_readiness_blocks_default_mock_mode() -> None:
    report = evaluate_splunk_mcp_live_readiness()

    assert report["ready_for_live_splunk_mcp"] is False
    assert report["mcp_called"] is False
    assert report["execution_authorized"] is False
    assert "mcp_mode_must_be_registry" in report["blockers"]
    assert "coe_contract_approval_required" in report["blockers"]


def test_live_readiness_requires_coe_approval_even_when_registry_configured(monkeypatch) -> None:
    _configure_live_like_registry(monkeypatch)

    report = evaluate_splunk_mcp_live_readiness(coe_contract_approved=False)

    assert report["ready_for_live_splunk_mcp"] is False
    assert report["blockers"] == ["coe_contract_approval_required"]
    assert report["server"]["configured"] is True
    assert "splunk_run_query" in report["safe_tools_observed"]


def test_live_readiness_passes_only_when_all_gates_and_coe_approval_present(monkeypatch) -> None:
    _configure_live_like_registry(monkeypatch)

    report = evaluate_splunk_mcp_live_readiness(coe_contract_approved=True)

    assert report["ready_for_live_splunk_mcp"] is True
    assert report["blockers"] == []
    assert report["authority"] == "readiness_report_only"
    assert report["go_live_steps"]


def test_live_readiness_blocks_when_safe_search_tool_missing(monkeypatch) -> None:
    _configure_live_like_registry(monkeypatch)
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "splunk_get_indexes,splunk_get_metadata")

    report = evaluate_splunk_mcp_live_readiness(coe_contract_approved=True)

    assert report["ready_for_live_splunk_mcp"] is False
    assert "safe_splunk_search_tool_required" in report["blockers"]


def _configure_live_like_registry(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_DEFAULT_SERVER", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "true")
    monkeypatch.setenv(
        "MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST",
        "splunk_get_indexes,splunk_get_metadata,splunk_run_query",
    )
