"""Read-only settings status surface.

Returns non-secret configuration state derived from the central ``Settings``
module. Never returns tokens, passwords, or session secrets — only booleans
indicating whether they are configured.
"""

import base64
import json
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import SUPPORTED_AI_SOC_LLM_MODES, SUPPORTED_ROUTING_MODES, settings
from app.connectors.embeddings import get_embeddings_connector
from app.connectors.llm import get_llm_connector
from app.connectors.llm.registry import SUPPORTED_PROVIDER_TYPES as SUPPORTED_LLM_PROVIDER_TYPES
from app.connectors.llm.registry import load_llm_registry_status
from app.connectors.mcp import get_mcp_connector
from app.connectors.mcp.discovery import classify_mcp_tool
from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.mcp.registry import SUPPORTED_AUTH_MODES as SUPPORTED_MCP_AUTH_MODES
from app.connectors.mcp.registry import SUPPORTED_MCP_TYPES, SUPPORTED_TRANSPORTS
from app.connectors.rag import get_rag_connector
from app.connectors.telemetry import get_telemetry_connector, metrics
from app.knowledge.soc_kb_retriever import soc_kb_status_summary
from app.llm.registry_settings import build_llm_governance_status
from app.providers import ProviderType, mock_asset_inventory_profile, splunk_provider_profile
from app.spl.mcp_source_discovery import run_mcp_source_discovery
from app.spl.source_profile_catalog import list_source_profile_slot_definitions
from app.spl.source_profile_resolver import build_policy_derived_profile, merge_profiles
from app.spl.source_profile_store import (
    load_persisted_source_profile_document,
    merge_mcp_discovery_into_store,
    save_persisted_source_profile,
)
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


class McpVerificationRequest(BaseModel):
    provider_kind: str = "splunk"
    deployment_mode: str = "coe"
    discovery_policy: str = "dynamic"
    transport: str = "streamable_http"
    auth_method: str = "none"
    url: str = ""
    bearer_token: str = ""
    username: str = ""
    password: str = ""
    timeout_seconds: int = 5


_ALLOWED_TOOLS = [
    "splunk_run_query",
    "splunk_get_indexes",
    "splunk_get_metadata",
]


class LlmProviderDraft(BaseModel):
    provider_id: str
    provider_type: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    auth_mode: str = "api_key"


class LlmRoleMappingDraft(BaseModel):
    role: str
    provider: str = ""
    model: str = ""


class LlmSettingsDraftCheckRequest(BaseModel):
    mode: str = "mock"
    enabled: bool = False
    allow_cloud: bool = False
    airgap_enforced: bool = False
    default_provider: str = ""
    default_model: str = ""
    timeout_seconds: int = 30
    max_input_tokens: int = 8000
    max_output_tokens: int = 1024
    temperature: float = 0.2
    streaming: bool = False
    log_prompts: bool = False
    log_responses: bool = False
    redact_secrets: bool = True
    require_context_sufficiency: bool = True
    require_source_refs: bool = True
    allow_insufficient_evidence_response: bool = False
    final_synthesis_enabled: bool = False
    answer_guard_enabled: bool = False
    providers: list[LlmProviderDraft] = []
    role_mappings: list[LlmRoleMappingDraft] = []


class LlmVerificationRequest(BaseModel):
    provider_id: str = ""
    provider_type: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    auth_mode: str = "api_key"
    timeout_seconds: int = 5
    allow_cloud: bool | None = None
    airgap_enforced: bool | None = None
    enable_test_prompt: bool = False


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
            "splunk_live_readiness": evaluate_splunk_mcp_live_readiness(registry=mcp_registry),
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
            "governance": build_llm_governance_status(),
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
            "routing_mode": settings.routing_mode,
            "supported_modes": list(SUPPORTED_ROUTING_MODES),
            "deterministic_router_enabled": True,
            "llm_shadow_enabled": settings.routing_llm_shadow_enabled,
            "llm_shadow_router_enabled": settings.routing_llm_shadow_enabled,
            "llm_assisted_enabled": settings.routing_mode == "llm_assisted_semantic",
            "route_selection_policy": "deterministic_registry_normalization_controls_final_route",
            "production_safe_default": settings.routing_mode in {"deterministic_only", "llm_shadow_only", "llm_assisted_semantic"},
            "llm_can_influence_final_selected_route": settings.routing_mode in {"llm_assisted_semantic", "llm_primary_lab"},
            "llm_influence_boundary": "LLM may suggest intent, evidence needs, and candidate route metadata; deterministic policy controls final skill, use case, tool mapping, and execution.",
            "compare_logging_enabled": settings.routing_compare_logging_enabled,
            "disagreement_logging_sink": "db",
            "db_disagreement_logging_enabled": db_telemetry_enabled and settings.routing_compare_logging_enabled,
            "chat_query_endpoint_wired": True,
            "workflow_planner_enabled": True,
            "workflow_planner_execution_enabled": False,
            "workflow_plan_logging_enabled": db_telemetry_enabled,
            "deterministic_threshold": settings.routing_deterministic_threshold,
            "llm_planner_enabled": settings.routing_mode in {"llm_shadow_only", "llm_assisted_semantic", "llm_primary_lab"},
            "llm_tool_recommendation_enabled": settings.llm_tool_recommendation_enabled,
            "shadow_router_enabled": settings.routing_llm_shadow_enabled and settings.routing_mode == "llm_shadow_only",
            "compare_node_enabled": True,
            "adjudicator_policy": "LLM advisory only; confidence is metadata only; execution gated by normalized_spl",
            "deterministic_tool_mapping": True,
            "llm_output_can_execute_tools_directly": False,
            "execution_authority": "spl_validation.normalized_spl plus MCP execution gate",
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


