"""Read-only settings status surface.

Returns non-secret configuration state derived from the central ``Settings``
module. Never returns tokens, passwords, or session secrets — only booleans
indicating whether they are configured.
"""

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.connectors.embeddings import get_embeddings_connector
from app.connectors.llm import get_llm_connector
from app.connectors.llm.registry import load_llm_registry_status
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.rag import get_rag_connector
from app.connectors.telemetry import get_telemetry_connector, metrics
from app.knowledge.soc_kb_retriever import soc_kb_status_summary
from app.providers import ProviderType, mock_asset_inventory_profile, splunk_provider_profile
from app.splunk.capabilities import build_splunk_capability_profile

router = APIRouter()


class ProviderDraftCheckRequest(BaseModel):
    provider_id: str
    display_name: str = ""
    provider_type: str
    environment_mode: str = "coe"
    enabled: bool = False
    discovery_mode: str = "restricted"
    transport: str = "streamable_http"
    auth_mode: str = "none"
    base_url: str = ""
    auth_token: str = ""
    username: str = ""
    password: str = ""
    notes: str = ""


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
    splunk_capability = build_splunk_capability_profile(mcp_registry)
    rag_status = get_rag_connector().health()
    soc_kb_status = soc_kb_status_summary()
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
            "discovery_enabled": True,
            "discovery_status": "mock" if mcp_registry.mode == "mock" else "configured_unavailable_without_real_adapter",
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
            "splunk_capability": splunk_capability.model_dump(),
            "environment_mode": splunk_capability.environment_mode,
            "splunk_mcp_enabled": settings.splunk_mcp_enabled,
            "splunk_mcp_discovery_mode": settings.splunk_mcp_discovery_mode,
            "splunk_ai_assistant_mode": settings.splunk_ai_assistant_mode,
            "splunk_saia_tools_enabled": settings.splunk_saia_tools_enabled,
            "splunk_saia_require_discovery": settings.splunk_saia_require_discovery,
            "splunk_run_query_require_validation": settings.splunk_run_query_require_validation,
            "splunk_allow_run_saved_search": settings.splunk_allow_run_saved_search,
            "fallback_required": splunk_capability.fallback_required,
            "discovered_core_tool_count": len(splunk_capability.available_core_tools),
            "discovered_saia_tool_count": len(splunk_capability.available_saia_tools),
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
            "repository_backend_type": soc_kb_status["repository_backend_type"],
            "retrieval_mode": soc_kb_status["retrieval_mode"],
            "vector_backend": soc_kb_status["vector_backend"],
            "vector_store": soc_kb_status["vector_backend"],
            "keyword_index": "deterministic_schema_keyword",
            "knowledge_graph": "placeholder" if soc_kb_status["graph_expansion_enabled"] else "disabled",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "embedding_model": soc_kb_status["embedding_model"],
            "reranker_model": soc_kb_status["reranker_model"],
            "embedding_indexing_enabled": soc_kb_status["embedding_indexing_enabled"],
            "reranker_enabled": soc_kb_status["reranker_enabled"],
            "graph_expansion_enabled": soc_kb_status["graph_expansion_enabled"],
            "last_ingestion_status": "never",
            "soc_kb": soc_kb_status,
            "soc_kb_retrieval_enabled": soc_kb_status["retrieval_enabled"],
            "collections_configured_count": soc_kb_status["collections_configured_count"],
            "documents_total_count": soc_kb_status["documents_total_count"],
            "eligible_current_approved_document_count": soc_kb_status["eligible_current_approved_document_count"],
            "draft_count": soc_kb_status["draft_count"],
            "retired_rejected_count": soc_kb_status["retired_rejected_count"],
            "superseded_count": soc_kb_status["superseded_count"],
            "validation_warning_count": soc_kb_status["validation_warning_count"],
            "import_batch_count": soc_kb_status["import_batch_count"],
            "environment": soc_kb_status["environment"],
            "direct_to_llm": False,
            "final_synthesis_enabled": False,
            "llm_selection_enabled": False,
            "llm_ambiguity_assist_enabled": soc_kb_status["llm_ambiguity_assist_enabled"],
            "hybrid_placeholder_enabled": soc_kb_status["hybrid_placeholder_enabled"],
            "graph_placeholder_enabled": soc_kb_status["graph_placeholder_enabled"],
            "reranker": {
                "enabled": soc_kb_status["reranker_enabled"],
                "provider": soc_kb_status["reranker_provider"],
                "model": soc_kb_status["reranker_model"],
                "configured": soc_kb_status["reranker_configured"],
                "available": soc_kb_status["reranker_available"],
            },
            "ambiguity_assist": soc_kb_status["ambiguity_assist"],
            "import_prompt_available": soc_kb_status["import_prompt_available"],
            "import_validation_enabled": soc_kb_status["import_validation_enabled"],
            "manual_edit_publish_available": soc_kb_status["manual_edit_publish_available"],
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
            "tool_recommendation_enabled": settings.llm_tool_recommendation_enabled,
            "direct_mcp_tool_calling_enabled": False,
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
            "llm_tool_recommendation_enabled": settings.llm_tool_recommendation_enabled,
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
            "direct_llm_to_mcp_tool_calling": False,
        },
    }


