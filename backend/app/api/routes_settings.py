"""Read-only settings status surface.

Returns non-secret configuration state derived from the central ``Settings``
module. Never returns tokens, passwords, or session secrets — only booleans
indicating whether they are configured.
"""

from fastapi import APIRouter

from app.config import settings
from app.connectors.embeddings import get_embeddings_connector
from app.connectors.llm import get_llm_connector
from app.connectors.llm.registry import load_llm_registry_status
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.rag import get_rag_connector
from app.connectors.telemetry import get_telemetry_connector, metrics

router = APIRouter()


_ALLOWED_TOOLS = [
    "splunk_run_query",
    "splunk_get_indexes",
    "splunk_get_metadata",
]


def _bool_configured(value: str) -> bool:
    return bool(value and value.strip())


def _safe_status(status: object) -> dict[str, object]:
    return {
        "mode": getattr(status, "mode", "unknown"),
        "configured": bool(getattr(status, "configured", False)),
        "available": bool(getattr(status, "available", False)),
        "detail": str(getattr(status, "detail", "unknown")),
        "implemented": bool(getattr(status, "implemented", True)),
        "fallback": getattr(status, "fallback", None),
    }


@router.get("/settings/status")
def settings_status() -> dict:
    mcp_status = get_mcp_connector().health()
    mcp_registry = load_mcp_registry_status()
    rag_status = get_rag_connector().health()
    llm_status = get_llm_connector().health()
    llm_registry = load_llm_registry_status()
    embeddings_status = get_embeddings_connector().health()
    telemetry_status = get_telemetry_connector().health()
    telemetry_sink = settings.ai_soc_telemetry_sink.strip().lower()
    db_telemetry_enabled = settings.telemetry_mode.strip().lower() == "db" and telemetry_sink in {"db", "both"}
    splunk_write_enabled = False
    splunk_sink_status = "not_implemented" if telemetry_sink in {"splunk", "both"} else "disabled"

    telemetry_counters = metrics.snapshot()
    return {
        "mcp": {
            "enabled": mcp_registry.mode == "registry" and any(server.enabled for server in mcp_registry.servers),
            "mode": mcp_registry.mode,
            "default_server": mcp_registry.default_server,
            "global_execution_enabled": mcp_registry.global_execution_enabled,
            "configured": mcp_registry.configured,
            "available": mcp_registry.available,
            "implemented": mcp_registry.implemented,
            "fallback": mcp_status.fallback,
            "status_detail": "connection_readiness_only" if mcp_registry.mode == "registry" else mcp_status.detail,
            "servers": [_mcp_server_payload(server) for server in mcp_registry.servers],
            "base_url_configured": _bool_configured(settings.splunk_mcp_base_url),
            "token_configured": _bool_configured(settings.splunk_mcp_token),
            "allowed_tools": _ALLOWED_TOOLS,
            "allowed_indexes": ["auth", "wineventlog", "linux_secure"],
            "allowed_sourcetypes": ["windows:security", "linux:audit", "auth0:log"],
            "timeout_seconds": 60,
            "max_rows": 1000,
            "last_check_status": "not_checked",
        },
        "rag": {
            "enabled": settings.rag_mode != "mock",
            "mode": rag_status.mode,
            "configured": rag_status.configured,
            "available": rag_status.available,
            "implemented": rag_status.implemented,
            "fallback": rag_status.fallback,
            "status_detail": rag_status.detail,
            "vault_path": "knowledge-vault",
            "approved_documents": 0,
            "draft_documents": 0,
            "vector_store": "not_connected",
            "keyword_index": "mock",
            "knowledge_graph": "mock",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "embedding_model": "not_configured",
            "last_ingestion_status": "never",
        },
        "llm": {
            "enabled": any(provider.enabled for provider in llm_registry.providers),
            "mode": llm_status.mode,
            "providers_configured": llm_registry.providers_configured,
            "default_provider": llm_registry.default_provider,
            "router_provider": llm_registry.router_provider,
            "synthesis_provider": llm_registry.synthesis_provider,
            "reasoning_provider": llm_registry.reasoning_provider,
            "teacher_provider": llm_registry.teacher_provider,
            "global_concurrency": llm_registry.global_concurrency,
            "concurrency_per_provider": llm_registry.concurrency_per_provider,
            "health_canary_enabled": llm_registry.health_canary_enabled,
            "role_resolution": llm_registry.role_resolution,
            "providers": [_llm_provider_payload(provider) for provider in llm_registry.providers],
            "configured": llm_registry.configured,
            "available": llm_registry.available,
            "implemented": llm_registry.implemented,
            "fallback": llm_status.fallback,
            "status_detail": "connection_readiness_only" if llm_registry.providers_configured != ["mock"] else llm_status.detail,
            "primary_model": _primary_model_name(llm_registry),
            "reasoning_enabled": settings.reasoning_enabled,
            "instruct_endpoint_configured": _bool_configured(settings.foundation_sec_instruct_url),
            "reasoning_endpoint_configured": _bool_configured(settings.foundation_sec_reasoning_url),
            "temperature": 0.2,
            "timeout_seconds": llm_registry.timeout_seconds,
            "max_context_tokens": 8000,
        },
        "embeddings": {
            **_safe_status(embeddings_status),
            "enabled": settings.embeddings_mode != "mock",
            "model": "mock-deterministic" if embeddings_status.mode == "mock" else "local-placeholder",
        },
        "telemetry": {
            **_safe_status(telemetry_status),
            "enabled": settings.telemetry_mode != "none" and telemetry_sink != "none",
            "sink": telemetry_sink,
            "database_telemetry_enabled": db_telemetry_enabled,
            "splunk_write_enabled": splunk_write_enabled,
            "splunk_sink_status": splunk_sink_status,
            "message": "Splunk write is disabled by default. AI-SOC telemetry is stored in the application database.",
        },
        "routing": {
            "mode": settings.routing_mode,
            "deterministic_router_enabled": True,
            "llm_shadow_router_enabled": settings.routing_llm_shadow_enabled,
            "compare_logging_enabled": settings.routing_compare_logging_enabled,
            "disagreement_logging_sink": "db",
            "db_disagreement_logging_enabled": db_telemetry_enabled and settings.routing_compare_logging_enabled,
            "chat_query_endpoint_wired": True,
            "workflow_planner_enabled": True,
            "workflow_planner_execution_enabled": False,
            "workflow_plan_logging_enabled": db_telemetry_enabled,
            "deterministic_threshold": settings.routing_deterministic_threshold,
            "llm_planner_enabled": True,
            "shadow_router_enabled": True,
            "compare_node_enabled": True,
            "adjudicator_policy": "prefer_planner_unless_low_confidence",
            "confidence_thresholds": {"high": 0.75, "medium": 0.55, "low": 0.55},
            "fallback_policy": "deterministic_on_planner_failure",
        },
        "safeguards": {
            "spl_validator_enabled": settings.spl_validation_enabled,
            "blocked_spl_commands": [item.strip() for item in settings.spl_blocked_commands.split(",") if item.strip()],
            "allowed_spl_commands": [item.strip() for item in settings.spl_allowed_commands.split(",") if item.strip()],
            "allowed_indexes": [item.strip() for item in settings.spl_allowed_indexes.split(",") if item.strip()],
            "allowed_sourcetypes": [item.strip() for item in settings.spl_allowed_sourcetypes.split(",") if item.strip()],
            "max_result_limit": settings.spl_max_result_limit,
            "time_range_required": True,
            "aggregation_required": True,
            "raw_event_dump_blocked": True,
            "write_approval_required": True,
            "evidence_validation_enabled": True,
            "prompt_injection_filter_enabled": True,
        },
        "observability": {
            "telemetry_enabled": settings.telemetry_mode != "none" and telemetry_sink != "none",
            "trace_logging_enabled": settings.debug_trace_enabled,
            "audit_sink_status": telemetry_status.detail,
            "telemetry_sink": telemetry_sink,
            "database_telemetry_enabled": db_telemetry_enabled,
            "splunk_write_enabled": splunk_write_enabled,
            "splunk_sink_status": splunk_sink_status,
            "telemetry_write_failures": telemetry_counters.get("telemetry_write_failures", 0),
            "recent_trace": None,
            "planner_deterministic_mismatch_count": 0,
            "fallback_count": 0,
        },
    }