@router.post("/settings/mcp/validate")
def validate_mcp_settings(payload: McpVerificationRequest | None = None) -> dict:
    draft = _mcp_verification_payload(payload)
    return _mcp_verification_result(draft, action="validate")


@router.post("/settings/mcp/test")
def test_mcp_connection(payload: McpVerificationRequest | None = None) -> dict:
    draft = _mcp_verification_payload(payload)
    return _mcp_verification_result(draft, action="test")


@router.post("/settings/mcp/discover")
def discover_mcp_tools(payload: McpVerificationRequest | None = None) -> dict:
    draft = _mcp_verification_payload(payload)
    return _mcp_verification_result(draft, action="discover")


@router.post("/settings/llm/check")
def check_llm_settings_draft(payload: LlmSettingsDraftCheckRequest) -> dict:
    """Validate a governed-LLM settings draft without persisting anything.

    Mirrors ``/settings/providers/check``: secrets are accepted transiently for
    validation only, never stored and never echoed back. The response exposes
    only ``*_configured`` booleans.
    """
    mode = payload.mode.strip().lower()
    errors: list[str] = []
    warnings: list[str] = []

    if mode not in SUPPORTED_AI_SOC_LLM_MODES:
        errors.append("invalid_mode")
    if payload.timeout_seconds <= 0:
        errors.append("timeout_seconds_must_be_positive")
    if payload.max_input_tokens <= 0:
        errors.append("max_input_tokens_must_be_positive")
    if payload.max_output_tokens <= 0:
        errors.append("max_output_tokens_must_be_positive")
    if not 0.0 <= payload.temperature <= 2.0:
        errors.append("temperature_out_of_range")

    cloud_allowed = payload.allow_cloud and not payload.airgap_enforced
    if payload.allow_cloud and payload.airgap_enforced:
        warnings.append("cloud_allowance_overridden_by_airgap_enforcement")
    if payload.final_synthesis_enabled:
        warnings.append("final_synthesis_lab_deterministic_draft_only_no_live_llm")
    if payload.answer_guard_enabled:
        warnings.append("answer_guard_runs_on_synthesis_draft_when_synthesis_enabled")
    if payload.allow_insufficient_evidence_response and payload.require_source_refs:
        warnings.append("insufficient_evidence_answer_conflicts_with_required_source_refs")

    configured_providers = [
        {
            "provider_id": provider.provider_id.strip()[:120] or "unknown",
            "provider_type": provider.provider_type.strip()[:60],
            "base_url_configured": bool(provider.base_url.strip()),
            "api_key_configured": bool(provider.api_key.strip()),
            "default_model_configured": bool(provider.model.strip()),
        }
        for provider in payload.providers
    ]
    configured_provider_ids = {provider["provider_id"] for provider in configured_providers}
    role_mappings = [
        {
            "role": role.role.strip()[:120],
            "provider": role.provider.strip()[:120] or None,
            "model": role.model.strip()[:160] or None,
            "enabled": bool(role.provider.strip()),
            "execution_eligible": False,
            "validator_required": True,
        }
        for role in payload.role_mappings
    ]
    for role in role_mappings:
        if role["provider"] and role["provider"] not in configured_provider_ids:
            warnings.append(f"role_provider_not_in_draft_provider_list:{role['role']}")
    role_provider_ids = {role["provider"] for role in role_mappings if role["provider"]}
    if {"foundation_sec_instruct", "foundation_sec_reasoning"} & role_provider_ids and not {
        "foundation_sec_instruct",
        "foundation_sec_reasoning",
    }.issubset(role_provider_ids | configured_provider_ids):
        warnings.append("foundation_sec_role_separation_degraded_single_model_configured")
    if mode not in {"mock", "disabled"} and not any(p["base_url_configured"] for p in configured_providers):
        warnings.append("no_provider_endpoint_configured_for_non_mock_mode")

    return {
        "mode": mode,
        "enabled": payload.enabled and mode != "disabled",
        "cloud_allowed": cloud_allowed,
        "cloud_requested": payload.allow_cloud,
        "airgap_enforced": payload.airgap_enforced,
        "default_provider": payload.default_provider.strip() or None,
        "default_model": payload.default_model.strip() or None,
        "final_synthesis_enabled": payload.final_synthesis_enabled,
        "answer_guard_enabled": payload.answer_guard_enabled,
        "context_sufficiency_required": payload.require_context_sufficiency,
        "limits": {
            "timeout_seconds": payload.timeout_seconds,
            "max_input_tokens": payload.max_input_tokens,
            "max_output_tokens": payload.max_output_tokens,
            "temperature": payload.temperature,
            "streaming": payload.streaming,
        },
        "safety": {
            "log_prompts": payload.log_prompts,
            "log_responses": payload.log_responses,
            "redact_secrets": payload.redact_secrets,
            "require_source_refs": payload.require_source_refs,
            "allow_insufficient_evidence_response": payload.allow_insufficient_evidence_response,
        },
        "providers": configured_providers,
        "role_mappings": role_mappings,
        "validation_status": "pass" if not errors else "fail",
        "validation_errors": errors,
        "warnings": warnings,
        "saved": False,
        "not_persisted": True,
        "safe_message": "Draft validated without storing values. Persisted LLM settings are not enabled in this stage; apply changes via environment variables.",
    }


