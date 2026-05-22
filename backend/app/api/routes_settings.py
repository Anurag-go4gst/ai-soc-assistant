"""Read-only settings status surface.

Returns non-secret configuration state derived from the central ``Settings``
module. Never returns tokens, passwords, or session secrets — only booleans
indicating whether they are configured.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


_ALLOWED_TOOLS = [
    "splunk_run_query",
    "splunk_get_indexes",
    "splunk_get_metadata",
]


def _bool_configured(value: str) -> bool:
    return bool(value and value.strip())


@router.get("/settings/status")
def settings_status() -> dict:
    mcp_mode = "live" if settings.splunk_mcp_enabled else "mock"
    llm_mode = "live" if settings.llm_enabled else "mock"

    return {
        "mcp": {
            "enabled": settings.splunk_mcp_enabled,
            "mode": mcp_mode,
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
            "enabled": False,
            "mode": "mock",
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
            "enabled": settings.llm_enabled,
            "mode": llm_mode,
            "primary_model": "Foundation-Sec Instruct",
            "reasoning_enabled": settings.reasoning_enabled,
            "instruct_endpoint_configured": _bool_configured(settings.foundation_sec_instruct_url),
            "reasoning_endpoint_configured": _bool_configured(settings.foundation_sec_reasoning_url),
            "temperature": 0.2,
            "timeout_seconds": 30,
            "max_context_tokens": 8000,
        },
        "routing": {
            "mode": settings.routing_mode,
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
            "telemetry_enabled": True,
            "trace_logging_enabled": settings.debug_trace_enabled,
            "audit_sink_status": "mock",
            "audit_index": "ai_soc_audit",
            "recent_trace": None,
            "planner_deterministic_mismatch_count": 0,
            "fallback_count": 0,
        },
    }