@router.get("/settings/providers/status")
def provider_settings_status() -> dict:
    mcp_registry = load_mcp_registry_status()
    splunk_capability = build_splunk_capability_profile(mcp_registry)
    splunk_provider = splunk_provider_profile(splunk_capability)
    mock_asset_provider = mock_asset_inventory_profile()
    providers = [
        _provider_payload(
            provider=splunk_provider,
            display_name="Splunk MCP",
            enabled=settings.splunk_mcp_enabled,
            status="active" if splunk_provider.available else "configured_unavailable",
            discovered_tools_count=len(splunk_capability.available_tools),
            last_discovered=splunk_capability.discovered_at,
        ),
        _provider_payload(
            provider=mock_asset_provider,
            display_name="Mock Asset Inventory",
            enabled=True,
            status="active",
            discovered_tools_count=len(mock_asset_provider.discovered_operations),
            last_discovered=None,
        ),
    ]

    return {
        "providers": providers,
        "provider_types": [ProviderType.SPLUNK_MCP.value, ProviderType.ASSET_INVENTORY.value],
        "splunk_capability": splunk_capability.model_dump(),
        "saia": {
            "splunk_ai_assistant_mode": settings.splunk_ai_assistant_mode,
            "saia_discovered": splunk_capability.saia_available,
            "saia_usable": splunk_capability.saia_usable,
            "fallback_active": splunk_capability.fallback_required,
            "features": {
                "generate_spl": settings.splunk_use_saia_generate_spl,
                "explain_spl": settings.splunk_use_saia_explain_spl,
                "optimize_spl": settings.splunk_use_saia_optimize_spl,
                "ask_splunk_question": settings.splunk_use_saia_ask_question,
            },
        },
        "tool_groups": _tool_groups(mcp_registry, splunk_capability),
        "notes": [
            "Read-only provider readiness surface.",
            "Secrets and credential values are never returned.",
            "Only Splunk MCP and mock asset inventory are active in this stage.",
        ],
    }