@router.post("/settings/llm/validate")
def validate_llm_settings(payload: LlmVerificationRequest | None = None) -> dict:
    draft = _llm_verification_payload(payload)
    return _llm_verification_result(draft, action="validate")


@router.post("/settings/llm/test")
def test_llm_connection(payload: LlmVerificationRequest | None = None) -> dict:
    draft = _llm_verification_payload(payload)
    return _llm_verification_result(draft, action="test")


@router.post("/settings/llm/models")
def list_llm_models(payload: LlmVerificationRequest | None = None) -> dict:
    draft = _llm_verification_payload(payload)
    return _llm_verification_result(draft, action="models")


# Smoke prompt is fixed and self-contained so the generation check never depends
# on governed evidence, RAG, or the /chat pipeline. This proves the model
# actually generates text end-to-end through the backend; it is NOT a synthesis
# path and never reaches a real answer surface.
_LLM_SMOKE_PROMPT = (
    "You are a SOC assistant. In one short sentence, name the first thing an "
    "analyst should check for a brute-force login alert."
)


@router.post("/settings/llm/smoke")
def smoke_llm_generation(payload: LlmVerificationRequest | None = None) -> dict:
    """Send one fixed prompt to the provider's chat/completions and return the
    generated text. Proves live generation without touching the /chat pipeline.

    Output capped small on purpose: ``_json_request`` clamps the socket timeout
    to 30s, and a local llama.cpp build runs at single-digit tokens/sec, so a
    large completion would time out before it returned.
    """
    draft = _llm_verification_payload(payload)
    errors = _validate_llm_draft(draft)
    if errors:
        return _llm_smoke_payload(
            draft=draft,
            status="Not connected",
            generated=False,
            reachable=False,
            failure_reason=_plain_llm_reason(errors[0]),
            technical_detail=", ".join(errors),
        )
    policy_allowed, policy_reason = _llm_policy_allowed(draft)
    if not policy_allowed:
        return _llm_smoke_payload(
            draft=draft,
            status="Blocked by airgap policy" if policy_reason == "airgap" else "Blocked by cloud policy",
            generated=False,
            reachable=False,
            failure_reason="Provider is blocked by policy.",
            technical_detail=f"blocked_by_{policy_reason}_policy",
        )

    url = draft.base_url.rstrip("/") + "/chat/completions"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    _apply_auth(headers, auth_mode=draft.auth_mode, api_key=draft.api_key)
    body: dict[str, object] = {
        "model": draft.model.strip(),
        "messages": [{"role": "user", "content": _LLM_SMOKE_PROMPT}],
        "max_tokens": 64,
        "temperature": settings.ai_soc_llm_temperature,
        "stream": False,
    }
    started = time.monotonic()
    try:
        data = _json_request(url, headers=headers, timeout=draft.timeout_seconds, body=body)
    except HTTPError as exc:
        return _llm_smoke_payload(
            draft=draft,
            status="Reachable but error",
            generated=False,
            reachable=True,
            failure_reason="Endpoint reached but returned an error during generation.",
            technical_detail=f"http_{exc.code}",
        )
    except URLError as exc:
        return _llm_smoke_payload(
            draft=draft,
            status="Not connected",
            generated=False,
            reachable=False,
            failure_reason="Cannot reach LLM endpoint. Check URL, network, firewall, or that the server is bound where the backend can reach it.",
            technical_detail=_sanitize_detail(f"url_error:{type(getattr(exc, 'reason', exc)).__name__}"),
        )
    except Exception as exc:  # noqa: BLE001 - report any failure as a safe smoke result, never raise to the client.
        return _llm_smoke_payload(
            draft=draft,
            status="Error",
            generated=False,
            reachable=False,
            failure_reason="Generation smoke failed before a completion was returned.",
            technical_detail=_sanitize_detail(type(exc).__name__),
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    text, usage = _extract_llm_completion(data)
    if not text:
        return _llm_smoke_payload(
            draft=draft,
            status="Reachable but empty",
            generated=False,
            reachable=True,
            failure_reason="Endpoint reached but returned no completion text.",
            technical_detail="empty_completion",
            latency_ms=elapsed_ms,
        )
    return _llm_smoke_payload(
        draft=draft,
        status="Generated",
        generated=True,
        reachable=True,
        failure_reason="Live generation works. This is a connectivity smoke only; /chat synthesis is separate.",
        technical_detail="completion_returned",
        generated_text=text,
        usage=usage,
        latency_ms=elapsed_ms,
    )


def _mcp_verification_payload(payload: McpVerificationRequest | None) -> McpVerificationRequest:
    if payload is not None:
        return payload
    return McpVerificationRequest(
        provider_kind="splunk",
        deployment_mode=settings.ai_soc_environment_mode,
        discovery_policy=settings.splunk_mcp_discovery_mode,
        transport="streamable_http",
        auth_method="bearer" if _bool_configured(settings.splunk_mcp_token) else "none",
        url=settings.splunk_mcp_base_url,
        bearer_token=settings.splunk_mcp_token,
    )


def _mcp_verification_result(payload: McpVerificationRequest, *, action: str) -> dict[str, object]:
    checks = _validate_mcp_draft(payload)
    if checks:
        return _mcp_connection_payload(
            status="Not connected",
            url_configured=bool(payload.url.strip()),
            authentication_configured=_mcp_auth_configured(payload),
            reachable=False,
            authenticated=False,
            handshake="failed",
            tools=[],
            failure_reason=_plain_mcp_reason(checks[0]),
            technical_detail=", ".join(checks),
            action=action,
        )

    if action == "validate":
        return _mcp_connection_payload(
            status="Not connected",
            url_configured=bool(payload.url.strip()),
            authentication_configured=_mcp_auth_configured(payload),
            reachable=None,
            authenticated=None,
            handshake="not supported",
            tools=[],
            failure_reason="Settings are valid. Connection has not been tested.",
            technical_detail="validation_only_no_network_call",
            action=action,
        )

    transport = payload.transport.strip().lower()
    discovery_policy = payload.discovery_policy.strip().lower()
    if transport == "stdio" or discovery_policy == "static_only":
        return _mcp_connection_payload(
            status="Blocked by policy",
            url_configured=bool(payload.url.strip()),
            authentication_configured=_mcp_auth_configured(payload),
            reachable=False,
            authenticated=False,
            handshake="not supported",
            tools=[],
            failure_reason="Connection verification is blocked by MCP discovery policy.",
            technical_detail=f"transport={transport};discovery_policy={discovery_policy}",
            action=action,
        )

    response = _fetch_mcp_tools(payload)
    return _mcp_connection_payload(
        status=response["status"],
        url_configured=bool(payload.url.strip()),
        authentication_configured=_mcp_auth_configured(payload),
        reachable=response["reachable"],
        authenticated=response["authenticated"],
        handshake=response["handshake"],
        tools=response["tools"],
        failure_reason=response["failure_reason"],
        technical_detail=response["technical_detail"],
        action=action,
    )


def _validate_mcp_draft(payload: McpVerificationRequest) -> list[str]:
    errors: list[str] = []
    provider_kind = payload.provider_kind.strip().lower()
    deployment_mode = payload.deployment_mode.strip().lower()
    discovery_policy = payload.discovery_policy.strip().lower()
    transport = payload.transport.strip().lower()
    auth_method = payload.auth_method.strip().lower()
    if provider_kind not in SUPPORTED_MCP_TYPES:
        errors.append("provider_kind_is_not_supported")
    if deployment_mode not in {"coe", "customer_test", "production", "air_gapped"}:
        errors.append("deployment_mode_is_not_supported")
    if discovery_policy not in {"dynamic", "restricted", "static_only"}:
        errors.append("discovery_policy_is_not_supported")
    if transport not in SUPPORTED_TRANSPORTS and transport != "mock":
        errors.append("transport_is_not_supported")
    if auth_method not in SUPPORTED_MCP_AUTH_MODES:
        errors.append("authentication_method_is_not_supported")
    if transport in {"streamable_http", "sse"}:
        if not payload.url.strip():
            errors.append("mcp_url_is_required")
        elif not _valid_http_url(payload.url):
            errors.append("mcp_url_is_not_valid")
    if auth_method == "bearer" and not payload.bearer_token.strip():
        errors.append("bearer_token_is_required")
    if auth_method == "basic" and not (payload.username.strip() and payload.password.strip()):
        errors.append("username_and_password_are_required")
    if payload.timeout_seconds <= 0:
        errors.append("timeout_seconds_must_be_positive")
    return errors


def _fetch_mcp_tools(payload: McpVerificationRequest) -> dict[str, object]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    _apply_auth(headers, auth_mode=payload.auth_method, api_key=payload.bearer_token, username=payload.username, password=payload.password)
    endpoint = payload.url.strip()
    technical: list[str] = []
    initialized = False
    tools: list[dict[str, object]] = []
    try:
        init_body = {
            "jsonrpc": "2.0",
            "id": "ai-soc-verify-init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-soc-assistant", "version": "stage-3j-h"},
            },
        }
        init_payload = _json_request(endpoint, headers=headers, body=init_body, timeout=payload.timeout_seconds)
        initialized = "result" in init_payload or "serverInfo" in json.dumps(init_payload)
        tools_payload = _json_request(endpoint, headers=headers, body={"jsonrpc": "2.0", "id": "ai-soc-verify-tools", "method": "tools/list", "params": {}}, timeout=payload.timeout_seconds)
        tools = _extract_mcp_tools(tools_payload, payload.provider_kind)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return {
                "status": "Reachable but authentication failed",
                "reachable": True,
                "authenticated": False,
                "handshake": "failed",
                "tools": [],
                "failure_reason": "Authentication failed. Check bearer token or username/password.",
                "technical_detail": f"http_{exc.code}",
            }
        return {
            "status": "Error",
            "reachable": True,
            "authenticated": exc.code not in {401, 403},
            "handshake": "failed",
            "tools": [],
            "failure_reason": "MCP endpoint returned an error during connection verification.",
            "technical_detail": f"http_{exc.code}",
        }
    except URLError as exc:
        return {
            "status": "Not connected",
            "reachable": False,
            "authenticated": False,
            "handshake": "failed",
            "tools": [],
            "failure_reason": "Cannot reach MCP endpoint. Check URL, network, firewall, or DNS.",
            "technical_detail": _sanitize_detail(f"url_error:{type(getattr(exc, 'reason', exc)).__name__}"),
        }
    except Exception as exc:  # noqa: BLE001
        technical.append(type(exc).__name__)
        return {
            "status": "Error",
            "reachable": False,
            "authenticated": False,
            "handshake": "failed",
            "tools": [],
            "failure_reason": "MCP connection verification failed before tool discovery completed.",
            "technical_detail": _sanitize_detail(",".join(technical)),
        }

    if not tools:
        return {
            "status": "Reachable but no tools discovered",
            "reachable": True,
            "authenticated": True,
            "handshake": "passed" if initialized else "not supported",
            "tools": [],
            "failure_reason": "MCP server responded, but no tools were discovered.",
            "technical_detail": "tools_list_empty",
        }
    if payload.provider_kind.strip().lower() == "splunk" and not any("splunk_core" in tool.get("categories", []) for tool in tools):
        return {
            "status": "Reachable but unsupported MCP server",
            "reachable": True,
            "authenticated": True,
            "handshake": "passed" if initialized else "not supported",
            "tools": tools,
            "failure_reason": "Splunk MCP tools were not found on this server.",
            "technical_detail": "splunk_core_tools_not_discovered",
        }
    return {
        "status": "Connected",
        "reachable": True,
        "authenticated": True,
        "handshake": "passed" if initialized else "not supported",
        "tools": tools,
        "failure_reason": "Connection is valid, but execution tools remain gated by policy.",
        "technical_detail": "safe_discovery_only",
    }


