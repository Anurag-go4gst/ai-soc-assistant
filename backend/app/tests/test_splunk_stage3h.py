from __future__ import annotations

import json

from app.api.routes_settings import settings_status
from app.connectors.mcp.registry import McpRegistryStatus, McpServerStatus
from app.evidence.source_evidence import build_source_evidence
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.orchestration.mcp_tool_selector import select_mcp_tool
from app.splunk.capabilities import build_splunk_capability_profile
from app.splunk.spl_services import generate_candidate_spl_with_provider, optimize_spl


APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}


def _registry(tools: list[str], available: bool = True) -> McpRegistryStatus:
    descriptors = [{"name": tool, "description": "", "capability": "spl_search" if "run_query" in tool else "metadata_lookup", "categories": [], "blocked": False, "blocked_reason": None} for tool in tools]
    return McpRegistryStatus(
        mode="mock",
        default_server="splunk_soc",
        global_execution_enabled=False,
        servers=[
            McpServerStatus(
                name="splunk_soc",
                type="splunk",
                enabled=True,
                implemented=True,
                configured=True,
                available=available,
                transport="mock",
                url_configured=False,
                command_configured=False,
                auth_mode="none",
                auth_configured=True,
                execution_enabled=False,
                discovered_tools_count=len(tools),
                discovered_tools_safe_names=tools,
                discovered_tools=descriptors,
                blocked_tools_count=0,
                blocked_tools_safe_names=[],
                splunk_app_id="7931",
                splunk_platform="mock",
                search_execution_allowed=False,
                saia_spl_generation_allowed=False,
                knowledge_object_discovery_allowed=True,
                list_tools_allowed=True,
            )
        ],
    )


def test_capability_profile_core_only(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "auto")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "splunk_get_metadata"]))
    assert profile.core_splunk_tools_available is True
    assert profile.saia_available is False
    assert profile.saia_usable is False
    assert profile.fallback_required is True


def test_run_query_aliases_are_canonicalized_without_duplicate_execution_tools(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "auto")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "run_splunk_query", "splunk_get_indexes"]))

    assert profile.run_query_available is True
    assert profile.available_tools.count("splunk_run_query") == 1
    assert "run_splunk_query" not in profile.available_tools


def test_capability_profile_saia_available_auto(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "auto")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]), required_saia_tool="saia_generate_spl")
    assert profile.saia_available is True
    assert profile.saia_usable is True


def test_capability_profile_saia_disabled_env(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "disabled")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]), required_saia_tool="saia_generate_spl")
    assert profile.saia_available is True
    assert profile.saia_usable is False
    assert profile.fallback_required is True


def test_air_gapped_defaults_to_fallback(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.ai_soc_environment_mode", "air_gapped")
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "auto")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]), required_saia_tool="saia_generate_spl")
    candidate, metadata = generate_candidate_spl_with_provider("trace-airgap", "attack_discovery", "failed login spike", profile)
    assert profile.fallback_required is True
    assert metadata["selected_candidate_spl_provider"] in {"template", "internal_llm"}
    assert candidate.candidate_spl


def test_air_gapped_explicit_enabled_allows_saia(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.ai_soc_environment_mode", "air_gapped")
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "enabled")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]), required_saia_tool="saia_generate_spl")

    assert profile.saia_usable is True
    assert profile.fallback_required is False


def test_saia_generate_spl_candidate_only(monkeypatch) -> None:
    monkeypatch.setattr("app.splunk.capabilities.settings.splunk_ai_assistant_mode", "auto")
    profile = build_splunk_capability_profile(_registry(["splunk_run_query", "splunk_get_indexes", "saia_generate_spl"]), required_saia_tool="saia_generate_spl")
    candidate, metadata = generate_candidate_spl_with_provider("trace-saia", "attack_discovery", "failed login spike", profile)
    assert metadata["selected_candidate_spl_provider"] == "saia_generate_spl"
    assert candidate.generation_mode == "saia_generate_spl"
    assert metadata["execution_eligible"] is False
    assert metadata["validation_required"] is True


def test_optimized_spl_requires_revalidation() -> None:
    result = optimize_spl("search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now | table user | stats count by user | sort -count")
    assert result["optimization_applied"] is True
    assert result["requires_revalidation"] is True
    assert result["revalidation_status"] is not None


def test_splunk_run_query_requires_normalized_spl(monkeypatch) -> None:
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.get_telemetry_connector", lambda: FakeTelemetry())
    execution, review = evaluate_mcp_execution(
        trace_id="trace-null-normalized",
        selected_skill="attack_discovery",
        workflow_plan={},
        spl_validation={**APPROVED_VALIDATION, "approved": True, "normalized_spl": None},
    )
    assert execution["executed_spl"] is None
    assert execution["status"] == "requires_human_review"
    assert review["reason"] == "normalized_spl_null"


def test_saved_search_default_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://splunk-mcp.example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "none")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST", "splunk_run_saved_search")
    selection = select_mcp_tool(
        trace_id="trace-saved",
        selected_skill="attack_discovery",
        workflow_plan={},
        execution_intent="spl_search",
        spl_validation=APPROVED_VALIDATION,
        user_requested_mcp_tool="splunk_run_saved_search",
    )
    assert selection["tool_selection_status"] == "requires_human_review"
    assert selection["blocked_reason"] == "saved_search_execution_disabled"


def test_status_does_not_leak_secrets(monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "registry")
    monkeypatch.setenv("MCP_SERVERS", "splunk_soc")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_TYPE", "splunk")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_URL", "https://user:secret@example.invalid/mcp")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer")
    monkeypatch.setenv("MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN", "super-secret-token")
    payload = settings_status()
    serialized = json.dumps(payload, default=str).lower()
    assert "super-secret-token" not in serialized
    assert "user:secret" not in serialized


def test_source_evidence_for_splunk_results() -> None:
    evidence = build_source_evidence(
        trace_id="trace-source",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution={
            "status": "executed",
            "selected_mcp_server": "splunk_soc",
            "selected_mcp_tool": "run_splunk_query",
            "executed_spl": APPROVED_VALIDATION["normalized_spl"],
            "result_count": 1,
            "results_preview": [{"user": "svc_app", "fail_count": 184}],
            "block_reason": None,
        },
    )
    item = evidence[0]
    assert item["source_type"] == "splunk_mcp"
    assert item["tool_name"] == "run_splunk_query"
    assert item["result_count"] == 1
    assert item["fields_returned"] == ["user", "fail_count"]
    assert item["preview_rows"]
    assert item["tool_category"] == "execution"


def test_saia_source_evidence_is_candidate_only_not_execution_evidence() -> None:
    evidence = build_source_evidence(
        trace_id="trace-saia-evidence",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation={**APPROVED_VALIDATION, "selected_candidate_spl_provider": "saia_generate_spl"},
        execution={
            "status": "requires_human_review",
            "selected_mcp_server": "splunk_soc",
            "selected_mcp_tool": "run_splunk_query",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
            "block_reason": "mcp_global_execution_disabled",
        },
    )

    saia = evidence[0]
    splunk = evidence[1]
    assert saia["source_type"] == "splunk_mcp_saia"
    assert saia["output_type"] == "candidate_spl"
    assert saia["tool_category"] is None
    assert saia["executed_spl"] is None
    assert splunk["source_type"] == "splunk_mcp"
    assert splunk["collection_status"] == "blocked"


class FakeTelemetry:
    def record_mcp_execution(self, trace_id: str, **fields) -> None:
        pass
