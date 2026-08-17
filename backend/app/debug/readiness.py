"""Consolidated readiness snapshot for GET /debug/readiness."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.discovery_snapshot import get_discovery_snapshot_store
from app.connectors.mcp.effective_catalog import compute_effective_catalog
from app.connectors.mcp.registry import load_mcp_registry_status
from app.connectors.telemetry import get_telemetry_connector, metrics
from app.connectors.telemetry.db import DbTelemetryConnector
from app.knowledge.soc_kb_retriever import soc_kb_status_summary
from app.llm.registry_settings import build_llm_governance_status


def _mcp_discovery_summary() -> list[dict[str, Any]]:
    """Three independently observable states per server, so an operator
    never has to infer discovery status from execution behavior:
    MCP_CONFIGURED (server.configured), MCP_DISCOVERY_VERIFIED
    (discovery_status == "ok", i.e. a live handshake has actually run this
    process lifetime), MCP_GLOBAL_EXECUTION_ENABLED (registry-wide flag).
    In-memory discovery state is process-lifetime only by design (every
    process re-verifies the live server catalog rather than trusting a
    stale persisted one) -- after a backend restart this always starts
    DISCOVERY_VERIFIED=false again until an operator calls
    POST /debug/mcp/discovery/refresh (see GET /debug/mcp/catalog for full
    per-tool detail)."""
    registry = load_mcp_registry_status()
    store = get_discovery_snapshot_store()
    summary: list[dict[str, Any]] = []
    for server in registry.servers:
        snapshot = store.get(server.name)
        result = compute_effective_catalog(server, mode=registry.mode, snapshot=snapshot)
        summary.append(
            {
                "server_name": server.name,
                "mcp_configured": server.configured,
                "mcp_discovery_verified": result.discovery_status == "ok",
                "mcp_discovery_status": result.discovery_status,
                "mcp_discovery_age_seconds": result.discovery_age_seconds,
                "mcp_global_execution_enabled": registry.global_execution_enabled,
            }
        )
    return summary


def build_debug_readiness() -> dict[str, Any]:
    telemetry = get_telemetry_connector()
    telemetry_health = telemetry.health()
    sink = settings.ai_soc_telemetry_sink.strip().lower()
    return {
        "telemetry": {
            "telemetry_mode": settings.telemetry_mode,
            "telemetry_sink": sink,
            "telemetry_enabled": settings.telemetry_mode.strip().lower() != "none" and sink != "none",
            "connector_mode": telemetry_health.mode,
            "connector_configured": telemetry_health.configured,
            "connector_available": telemetry_health.available,
            "connector_detail": telemetry_health.detail,
            "global_write_disabled": DbTelemetryConnector._global_disabled_after_failure,
            "metrics": metrics.snapshot(),
        },
        "llm": build_llm_governance_status(),
        "mcp": load_mcp_registry_status(),
        "mcp_discovery": _mcp_discovery_summary(),
        "rag": soc_kb_status_summary(),
        "debug_api_enabled": settings.ai_soc_debug_api_enabled,
    }