def _mcp_connection_payload(
    *,
    status: str,
    url_configured: bool,
    authentication_configured: bool,
    reachable: bool | None,
    authenticated: bool | None,
    handshake: str,
    tools: list[dict[str, object]],
    failure_reason: str,
    technical_detail: str,
    action: str,
) -> dict[str, object]:
    splunk_core_count = sum(1 for tool in tools if "splunk_core" in tool.get("categories", []))
    saia_count = sum(1 for tool in tools if "saia" in tool.get("categories", []))
    return {
        "action": action,
        "status": status,
        "url_configured": url_configured,
        "authentication_configured": authentication_configured,
        "reachable": reachable,
        "authenticated": authenticated,
        "mcp_handshake": handshake,
        "tools_discovered_count": len(tools),
        "splunk_core_tools_discovered_count": splunk_core_count,
        "saia_tools_discovered_count": saia_count,
        "execution_policy": "gated",
        "last_checked_time": _now_iso(),
        "failure_reason": failure_reason,
        "technical_error_detail": _sanitize_detail(technical_detail),
        "tools": tools,
        "safe_message": failure_reason,
        "secrets_returned": False,
    }


def _extract_mcp_tools(payload: object, provider_kind: str) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    raw_tools = payload.get("tools")
    if raw_tools is None and isinstance(payload.get("result"), dict):
        raw_tools = payload["result"].get("tools")
    tools: list[dict[str, object]] = []
    for raw in raw_tools or []:
        if not isinstance(raw, dict):
            continue
        descriptor = classify_mcp_tool(str(raw.get("name") or ""), str(raw.get("description") or ""), server_type=provider_kind.strip().lower())
        tools.append(descriptor.safe_payload())
    return tools