def _mcp_server_payload(server: object) -> dict[str, object]:
    return {
        "name": getattr(server, "name", "unknown"),
        "type": getattr(server, "type", "generic"),
        "enabled": bool(getattr(server, "enabled", False)),
        "implemented": bool(getattr(server, "implemented", False)),
        "configured": bool(getattr(server, "configured", False)),
        "available": bool(getattr(server, "available", False)),
        "transport": getattr(server, "transport", "unknown"),
        "url_configured": bool(getattr(server, "url_configured", False)),
        "command_configured": bool(getattr(server, "command_configured", False)),
        "auth_mode": getattr(server, "auth_mode", "none"),
        "auth_configured": bool(getattr(server, "auth_configured", False)),
        "execution_enabled": bool(getattr(server, "execution_enabled", False)),
        "discovered_tools_count": int(getattr(server, "discovered_tools_count", 0)),
        "discovered_tools_safe_names": list(getattr(server, "discovered_tools_safe_names", [])),
        "blocked_tools_count": int(getattr(server, "blocked_tools_count", 0)),
        "blocked_tools_safe_names": list(getattr(server, "blocked_tools_safe_names", [])),
        "last_error": getattr(server, "last_error", None),
        "splunk_app_id": getattr(server, "splunk_app_id", None),
        "splunk_platform": getattr(server, "splunk_platform", None),
        "search_execution_allowed": getattr(server, "search_execution_allowed", None),
        "saia_spl_generation_allowed": getattr(server, "saia_spl_generation_allowed", None),
        "knowledge_object_discovery_allowed": getattr(server, "knowledge_object_discovery_allowed", None),
        "list_tools_allowed": getattr(server, "list_tools_allowed", None),
    }


