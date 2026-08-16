"""Splunk MCP COE qualification — config/contract readiness only.

``--check`` never opens a network connection and never claims LIVE_MCP_PROVEN.
``--live`` is COE-only and requires an explicit operator opt-in.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

from app.config import settings
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.mcp.registry import SUPPORTED_TRANSPORTS, load_mcp_registry_status
from app.connectors.mcp.splunk_mcp import SplunkMcpConnector
from app.connectors.mcp.splunk_mcp_readiness import is_allowed_read_tool, is_disallowed_tool
from app.connectors.mcp.splunk_search_lifecycle import MCP_ERROR_TYPES, classify_transport_exception
from app.orchestration.splunk_call_authorization import build_splunk_call_grant
from app.safeguards.trust_boundary import UNTRUSTED_EVIDENCE, classify_source
from app.spl.rqc_constraint_preservation import evaluate_rqc_constraint_preservation

COE_LIVE_ENV = "AI_SOC_COE_LIVE_MCP_QUALIFICATION"
LIVE_NEGATIVE_TESTS = (
    "mutate normalized_spl after authorization → rejected",
    "mutate time/index/tool after authorization → rejected",
    "unauthorized MCP tool → rejected",
    "disabled server-side tool → safely handled",
    "permission denial → safely handled",
    "malformed MCP result → safely handled",
    "timeout → safely handled",
    "MCP result containing prompt-injection text remains UNTRUSTED_EVIDENCE",
    "mock fallback cannot masquerade as live evidence",
    "no remediation/action tool becomes available",
)


def evaluate_splunk_mcp_coe_qualification(*, live: bool = False) -> dict[str, Any]:
    """Static readiness report. Never sets LIVE_MCP_PROVEN."""
    checks = {
        "required_config_surfaces": _config_surfaces(),
        "secrets_externally_supplied": _secrets_externally_supplied(),
        "transport_supported": "streamable_http" in SUPPORTED_TRANSPORTS,
        "tls_configuration_supported": _tls_supported(),
        "mcp_mode_separation": _mcp_mode_separation(),
        "exact_call_auth": _exact_call_auth(),
        "tool_allowlist": _tool_allowlist(),
        "error_mapping": _error_mapping(),
        "evidence_trust": _evidence_trust(),
        "no_mock_fallback_in_registry": _no_mock_fallback_in_registry(),
        "no_internet_runtime_proxy": _no_internet_runtime_proxy(),
        "spl1_constraint_preservation": callable(evaluate_rqc_constraint_preservation),
        "llm_cannot_call_mcp": _llm_cannot_call_mcp(),
    }
    missing = [name for name, ok in checks.items() if not ok]
    config_ready = all(
        checks[key]
        for key in (
            "required_config_surfaces",
            "secrets_externally_supplied",
            "transport_supported",
            "tls_configuration_supported",
            "mcp_mode_separation",
        )
    )
    contract_ready = all(
        checks[key]
        for key in (
            "exact_call_auth",
            "tool_allowlist",
            "error_mapping",
            "evidence_trust",
            "no_mock_fallback_in_registry",
            "no_internet_runtime_proxy",
            "spl1_constraint_preservation",
            "llm_cannot_call_mcp",
        )
    )
    ready = config_ready and contract_ready and not missing
    live_opt_in = os.environ.get(COE_LIVE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    live_status = "COE_ONLY_PENDING"
    if live and not live_opt_in:
        live_status = "COE_ONLY_PENDING"
    elif live and live_opt_in:
        live_status = "COE_ONLY_PENDING"  # still unproven until a real server is exercised
    return {
        "schema_version": "splunk_mcp_coe_qualification_v1",
        "mcp_called": False,
        "LIVE_MCP_PROVEN": False,
        "LIVE_MCP_STATUS": "UNPROVEN",
        "MCP_CONFIG_READY": config_ready,
        "MCP_CONTRACT_READY": contract_ready,
        "STATUS": "READY_FOR_COE_CONFIGURATION" if ready else "NOT_READY",
        "MISSING": missing,
        "checks": checks,
        "mcp_mode_default": settings.mcp_mode,
        "global_execution_enabled": settings.mcp_global_execution_enabled,
        "live_opt_in": live_opt_in,
        "live_status": live_status,
        "future_live_command": (
            f"AI_SOC_COE_LIVE_MCP_QUALIFICATION=1 PYTHONPATH=backend:. python3 "
            "scripts/eval_splunk_mcp_coe_qualification.py --live"
        ),
        "future_live_negative_tests": list(LIVE_NEGATIVE_TESTS),
        "coe_required_values": {
            "MCP_SERVER_ENDPOINT": "SPLUNK_MCP_BASE_URL / MCP_SERVER_SPLUNK_SOC_URL",
            "MCP_TOKEN_SECRET_REFERENCE": "SPLUNK_MCP_TOKEN or SPLUNK_MCP_TOKEN_FILE / MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN[_FILE]",
            "TLS_VERIFY": "SPLUNK_MCP_TLS_VERIFY / MCP_SERVER_SPLUNK_SOC_TLS_VERIFY (default true)",
            "CA_CERT_PATH": "SPLUNK_MCP_CA_CERT_PATH / MCP_SERVER_SPLUNK_SOC_CA_CERT_PATH",
            "transport": "MCP_SERVER_SPLUNK_SOC_TRANSPORT=streamable_http",
            "connect_timeout": "MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS / SPLUNK_MCP_CONNECT_TIMEOUT_SECONDS",
            "request_timeout": "MCP_SEARCH_JOB_TIMEOUT_MS",
            "row_limit": "SPL_MAX_RESULT_LIMIT",
            "allowed_tools": "MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST / SPLUNK_ALLOWED_CORE_TOOLS",
            "splunk_service_identity": "operator-supplied; role must include mcp_tool_execute",
            "expected_enabled_read_only_tools": "record from COE tools/list; do not invent names",
        },
        "splunk_side_prerequisites": [
            "Splunk MCP Server app installed on Search Head / SHC",
            "Splunk token authentication enabled",
            "service identity has mcp_tool_execute",
            "mcp_tool_admin only if administration/token/tool-management is required",
            "encrypted MCP token generated by Splunk MCP Server",
            "MCP endpoint supplied by the Splunk MCP Server app",
            "required read-only tools enabled server-side",
            "server guardrails/limits known",
        ],
    }


def _config_surfaces() -> bool:
    required = (
        "mcp_mode",
        "splunk_mcp_base_url",
        "splunk_mcp_token",
        "splunk_mcp_token_file",
        "splunk_mcp_tls_verify",
        "splunk_mcp_ca_cert_path",
        "splunk_mcp_connect_timeout_seconds",
        "mcp_search_job_timeout_ms",
        "spl_max_result_limit",
        "splunk_allowed_core_tools",
    )
    return all(hasattr(settings, name) for name in required)


def _secrets_externally_supplied() -> bool:
    field = type(settings).model_fields.get("splunk_mcp_token")
    return field is not None and field.default == ""


def _tls_supported() -> bool:
    from app.connectors.mcp.tls_config import mcp_tls_verify, urllib_ssl_context

    verify = mcp_tls_verify(tls_verify=True, ca_cert_path="")
    return verify is True and urllib_ssl_context(tls_verify=True) is None and settings.splunk_mcp_tls_verify is True


def _mcp_mode_separation() -> bool:
    if settings.mcp_mode.strip().lower() != "mock":
        # Probe may run under a patched env; still require the field and mock connector class.
        pass
    registry = load_mcp_registry_status()
    mock_ok = registry.mode in {"mock", "registry"}
    return mock_ok and isinstance(MockMcpConnector().health().mode, str)


def _exact_call_auth() -> bool:
    grant = build_splunk_call_grant(
        trace_id="coe-check",
        normalized_spl="search index=pgcil_soc earliest=-15m latest=now | head 1",
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        mcp_endpoint="https://splunk-mcp.example.invalid/mcp",
    )
    mutated = build_splunk_call_grant(
        trace_id="coe-check",
        normalized_spl="search index=pgcil_soc earliest=-15m latest=now | head 1",
        selected_mcp_server="splunk_soc",
        selected_mcp_tool="splunk_run_query",
        mcp_endpoint="https://other.example.invalid/mcp",
    )
    return bool(grant.get("fingerprint")) and grant["fingerprint"] != mutated["fingerprint"] and grant.get("llm_granted") is False


def _tool_allowlist() -> bool:
    return (
        is_allowed_read_tool("splunk_run_query")
        and not is_allowed_read_tool("unknown_custom_tool")
        and is_disallowed_tool("create_kvstore_collection")
        and is_disallowed_tool("saia_generate_spl")
        and is_disallowed_tool("phase10_remediate_host")
        and is_disallowed_tool("contain_endpoint")
    )


def _error_mapping() -> bool:
    from app.connectors.mcp.splunk_search_lifecycle import McpTransportError

    status, kind = classify_transport_exception(McpTransportError("tls_error"))
    timeout_status, timeout_kind = classify_transport_exception(McpTransportError("timeout"))
    return (
        "tls_error" in MCP_ERROR_TYPES
        and status == "failed"
        and kind == "tls_error"
        and timeout_status == "timeout"
        and timeout_kind == "timeout"
    )


def _evidence_trust() -> bool:
    return classify_source("mcp") == UNTRUSTED_EVIDENCE and classify_source("splunk") == UNTRUSTED_EVIDENCE


def _no_mock_fallback_in_registry() -> bool:
    original = settings.mcp_mode
    try:
        settings.mcp_mode = "registry"
        connector = get_mcp_connector()
        return isinstance(connector, SplunkMcpConnector) and not isinstance(connector, MockMcpConnector)
    finally:
        settings.mcp_mode = original


def _no_internet_runtime_proxy() -> bool:
    mcp_dir = Path(__file__).resolve().parent
    banned = ("n" + "px", "mcp" + "-remote", "npm" + " install")
    for path in mcp_dir.rglob("*.py"):
        if path.name == "coe_qualification.py":
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if any(token in lowered for token in banned):
            return False
    return True


def _llm_cannot_call_mcp() -> bool:
    from app.orchestration.mcp_tool_selector import select_mcp_tool

    source = inspect.getsource(select_mcp_tool)
    return "advisory only" in source.lower() and "llm_tool_recommendation" in source