def _mcp_auth_configured(payload: McpVerificationRequest) -> bool:
    auth_method = payload.auth_method.strip().lower()
    if auth_method == "none":
        return True
    if auth_method == "bearer":
        return bool(payload.bearer_token.strip())
    if auth_method == "basic":
        return bool(payload.username.strip() and payload.password.strip())
    return False


def _plain_mcp_reason(reason: str) -> str:
    if reason in {"mcp_url_is_required", "mcp_url_is_not_valid"}:
        return "MCP URL is missing or invalid."
    if reason in {"bearer_token_is_required", "username_and_password_are_required"}:
        return "Authentication is required but credentials are not configured."
    if reason == "transport_is_not_supported":
        return "MCP transport is not supported."
    if reason == "authentication_method_is_not_supported":
        return "Authentication method is not supported."
    if reason == "provider_kind_is_not_supported":
        return "Provider kind is not supported."
    return "MCP settings are not valid."


def _llm_verification_payload(payload: LlmVerificationRequest | None) -> LlmVerificationRequest:
    if payload is not None:
        return payload
    provider_id = settings.ai_soc_llm_default_provider.strip() or "openai_compatible"
    candidates = {
        "openai_compatible": (
            "openai_compatible",
            settings.ai_soc_llm_openai_base_url,
            settings.ai_soc_llm_openai_api_key,
            settings.ai_soc_llm_openai_model or settings.ai_soc_llm_default_model,
        ),
        "foundation_sec_instruct": (
            "cisco_compatible",
            settings.ai_soc_llm_foundation_sec_instruct_base_url,
            settings.ai_soc_llm_foundation_sec_instruct_api_key,
            settings.ai_soc_llm_foundation_sec_instruct_model or settings.ai_soc_llm_default_model,
        ),
        "foundation_sec_reasoning": (
            "cisco_compatible",
            settings.ai_soc_llm_foundation_sec_reasoning_base_url,
            settings.ai_soc_llm_foundation_sec_reasoning_api_key,
            settings.ai_soc_llm_foundation_sec_reasoning_model or settings.ai_soc_llm_default_model,
        ),
        "local": (
            "ollama",
            settings.ai_soc_llm_local_base_url,
            settings.ai_soc_llm_local_api_key,
            settings.ai_soc_llm_local_model or settings.ai_soc_llm_default_model,
        ),
    }
    provider_type, base_url, api_key, model = candidates.get(provider_id, candidates["openai_compatible"])
    return LlmVerificationRequest(
        provider_id=provider_id,
        provider_type=provider_type,
        base_url=base_url,
        api_key=api_key,
        model=model,
        auth_mode="api_key" if api_key else "none",
        timeout_seconds=settings.ai_soc_llm_timeout_seconds,
    )