def _llm_provider_payload(provider: object) -> dict[str, object]:
    return {
        "name": getattr(provider, "name", "unknown"),
        "type": getattr(provider, "type", "mock"),
        "family": getattr(provider, "family", "other"),
        "model_role": getattr(provider, "model_role", "general"),
        "enabled": bool(getattr(provider, "enabled", False)),
        "implemented": bool(getattr(provider, "implemented", False)),
        "configured": bool(getattr(provider, "configured", False)),
        "available": bool(getattr(provider, "available", False)),
        "model": getattr(provider, "model", ""),
        "base_url_configured": bool(getattr(provider, "base_url_configured", False)),
        "api_key_configured": bool(getattr(provider, "api_key_configured", False)),
        "auth_mode": getattr(provider, "auth_mode", "none"),
        "context_tokens": getattr(provider, "context_tokens", None),
        "max_output_tokens": getattr(provider, "max_output_tokens", None),
        "supports_streaming": bool(getattr(provider, "supports_streaming", False)),
        "supports_json_mode": bool(getattr(provider, "supports_json_mode", False)),
        "supports_tool_calling": bool(getattr(provider, "supports_tool_calling", False)),
        "concurrency_limit": int(getattr(provider, "concurrency_limit", 1)),
        "last_error": getattr(provider, "last_error", None),
    }


def _primary_model_name(registry: object) -> str:
    providers = getattr(registry, "providers", [])
    resolved = getattr(registry, "role_resolution", {}).get("router")
    for provider in providers:
        if getattr(provider, "name", None) == resolved:
            return str(getattr(provider, "model", "") or provider.name)
    return "mock-model"
