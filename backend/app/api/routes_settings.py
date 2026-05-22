"""Read-only settings status surface.

Returns non-secret configuration state derived from the central ``Settings``
module. Never returns tokens, passwords, or session secrets — only booleans
indicating whether they are configured.
"""

from fastapi import APIRouter

from app.config import settings
from app.connectors.embeddings import get_embeddings_connector
from app.connectors.llm import get_llm_connector
from app.connectors.mcp import get_mcp_connector
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
    rag_status = get_rag_connector().health()
    llm_status = get_llm_connector().health()
    embeddings_status = get_embeddings_connector().health()
    telemetry_status = get_telemetry_connector().health()
    telemetry_sink = settings.ai_soc_telemetry_sink.strip().lower()
    db_telemetry_enabled = settings.telemetry_mode.strip().lower() == "db" and telemetry_sink in {"db", "both"}
    splunk_write_enabled = False
    splunk_sink_status = "not_implemented" if telemetry_sink in {"splunk", "both"} else "disabled"

    telemetry_counters = metrics.snapshot()
    return {
        "mcp": {
            "enabled": settings.mcp_mode == "splunk_mcp" and settings.splunk_mcp_enabled,
            "mode": mcp_status.mode,
            "configured": mcp_status.configured,
            "available": mcp_status.available,
            "implemented": mcp_status.implemented,
            "fallback": mcp_status.fallback,
            "status_detail": mcp_status.detail,
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
            "enabled": settings.llm_mode != "mock" and settings.llm_enabled,
            "mode": llm_status.mode,
            "configured": llm_status.configured,
            "available": llm_status.available,
            "implemented": llm_status.implemented,
            "fallback": llm_status.fallback,
            "status_detail": llm_status.detail,
            "primary_model": "Foundation-Sec Instruct",
            "reasoning_enabled": settings.reasoning_enabled,
            "instruct_endpoint_configured": _bool_configured(settings.foundation_sec_instruct_url),
            "reasoning_endpoint_configured": _bool_configured(settings.foundation_sec_reasoning_url),
            "temperature": 0.2,
            "timeout_seconds": 30,
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
            "deterministic_threshold": settings.routing_deterministic_threshold,
            "llm_planner_enabled": True,
            "shadow_router_enabled": True,
            "compare_node_enabled": True,
            "adjudicator_policy": "prefer_planner_unless_low_confidence",
            "confidence_thresholds": {"high": 0.75, "medium": 0.55, "low": 0.55},
            "fallback_policy": "deterministic_on_planner_failure",
        },
        "safeguards": {
            "spl_validator_enabled": True,
            "blocked_spl_commands": ["delete", "outputlookup", "sendemail", "script"],
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