def _llm_verification_result(payload: LlmVerificationRequest, *, action: str) -> dict[str, object]:
    errors = _validate_llm_draft(payload)
    policy_allowed, policy_reason = _llm_policy_allowed(payload)
    if errors:
        return _llm_connection_payload(
            status="Not connected",
            payload=payload,
            reachable=False,
            authenticated=False,
            model_available="unknown",
            policy_allowed=policy_allowed,
            models=[],
            failure_reason=_plain_llm_reason(errors[0]),
            technical_detail=", ".join(errors),
            action=action,
        )
    if not policy_allowed:
        status = "Blocked by airgap policy" if policy_reason == "airgap" else "Blocked by cloud policy"
        return _llm_connection_payload(
            status=status,
            payload=payload,
            reachable=False,
            authenticated=False,
            model_available="unknown",
            policy_allowed=False,
            models=[],
            failure_reason="Provider is blocked by airgap policy." if policy_reason == "airgap" else "Cloud LLM is not allowed in this deployment mode.",
            technical_detail=f"blocked_by_{policy_reason}_policy",
            action=action,
        )
    if action == "validate":
        return _llm_connection_payload(
            status="Config valid, not tested",
            payload=payload,
            reachable=None,
            authenticated=None,
            model_available="unknown",
            policy_allowed=True,
            models=[],
            failure_reason="Settings are valid. Connection has not been tested.",
            technical_detail="validation_only_no_network_call",
            action=action,
        )
    if action == "models" and not _llm_supports_model_listing(payload.provider_type):
        return _llm_connection_payload(
            status="Config valid, not tested",
            payload=payload,
            reachable=None,
            authenticated=None,
            model_available="unknown",
            policy_allowed=True,
            models=[],
            failure_reason="Model listing not supported by this provider.",
            technical_detail="model_listing_not_supported",
            action=action,
        )
    response = _fetch_llm_models(payload)
    return _llm_connection_payload(action=action, payload=payload, **response)


def _validate_llm_draft(payload: LlmVerificationRequest) -> list[str]:
    errors: list[str] = []
    provider_type = payload.provider_type.strip().lower()
    if provider_type not in SUPPORTED_LLM_PROVIDER_TYPES and provider_type != "local":
        errors.append("provider_type_is_not_supported")
    if not payload.base_url.strip():
        errors.append("base_url_is_required")
    elif not _valid_http_url(payload.base_url):
        errors.append("base_url_is_not_valid")
    if not payload.model.strip():
        errors.append("model_name_is_required")
    if payload.auth_mode.strip().lower() in {"api_key", "bearer"} and not payload.api_key.strip():
        errors.append("api_key_is_required")
    if payload.timeout_seconds <= 0:
        errors.append("timeout_seconds_must_be_positive")
    return errors


def _llm_policy_allowed(payload: LlmVerificationRequest) -> tuple[bool, str | None]:
    airgap = settings.ai_soc_llm_airgap_enforced if payload.airgap_enforced is None else payload.airgap_enforced
    allow_cloud = settings.ai_soc_llm_allow_cloud if payload.allow_cloud is None else payload.allow_cloud
    is_cloud = _llm_provider_is_cloud(payload.provider_type, payload.base_url)
    if airgap and is_cloud:
        return False, "airgap"
    if not allow_cloud and is_cloud:
        return False, "cloud"
    return True, None