@router.post("/settings/providers/check")
def check_provider_draft(payload: ProviderDraftCheckRequest) -> dict:
    provider_type = payload.provider_type.strip()
    transport = payload.transport.strip()
    auth_mode = payload.auth_mode.strip()
    base_url = payload.base_url.strip()
    validation_errors: list[str] = []

    if provider_type not in {ProviderType.SPLUNK_MCP.value, ProviderType.ASSET_INVENTORY.value}:
        validation_errors.append("provider_type_not_supported_in_this_stage")
    if payload.environment_mode not in {"coe", "customer_test", "production", "air_gapped"}:
        validation_errors.append("invalid_environment_mode")
    if payload.discovery_mode not in {"dynamic", "restricted", "static_only"}:
        validation_errors.append("invalid_discovery_mode")
    if transport not in {"streamable_http", "sse", "stdio", "mock"}:
        validation_errors.append("invalid_transport")
    if auth_mode not in {"none", "bearer", "basic"}:
        validation_errors.append("invalid_auth_mode")
    if provider_type == ProviderType.SPLUNK_MCP.value and transport in {"streamable_http", "sse"} and not base_url:
        validation_errors.append("base_url_required_for_http_transport")
    if auth_mode == "bearer" and not payload.auth_token.strip():
        validation_errors.append("auth_token_required_for_bearer_mode")
    if auth_mode == "basic" and not (payload.username.strip() and payload.password.strip()):
        validation_errors.append("username_and_password_required_for_basic_mode")

    connection = _provider_connection_check(provider_type=provider_type, transport=transport, base_url=base_url, auth_mode=auth_mode, auth_token=payload.auth_token) if not validation_errors else _connection_result("not_checked", "validation_failed")
    return {
        "provider_id": payload.provider_id.strip()[:120],
        "provider_type": provider_type,
        "enabled": payload.enabled,
        "environment_mode": payload.environment_mode,
        "discovery_mode": payload.discovery_mode,
        "transport": transport,
        "auth_mode": auth_mode,
        "base_url_configured": bool(base_url),
        "auth_token_configured": bool(payload.auth_token.strip()),
        "username_configured": bool(payload.username.strip()),
        "password_configured": bool(payload.password.strip()),
        "validation_status": "pass" if not validation_errors else "fail",
        "validation_errors": validation_errors,
        "connection_check": connection,
        "saved": False,
        "not_persisted": True,
        "safe_message": "Draft checked without storing secrets. Persisted provider settings are not enabled in this stage.",
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
        "discovered_tools": list(getattr(server, "discovered_tools", [])),
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


def _provider_payload(
    *,
    provider: object,
    display_name: str,
    enabled: bool,
    status: str,
    discovered_tools_count: int,
    last_discovered: str | None,
) -> dict[str, object]:
    return {
        "provider_id": getattr(provider, "provider_id", "unknown"),
        "display_name": display_name,
        "provider_type": getattr(getattr(provider, "provider_type", None), "value", str(getattr(provider, "provider_type", "unknown"))),
        "enabled": enabled,
        "status": status,
        "environment_mode": getattr(provider, "environment_mode", settings.ai_soc_environment_mode),
        "available": bool(getattr(provider, "available", False)),
        "auth_configured": bool(getattr(provider, "auth_configured", False)),
        "discovered_operations": _enum_values(getattr(provider, "discovered_operations", [])),
        "allowed_operations": _enum_values(getattr(provider, "allowed_operations", [])),
        "blocked_operations": _enum_values(getattr(provider, "blocked_operations", [])),
        "discovered_operations_count": len(getattr(provider, "discovered_operations", [])),
        "discovered_tools_count": discovered_tools_count,
        "hil_required_operations_count": len(getattr(provider, "hil_required_operations", [])),
        "hil_required_operations": _enum_values(getattr(provider, "hil_required_operations", [])),
        "read_only_supported": bool(getattr(provider, "read_only_supported", True)),
        "write_supported": bool(getattr(provider, "write_supported", False)),
        "evidence_output_supported": bool(getattr(provider, "evidence_output_supported", True)),
        "fallback_required": bool(getattr(provider, "fallback_required", False)),
        "warnings": list(getattr(provider, "warnings", [])),
        "last_discovered": last_discovered,
        "planned": False,
        "actions": {"view": True, "discover": False, "edit": False},
    }


def _tool_groups(registry: object, splunk_capability: object) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = {category: [] for category in _tool_group_categories()}
    for server in getattr(registry, "servers", []):
        for tool in getattr(server, "discovered_tools", []):
            category = _tool_category(tool)
            groups.setdefault(category, []).append(_tool_payload(server, tool, category, splunk_capability))
    if not groups["asset_lookup"]:
        groups["asset_lookup"].append(
            {
                "provider_id": "mock_asset_inventory",
                "server_name": "mock_asset_inventory",
                "tool_name": "mock_asset_lookup",
                "category": "asset_lookup",
                "allowed": True,
                "blocked": False,
                "blocked_reason": None,
                "requires_hil": False,
                "execution_eligible": False,
                "source_evidence_supported": True,
                "description": "Mock read-only asset lookup.",
            }
        )
    return groups


def _tool_group_categories() -> list[str]:
    return [
        "discovery",
        "context_lookup",
        "event_query",
        "asset_lookup",
        "candidate_generation",
        "explanation",
        "optimization",
        "execution",
        "saved_search_execution",
        "write_action",
        "admin_action",
        "unknown",
    ]


def _tool_payload(server: object, tool: dict[str, object], category: str, splunk_capability: object) -> dict[str, object]:
    name = str(tool.get("name") or "unknown")
    blocked = bool(tool.get("blocked"))
    saved_search_blocked = category == "saved_search_execution" and not bool(getattr(splunk_capability, "run_saved_search_allowed", False))
    execution_eligible = category == "event_query" and not blocked and not saved_search_blocked and bool(getattr(splunk_capability, "run_query_requires_validation", True))
    return {
        "provider_id": getattr(server, "name", "unknown"),
        "server_name": getattr(server, "name", "unknown"),
        "tool_name": name,
        "category": category,
        "allowed": bool(not blocked and not saved_search_blocked and category not in {"write_action", "admin_action", "unknown"}),
        "blocked": bool(blocked or saved_search_blocked or category in {"write_action", "admin_action"}),
        "blocked_reason": "saved_search_execution_disabled" if saved_search_blocked else tool.get("blocked_reason"),
        "requires_hil": bool(category == "saved_search_execution" and getattr(splunk_capability, "run_saved_search_requires_hil", True)),
        "execution_eligible": execution_eligible,
        "source_evidence_supported": category in {"event_query", "asset_lookup"},
        "description": str(tool.get("description") or ""),
    }


def _tool_category(tool: dict[str, object]) -> str:
    categories = {str(item) for item in tool.get("categories", []) or []}
    capability = str(tool.get("capability") or "unknown")
    name = str(tool.get("name") or "").lower()
    if "saved_search_execution" in categories or capability == "saved_search_execution":
        return "saved_search_execution"
    if "candidate_generation" in categories or capability == "candidate_generation":
        return "candidate_generation"
    if "explanation" in categories or capability == "explanation":
        return "explanation"
    if "optimization" in categories or capability == "optimization":
        return "optimization"
    if "admin_or_sensitive" in categories:
        return "admin_action"
    if capability == "spl_search":
        return "event_query" if name in {"run_splunk_query", "splunk_run_query"} else "execution"
    if capability in {"metadata_lookup", "knowledge_object_discovery", "splunk_guidance"}:
        return "context_lookup"
    if capability == "asset_lookup":
        return "asset_lookup"
    if capability == "ticket_lookup":
        return "context_lookup"
    return "unknown"


def _enum_values(items: object) -> list[str]:
    return [getattr(item, "value", str(item)) for item in list(items or [])]


def _provider_connection_check(*, provider_type: str, transport: str, base_url: str, auth_mode: str, auth_token: str) -> dict[str, object]:
    if provider_type == ProviderType.ASSET_INVENTORY.value:
        return _connection_result("pass", "mock_asset_inventory_available")
    if transport == "mock":
        return _connection_result("pass", "mock_transport_available")
    if transport == "stdio":
        return _connection_result("not_checked", "stdio_transport_requires_server_process")
    if not base_url:
        return _connection_result("not_checked", "base_url_not_configured")
    request = Request(base_url, method="HEAD")
    if auth_mode == "bearer" and auth_token.strip():
        request.add_header("Authorization", f"Bearer {auth_token.strip()}")
    try:
        with urlopen(request, timeout=3) as response:  # noqa: S310 - admin-supplied endpoint, no persistence.
            return _connection_result("pass", f"http_{response.status}")
    except HTTPError as exc:
        if exc.code in {200, 204, 301, 302, 401, 403, 404, 405}:
            return _connection_result("reachable", f"http_{exc.code}")
        return _connection_result("fail", f"http_{exc.code}")
    except URLError as exc:
        return _connection_result("fail", f"url_error:{type(exc.reason).__name__ if hasattr(exc, 'reason') else type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        return _connection_result("fail", type(exc).__name__)


def _connection_result(status: str, reason: str) -> dict[str, object]:
    return {
        "status": status,
        "reason": reason,
        "real_connection_attempted": status not in {"not_checked"},
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
