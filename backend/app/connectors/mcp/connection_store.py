"""File-backed override for the Splunk MCP connection settings.

Operators can paste the Splunk MCP endpoint and encrypted token from the
Splunk MCP Server app into Settings instead of editing ``.env``. The secret is
persisted locally, applied to the process env used by the MCP registry loader,
and never returned by API responses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import settings

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "mcp_connection.json"
_SPLUNK_SERVER_ID = "splunk_soc"
_CORE_TOOLS = (
    "splunk_run_query",
    "splunk_get_info",
    "splunk_get_indexes",
    "splunk_get_index_info",
    "splunk_get_metadata",
    "splunk_get_user_info",
    "splunk_get_knowledge_objects",
)
_SAIA_TOOLS = (
    "saia_generate_spl",
    "saia_explain_spl",
    "saia_optimize_spl",
    "saia_ask_splunk_question",
)


def _store_path() -> Path:
    configured = (settings.ai_soc_mcp_connection_store_path or "").strip()
    return Path(configured) if configured else _DEFAULT_PATH


def _read_document() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_allowlist(document: dict[str, Any]) -> str:
    tools = list(_CORE_TOOLS)
    if document.get("deployment_mode") != "air_gapped" and document.get("saia_tools_enabled"):
        tools.extend(_SAIA_TOOLS)
    if document.get("allow_saved_search"):
        tools.append("splunk_run_saved_search")
    return ",".join(tools)


def load_connection_override() -> dict[str, Any]:
    return _read_document()


def apply_to_settings() -> dict[str, Any]:
    document = _read_document()
    if not document:
        return {}

    enabled = bool(document.get("enabled"))
    url = str(document.get("url") or "").strip()
    token = str(document.get("bearer_token") or "").strip()
    deployment_mode = str(document.get("deployment_mode") or "coe").strip().lower()
    discovery_mode = str(document.get("discovery_policy") or "dynamic").strip().lower()
    transport = str(document.get("transport") or "streamable_http").strip().lower()
    auth_method = str(document.get("auth_method") or "bearer").strip().lower()
    timeout_seconds = int(document.get("timeout_seconds") or 10)
    execution_enabled = bool(document.get("execution_enabled"))

    settings.splunk_mcp_enabled = enabled
    settings.ai_soc_environment_mode = deployment_mode
    settings.splunk_mcp_server_id = _SPLUNK_SERVER_ID
    settings.splunk_mcp_discovery_mode = discovery_mode
    settings.splunk_mcp_base_url = url
    settings.splunk_mcp_token = token
    settings.splunk_saia_tools_enabled = bool(document.get("saia_tools_enabled")) and deployment_mode != "air_gapped"
    settings.splunk_ai_assistant_mode = "disabled" if deployment_mode == "air_gapped" else str(document.get("splunk_ai_assistant_mode") or "auto")
    settings.splunk_allow_run_saved_search = bool(document.get("allow_saved_search"))

    os.environ["MCP_MODE"] = "registry"
    os.environ["MCP_SERVERS"] = _SPLUNK_SERVER_ID
    os.environ["MCP_DEFAULT_SERVER"] = _SPLUNK_SERVER_ID
    os.environ["MCP_SERVER_SPLUNK_SOC_ENABLED"] = "true" if enabled else "false"
    os.environ["MCP_SERVER_SPLUNK_SOC_TYPE"] = "splunk"
    os.environ["MCP_SERVER_SPLUNK_SOC_TRANSPORT"] = transport
    os.environ["MCP_SERVER_SPLUNK_SOC_URL"] = url
    os.environ["MCP_SERVER_SPLUNK_SOC_AUTH_MODE"] = auth_method
    os.environ["MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN"] = token
    os.environ["MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS"] = str(timeout_seconds)
    os.environ["MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST"] = _tool_allowlist(document)
    os.environ["MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED"] = "true" if execution_enabled else "false"
    os.environ["MCP_SERVER_SPLUNK_SOC_SPLUNK_APP_ID"] = "7931"
    os.environ["MCP_SERVER_SPLUNK_SOC_SPLUNK_PLATFORM"] = "cloud" if "splunkcloud" in url else "unknown"
    return document


def save_connection(
    *,
    enabled: bool,
    deployment_mode: str,
    discovery_policy: str,
    transport: str,
    auth_method: str,
    url: str,
    bearer_token: str | None,
    timeout_seconds: int,
    saia_tools_enabled: bool,
    splunk_ai_assistant_mode: str,
    allow_saved_search: bool,
    execution_enabled: bool,
    updated_by: str,
) -> dict[str, Any]:
    existing = _read_document()
    document: dict[str, Any] = {
        "enabled": bool(enabled),
        "deployment_mode": deployment_mode.strip().lower(),
        "discovery_policy": discovery_policy.strip().lower(),
        "transport": transport.strip().lower(),
        "auth_method": auth_method.strip().lower(),
        "url": url.strip(),
        "timeout_seconds": int(timeout_seconds),
        "saia_tools_enabled": bool(saia_tools_enabled) and deployment_mode.strip().lower() != "air_gapped",
        "splunk_ai_assistant_mode": "disabled" if deployment_mode.strip().lower() == "air_gapped" else splunk_ai_assistant_mode.strip().lower(),
        "allow_saved_search": bool(allow_saved_search),
        "execution_enabled": bool(execution_enabled),
        "updated_by": str(updated_by or "unknown"),
    }
    if bearer_token:
        document["bearer_token"] = bearer_token
    elif existing.get("bearer_token"):
        document["bearer_token"] = existing["bearer_token"]

    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    apply_to_settings()
    return document


def effective_connection() -> dict[str, Any]:
    return {
        "enabled": bool(settings.splunk_mcp_enabled),
        "server_id": _SPLUNK_SERVER_ID,
        "deployment_mode": settings.ai_soc_environment_mode,
        "discovery_policy": settings.splunk_mcp_discovery_mode,
        "transport": os.environ.get("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http"),
        "auth_method": os.environ.get("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer" if settings.splunk_mcp_token else "none"),
        "url": settings.splunk_mcp_base_url,
        "bearer_token_configured": bool((settings.splunk_mcp_token or "").strip()),
        "timeout_seconds": int(os.environ.get("MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS", "10")),
        "saia_tools_enabled": bool(settings.splunk_saia_tools_enabled) and settings.ai_soc_environment_mode != "air_gapped",
        "splunk_ai_assistant_mode": settings.splunk_ai_assistant_mode,
        "allow_saved_search": bool(settings.splunk_allow_run_saved_search),
        "execution_enabled": os.environ.get("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "false").lower() == "true",
        "source": "override" if _read_document() else "env",
    }