def _fetch_llm_models(payload: LlmVerificationRequest) -> dict[str, object]:
    url = _llm_models_url(payload.base_url)
    headers = {"Accept": "application/json"}
    _apply_auth(headers, auth_mode=payload.auth_mode, api_key=payload.api_key)
    try:
        data = _json_request(url, headers=headers, timeout=payload.timeout_seconds)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return {
                "status": "Reachable but authentication failed",
                "reachable": True,
                "authenticated": False,
                "model_available": "unknown",
                "policy_allowed": True,
                "models": [],
                "failure_reason": "Authentication failed. Check API key.",
                "technical_detail": f"http_{exc.code}",
            }
        if exc.code == 404:
            return {
                "status": "Model not found",
                "reachable": True,
                "authenticated": True,
                "model_available": False,
                "policy_allowed": True,
                "models": [],
                "failure_reason": "Model was not found. Check model name or provider configuration.",
                "technical_detail": "http_404",
            }
        return {
            "status": "Error",
            "reachable": True,
            "authenticated": exc.code not in {401, 403},
            "model_available": "unknown",
            "policy_allowed": True,
            "models": [],
            "failure_reason": "LLM endpoint returned an error during connection verification.",
            "technical_detail": f"http_{exc.code}",
        }
    except URLError as exc:
        return {
            "status": "Not connected",
            "reachable": False,
            "authenticated": False,
            "model_available": "unknown",
            "policy_allowed": True,
            "models": [],
            "failure_reason": "Cannot reach LLM endpoint. Check URL, network, firewall, or DNS.",
            "technical_detail": _sanitize_detail(f"url_error:{type(getattr(exc, 'reason', exc)).__name__}"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "Error",
            "reachable": False,
            "authenticated": False,
            "model_available": "unknown",
            "policy_allowed": True,
            "models": [],
            "failure_reason": "LLM connection verification failed before model checks completed.",
            "technical_detail": _sanitize_detail(type(exc).__name__),
        }
    models = _extract_llm_models(data)
    model_available = payload.model.strip() in models if models else "unknown"
    if model_available is False:
        return {
            "status": "Model not found",
            "reachable": True,
            "authenticated": True,
            "model_available": False,
            "policy_allowed": True,
            "models": models,
            "failure_reason": "Model was not found. Check model name or provider configuration.",
            "technical_detail": "model_missing_from_models_list",
        }
    return {
        "status": "Connected",
        "reachable": True,
        "authenticated": True,
        "model_available": model_available,
        "policy_allowed": True,
        "models": models,
        "failure_reason": "Connection works, but final synthesis is still disabled by configuration.",
        "technical_detail": "models_list_verified" if models else "endpoint_reachable_model_unknown",
    }


def _llm_connection_payload(
    *,
    action: str,
    payload: LlmVerificationRequest,
    status: str,
    reachable: bool | None,
    authenticated: bool | None,
    model_available: bool | str,
    policy_allowed: bool,
    models: list[str],
    failure_reason: str,
    technical_detail: str,
) -> dict[str, object]:
    return {
        "action": action,
        "status": status,
        "base_url_configured": bool(payload.base_url.strip()),
        "api_key_configured": bool(payload.api_key.strip()),
        "default_model_configured": bool(payload.model.strip()),
        "reachable": reachable,
        "authenticated": authenticated,
        "model_available": model_available,
        "policy_allowed": policy_allowed,
        "final_synthesis": "enabled" if settings.ai_soc_llm_final_synthesis_enabled else "disabled",
        "answer_guard": "enabled" if settings.ai_soc_llm_answer_guard_enabled else "disabled",
        "last_checked_time": _now_iso(),
        "failure_reason": failure_reason,
        "technical_error_detail": _sanitize_detail(technical_detail),
        "provider_id": payload.provider_id.strip()[:120] or None,
        "provider_type": payload.provider_type.strip().lower(),
        "model": payload.model.strip()[:160] or None,
        "models": models,
        "models_count": len(models),
        "safe_message": failure_reason,
        "secrets_returned": False,
    }


def _extract_llm_models(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("data", payload.get("models", []))
    names: list[str] = []
    for item in raw or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            model = item.get("id") or item.get("name") or item.get("model")
            if model:
                names.append(str(model)[:160])
    return sorted({name for name in names if name})


def _extract_llm_completion(payload: object) -> tuple[str, dict[str, int]]:
    """Pull the first completion text + token usage from an OpenAI-compatible
    chat.completion body. Returns ("", {}) on any unexpected shape."""
    if not isinstance(payload, dict):
        return "", {}
    text = ""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                text = str(message.get("content") or "").strip()
            if not text:
                text = str(first.get("text") or "").strip()
    usage_raw = payload.get("usage")
    usage: dict[str, int] = {}
    if isinstance(usage_raw, dict):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage_raw.get(key)
            if isinstance(value, int):
                usage[key] = value
    return text[:4000], usage


def _llm_smoke_payload(
    *,
    draft: "LlmVerificationRequest",
    status: str,
    generated: bool,
    reachable: bool,
    failure_reason: str,
    technical_detail: str,
    generated_text: str = "",
    usage: dict[str, int] | None = None,
    latency_ms: int | None = None,
) -> dict[str, object]:
    return {
        "action": "smoke",
        "status": status,
        "generated": generated,
        "reachable": reachable,
        "provider_id": draft.provider_id.strip()[:120] or None,
        "provider_type": draft.provider_type.strip().lower(),
        "model": draft.model.strip()[:160] or None,
        "base_url_configured": bool(draft.base_url.strip()),
        "api_key_configured": bool(draft.api_key.strip()),
        "generated_text": generated_text,
        "usage": usage or {},
        "latency_ms": latency_ms,
        "prompt": _LLM_SMOKE_PROMPT,
        "last_checked_time": _now_iso(),
        "failure_reason": failure_reason,
        "technical_error_detail": _sanitize_detail(technical_detail),
        "safe_message": failure_reason,
        "secrets_returned": False,
    }


def _plain_llm_reason(reason: str) -> str:
    if reason in {"base_url_is_required", "base_url_is_not_valid"}:
        return "LLM base URL is missing or invalid."
    if reason == "model_name_is_required":
        return "Model name is required."
    if reason == "api_key_is_required":
        return "API key is required for this provider."
    if reason == "provider_type_is_not_supported":
        return "LLM provider type is not supported."
    return "LLM settings are not valid."


def _llm_provider_is_cloud(provider_type: str, base_url: str) -> bool:
    provider_type = provider_type.strip().lower()
    if provider_type in {"ollama", "llamacpp", "vllm", "sglang", "tgi", "local"}:
        return False
    host = urlparse(base_url.strip()).hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    return provider_type in {"openai_compatible", "cisco_compatible", "custom_http"}


def _llm_supports_model_listing(provider_type: str) -> bool:
    return provider_type.strip().lower() in {"openai_compatible", "vllm", "sglang", "ollama", "llamacpp", "custom_http", "cisco_compatible"}


def _llm_models_url(base_url: str) -> str:
    stripped = base_url.rstrip("/") + "/"
    if stripped.endswith("/v1/"):
        return urljoin(stripped, "models")
    return urljoin(stripped, "models")


def _json_request(url: str, *, headers: dict[str, str], timeout: int, body: dict[str, object] | None = None) -> object:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, method="POST" if data is not None else "GET", headers=headers)
    with urlopen(request, timeout=min(max(timeout, 1), 30)) as response:  # noqa: S310 - admin-configured verification endpoint.
        raw = response.read(1024 * 256)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _apply_auth(headers: dict[str, str], *, auth_mode: str, api_key: str = "", username: str = "", password: str = "") -> None:
    auth_mode = auth_mode.strip().lower()
    if auth_mode in {"bearer", "api_key"} and api_key.strip():
        headers["Authorization"] = "Bearer " + api_key.strip()
    if auth_mode == "basic" and username.strip() and password.strip():
        token = base64.b64encode(f"{username.strip()}:{password.strip()}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _sanitize_detail(value: str) -> str:
    text = str(value)
    text = text.replace(settings.splunk_mcp_token, "[redacted]") if settings.splunk_mcp_token else text
    for secret in (
        settings.ai_soc_llm_openai_api_key,
        settings.ai_soc_llm_foundation_sec_instruct_api_key,
        settings.ai_soc_llm_foundation_sec_reasoning_api_key,
        settings.ai_soc_llm_local_api_key,
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    text = text.replace("Authorization", "Auth[redacted]")
    return text[:500]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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


class SourceProfileSaveRequest(BaseModel):
    values: dict[str, str] = {}


@router.get("/settings/source-profiles")
def get_source_profile_settings() -> dict:
    document = load_persisted_source_profile_document()
    values = dict(document.get("values") or {})
    effective = merge_profiles(build_policy_derived_profile(), values)
    mcp_preview, mcp_trace = run_mcp_source_discovery()
    return {
        "slots": list_source_profile_slot_definitions(),
        "values": values,
        "field_sources": dict(document.get("field_sources") or {}),
        "effective_profile_preview": effective,
        "mcp_discovery_preview": mcp_preview,
        "mcp_discovery_trace": mcp_trace,
        "orchestration_order": [
            "policy_env",
            "coe_store",
            "rag_kb",
            "chat_session",
            "mcp_discovery",
        ],
        "conflict_preference": "mcp_discovery_over_coe_store",
        "updated_at": document.get("updated_at"),
        "updated_by": document.get("updated_by"),
        "store_path_configured": bool(getattr(settings, "ai_soc_source_profile_store_path", "")),
    }


@router.put("/settings/source-profiles")
def save_source_profile_settings(payload: SourceProfileSaveRequest) -> dict:
    document = save_persisted_source_profile(payload.values, updated_by="coe_ui")
    return {
        "saved": True,
        "values": document.get("values") or {},
        "field_sources": document.get("field_sources") or {},
        "updated_at": document.get("updated_at"),
        "updated_by": document.get("updated_by"),
    }


@router.post("/settings/source-profiles/discover-from-mcp")
def discover_source_profiles_from_mcp() -> dict:
    discovered, trace = run_mcp_source_discovery()
    document = merge_mcp_discovery_into_store(discovered, overwrite=True)
    return {
        "saved": True,
        "discovered_slots": list(discovered.keys()),
        "values": document.get("values") or {},
        "field_sources": document.get("field_sources") or {},
        "mcp_discovery_trace": trace,
        "updated_at": document.get("updated_at"),
        "updated_by": document.get("updated_by"),
    }
