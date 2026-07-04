"""File-backed override for the Splunk MCP connection settings.

Operators can paste the Splunk MCP endpoint and encrypted token from the
Splunk MCP Server app into Settings instead of editing ``.env``. The secret is
persisted locally, applied to the process env used by the MCP registry loader,
and never returned by API responses.
"""

from __future__ import annotations

import json
import os
import re
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
    if not isinstance(parsed, dict):
        return {}
    return _normalize_document(parsed)


def _normalize_document(document: dict[str, Any]) -> dict[str, Any]:
    if "splunk" in document or "other_servers" in document:
        splunk = document.get("splunk") if isinstance(document.get("splunk"), dict) else {}
        other_servers = document.get("other_servers") if isinstance(document.get("other_servers"), list) else []
        return {
            "splunk": splunk,
            "other_servers": [server for server in other_servers if isinstance(server, dict)],
        }
    return {"splunk": dict(document), "other_servers": []}


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

    splunk = _splunk_document(document)
    other_servers = _other_server_documents(document)

    enabled = (
        bool(splunk.get("enabled"))
        if "enabled" in splunk
        else bool(settings.mcp_mode.strip().lower() == "registry" and settings.splunk_mcp_enabled)
    )
    url = str(splunk.get("url") if "url" in splunk else settings.splunk_mcp_base_url or "").strip()
    token = str(splunk.get("bearer_token") if "bearer_token" in splunk else settings.splunk_mcp_token or "").strip()
    deployment_mode = str(splunk.get("deployment_mode") if "deployment_mode" in splunk else settings.ai_soc_environment_mode or "coe").strip().lower()
    discovery_mode = str(splunk.get("discovery_policy") if "discovery_policy" in splunk else settings.splunk_mcp_discovery_mode or "dynamic").strip().lower()
    transport = str(splunk.get("transport") if "transport" in splunk else os.environ.get("MCP_SERVER_SPLUNK_SOC_TRANSPORT", "streamable_http")).strip().lower()
    auth_method = str(splunk.get("auth_method") if "auth_method" in splunk else os.environ.get("MCP_SERVER_SPLUNK_SOC_AUTH_MODE", "bearer" if token else "none")).strip().lower()
    timeout_seconds = int(splunk.get("timeout_seconds") if "timeout_seconds" in splunk else os.environ.get("MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS", "10") or 10)
    execution_enabled = bool(splunk.get("execution_enabled")) if "execution_enabled" in splunk else os.environ.get("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "false").lower() == "true"
    saia_tools_enabled = bool(splunk.get("saia_tools_enabled")) if "saia_tools_enabled" in splunk else bool(settings.splunk_saia_tools_enabled)
    ai_assistant_mode = str(splunk.get("splunk_ai_assistant_mode") if "splunk_ai_assistant_mode" in splunk else settings.splunk_ai_assistant_mode or "auto").strip().lower()
    allow_saved_search = bool(splunk.get("allow_saved_search")) if "allow_saved_search" in splunk else bool(settings.splunk_allow_run_saved_search)
    server_names = [_SPLUNK_SERVER_ID] if enabled else []
    server_names.extend(_server_id(server) for server in other_servers if bool(server.get("enabled")) and _server_id(server))
    default_server = _SPLUNK_SERVER_ID if enabled else (server_names[0] if server_names else "")
    mode = "registry" if server_names else "mock"
    global_execution_enabled = bool(
        server_names
        and (
            (enabled and execution_enabled)
            or any(bool(server.get("enabled")) and bool(server.get("execution_enabled")) for server in other_servers)
        )
    )

    settings.splunk_mcp_enabled = enabled
    settings.ai_soc_environment_mode = deployment_mode
    settings.splunk_mcp_server_id = _SPLUNK_SERVER_ID
    settings.splunk_mcp_discovery_mode = discovery_mode
    settings.splunk_mcp_base_url = url
    settings.splunk_mcp_token = token
    settings.splunk_saia_tools_enabled = saia_tools_enabled and deployment_mode != "air_gapped"
    settings.splunk_ai_assistant_mode = "disabled" if deployment_mode == "air_gapped" and "splunk_ai_assistant_mode" in splunk else ai_assistant_mode
    settings.splunk_allow_run_saved_search = allow_saved_search
    settings.mcp_mode = mode
    settings.mcp_servers = ",".join(server_names)
    settings.mcp_default_server = default_server or _SPLUNK_SERVER_ID
    settings.mcp_global_execution_enabled = global_execution_enabled

    os.environ["MCP_MODE"] = mode
    os.environ["MCP_SERVERS"] = ",".join(server_names)
    os.environ["MCP_DEFAULT_SERVER"] = default_server or _SPLUNK_SERVER_ID
    os.environ["MCP_GLOBAL_EXECUTION_ENABLED"] = "true" if global_execution_enabled else "false"
    os.environ["MCP_SERVER_SPLUNK_SOC_ENABLED"] = "true" if enabled else "false"
    os.environ["MCP_SERVER_SPLUNK_SOC_TYPE"] = "splunk"
    os.environ["MCP_SERVER_SPLUNK_SOC_TRANSPORT"] = transport
    os.environ["MCP_SERVER_SPLUNK_SOC_URL"] = url
    os.environ["MCP_SERVER_SPLUNK_SOC_AUTH_MODE"] = auth_method
    os.environ["MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN"] = token
    os.environ["MCP_SERVER_SPLUNK_SOC_CONNECT_TIMEOUT_SECONDS"] = str(timeout_seconds)
    os.environ["MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST"] = _tool_allowlist(splunk)
    os.environ["MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED"] = "true" if execution_enabled else "false"
    os.environ["MCP_SERVER_SPLUNK_SOC_SPLUNK_APP_ID"] = "7931"
    os.environ["MCP_SERVER_SPLUNK_SOC_SPLUNK_PLATFORM"] = "cloud" if "splunkcloud" in url else "unknown"
    for server in other_servers:
        _apply_other_server_to_env(server)
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
    existing_splunk = _splunk_document(existing)
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
    for key in ("last_check_status", "last_error", "last_technical_detail", "discovered_tools"):
        if key in existing_splunk:
            document[key] = existing_splunk[key]
    if bearer_token:
        document["bearer_token"] = bearer_token
    elif existing_splunk.get("bearer_token"):
        document["bearer_token"] = existing_splunk["bearer_token"]

    store_document = {
        "splunk": document,
        "other_servers": _other_server_documents(existing),
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store_document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    apply_to_settings()
    return document


def save_other_server(
    *,
    server_id: str,
    display_name: str,
    provider_type: str,
    url: str,
    bearer_token: str | None,
    username: str = "",
    password: str = "",
    command: str = "",
    args: str = "",
    enabled: bool = True,
    transport: str = "streamable_http",
    auth_method: str = "bearer",
    timeout_seconds: int = 10,
    execution_enabled: bool = False,
    discovered_tools: list[Any] | None = None,
    last_check_status: str | None = None,
    last_error: str | None = None,
    last_technical_detail: str | None = None,
    updated_by: str = "unknown",
) -> dict[str, Any]:
    document = _read_document()
    existing = {server["server_id"]: server for server in _other_server_documents(document) if server.get("server_id")}
    clean_id = _server_id({"server_id": server_id})
    if not clean_id or clean_id == _SPLUNK_SERVER_ID:
        raise ValueError("invalid_mcp_server_id")
    previous = existing.get(clean_id, {})
    server_document: dict[str, Any] = {
        "server_id": clean_id,
        "display_name": display_name.strip() or clean_id,
        "provider_type": provider_type.strip().lower(),
        "enabled": bool(enabled),
        "transport": transport.strip().lower(),
        "auth_method": auth_method.strip().lower(),
        "url": url.strip(),
        "username": username.strip(),
        "password": password,
        "command": command.strip(),
        "args": args.strip(),
        "timeout_seconds": int(timeout_seconds),
        "execution_enabled": bool(execution_enabled),
        "discovered_tools": discovered_tools if discovered_tools is not None else previous.get("discovered_tools", []),
        "last_check_status": last_check_status if last_check_status is not None else previous.get("last_check_status"),
        "last_error": last_error if last_error is not None else previous.get("last_error"),
        "last_technical_detail": last_technical_detail if last_technical_detail is not None else previous.get("last_technical_detail"),
        "updated_by": str(updated_by or "unknown"),
    }
    if bearer_token:
        server_document["bearer_token"] = bearer_token
    elif previous.get("bearer_token"):
        server_document["bearer_token"] = previous["bearer_token"]
    existing[clean_id] = server_document
    store_document = {
        "splunk": _splunk_document(document),
        "other_servers": list(existing.values()),
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store_document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    apply_to_settings()
    return server_document


def list_other_servers(*, include_secrets: bool = False) -> list[dict[str, Any]]:
    servers = _other_server_documents(_read_document())
    return [dict(server) if include_secrets else _public_other_server(server) for server in servers]


def get_other_server(server_id: str, *, include_secrets: bool = False) -> dict[str, Any] | None:
    clean_id = _server_id({"server_id": server_id})
    for server in _other_server_documents(_read_document()):
        if _server_id(server) == clean_id:
            return dict(server) if include_secrets else _public_other_server(server)
    return None


def delete_other_server(server_id: str) -> bool:
    document = _read_document()
    clean_id = _server_id({"server_id": server_id})
    servers = [server for server in _other_server_documents(document) if _server_id(server) != clean_id]
    if len(servers) == len(_other_server_documents(document)):
        return False
    _write_document({"splunk": _splunk_document(document), "other_servers": servers})
    apply_to_settings()
    return True


def record_other_server_check(
    server_id: str,
    *,
    status: str,
    failure_reason: str,
    technical_detail: str,
    discovered_tools: list[Any],
) -> dict[str, Any] | None:
    server = get_other_server(server_id, include_secrets=True)
    if server is None:
        return None
    return save_other_server(
        server_id=server["server_id"],
        display_name=str(server.get("display_name") or server["server_id"]),
        provider_type=str(server.get("provider_type") or "generic"),
        url=str(server.get("url") or ""),
        bearer_token=str(server.get("bearer_token") or "") or None,
        username=str(server.get("username") or ""),
        password=str(server.get("password") or ""),
        command=str(server.get("command") or ""),
        args=str(server.get("args") or ""),
        enabled=bool(server.get("enabled")),
        transport=str(server.get("transport") or "streamable_http"),
        auth_method=str(server.get("auth_method") or "none"),
        timeout_seconds=int(server.get("timeout_seconds") or 10),
        execution_enabled=bool(server.get("execution_enabled")),
        discovered_tools=discovered_tools,
        last_check_status=status,
        last_error=failure_reason,
        last_technical_detail=technical_detail,
        updated_by=str(server.get("updated_by") or "unknown"),
    )


def record_splunk_check(
    *,
    status: str,
    failure_reason: str,
    technical_detail: str,
    discovered_tools: list[Any],
) -> dict[str, Any]:
    document = _read_document()
    splunk = dict(_splunk_document(document))
    splunk["last_check_status"] = status
    splunk["last_error"] = failure_reason
    splunk["last_technical_detail"] = technical_detail
    splunk["discovered_tools"] = discovered_tools
    _write_document({"splunk": splunk, "other_servers": _other_server_documents(document)})
    apply_to_settings()
    return splunk


def effective_connection() -> dict[str, Any]:
    document = _read_document()
    splunk = _splunk_document(document) if document else {}
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
        "last_check_status": splunk.get("last_check_status"),
        "last_error": splunk.get("last_error"),
        "last_technical_detail": splunk.get("last_technical_detail"),
        "source": "override" if document else "env",
    }


def _splunk_document(document: dict[str, Any]) -> dict[str, Any]:
    splunk = document.get("splunk") if isinstance(document.get("splunk"), dict) else {}
    return splunk if isinstance(splunk, dict) else {}


def _other_server_documents(document: dict[str, Any]) -> list[dict[str, Any]]:
    servers = document.get("other_servers") if isinstance(document.get("other_servers"), list) else []
    return [server for server in servers if isinstance(server, dict)]


def _server_id(server: dict[str, Any]) -> str:
    raw = str(server.get("server_id") or server.get("name") or "").strip().lower()
    return re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")


def _env_key(server_id: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", server_id.upper()).strip("_")


def _tool_allowlist_for_server(server: dict[str, Any]) -> str:
    explicit = server.get("tool_allowlist")
    if isinstance(explicit, list):
        return ",".join(str(tool).strip() for tool in explicit if str(tool).strip())
    discovered = server.get("discovered_tools")
    if not isinstance(discovered, list):
        return ""
    names: list[str] = []
    for tool in discovered:
        if isinstance(tool, str):
            name = tool
        elif isinstance(tool, dict):
            name = str(tool.get("name") or tool.get("safe_name") or "")
        else:
            name = ""
        if name.strip():
            names.append(name.strip())
    return ",".join(names)


def _apply_other_server_to_env(server: dict[str, Any]) -> None:
    server_id = _server_id(server)
    if not server_id:
        return
    prefix = f"MCP_SERVER_{_env_key(server_id)}_"
    os.environ[prefix + "ENABLED"] = "true" if bool(server.get("enabled")) else "false"
    os.environ[prefix + "TYPE"] = str(server.get("provider_type") or "generic").strip().lower()
    os.environ[prefix + "TRANSPORT"] = str(server.get("transport") or "streamable_http").strip().lower()
    os.environ[prefix + "URL"] = str(server.get("url") or "").strip()
    os.environ[prefix + "COMMAND"] = str(server.get("command") or "").strip()
    os.environ[prefix + "ARGS"] = str(server.get("args") or "").strip()
    os.environ[prefix + "AUTH_MODE"] = str(server.get("auth_method") or "none").strip().lower()
    os.environ[prefix + "BEARER_TOKEN"] = str(server.get("bearer_token") or "").strip()
    os.environ[prefix + "USERNAME"] = str(server.get("username") or "").strip()
    os.environ[prefix + "PASSWORD"] = str(server.get("password") or "")
    os.environ[prefix + "CONNECT_TIMEOUT_SECONDS"] = str(int(server.get("timeout_seconds") or 10))
    os.environ[prefix + "TOOL_ALLOWLIST"] = _tool_allowlist_for_server(server)
    os.environ[prefix + "EXECUTION_ENABLED"] = "true" if bool(server.get("execution_enabled")) else "false"


def _write_document(document: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _public_other_server(server: dict[str, Any]) -> dict[str, Any]:
    return {
        "server_id": _server_id(server),
        "display_name": str(server.get("display_name") or _server_id(server)),
        "provider_type": str(server.get("provider_type") or "generic"),
        "enabled": bool(server.get("enabled")),
        "transport": str(server.get("transport") or "streamable_http"),
        "auth_method": str(server.get("auth_method") or "none"),
        "url_configured": bool(str(server.get("url") or "").strip()),
        "command_configured": bool(str(server.get("command") or "").strip()),
        "auth_configured": _stored_auth_configured(server),
        "timeout_seconds": int(server.get("timeout_seconds") or 10),
        "execution_enabled": bool(server.get("execution_enabled")),
        "last_check_status": server.get("last_check_status"),
        "last_error": server.get("last_error"),
        "last_technical_detail": server.get("last_technical_detail"),
        "discovered_tools": _public_discovered_tools(server),
        "bearer_token_configured": bool(str(server.get("bearer_token") or "").strip()),
        "secrets_returned": False,
    }


def _stored_auth_configured(server: dict[str, Any]) -> bool:
    auth_method = str(server.get("auth_method") or "none").strip().lower()
    if auth_method == "none":
        return True
    if auth_method == "bearer":
        return bool(str(server.get("bearer_token") or "").strip())
    if auth_method == "basic":
        return bool(str(server.get("username") or "").strip() and str(server.get("password") or ""))
    return False


def _public_discovered_tools(server: dict[str, Any]) -> list[dict[str, Any]]:
    raw_tools = server.get("discovered_tools")
    if not isinstance(raw_tools, list):
        return []
    tools: list[dict[str, Any]] = []
    for tool in raw_tools:
        if isinstance(tool, str):
            name = tool.strip()
            if name:
                tools.append({"name": name, "description": "", "capability": "unknown", "categories": [], "blocked": False, "blocked_reason": None})
        elif isinstance(tool, dict):
            name = str(tool.get("name") or tool.get("safe_name") or "").strip()
            if name:
                public = dict(tool)
                public["name"] = name
                tools.append(public)
    return tools
