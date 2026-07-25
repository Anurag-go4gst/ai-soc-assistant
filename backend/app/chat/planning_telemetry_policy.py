"""Planning telemetry persistence policy — audit-critical vs diagnostic (item 21b)."""

from __future__ import annotations

from app.config import Settings

# Locked decision 12 / item 21b — see docs/architecture/canonical_telemetry_coverage.md
AUDIT_CRITICAL_PLANNING_EVENTS: frozenset[str] = frozenset(
    {
        "handoff.persisted",
        "handoff.resumed",
        "resource_plan.created",
        "execution.started",
        "execution_step.started",
        "execution_step.completed",
        "execution_step.failed",
        "request.failed",
    }
)

DIAGNOSTIC_PLANNING_EVENTS: frozenset[str] = frozenset(
    {
        "query_understanding.completed",
        "lane_router.decided",
        "known_completeness.evaluated",
        "guided_resolution.started",
        "guided_intent.resolved",
        "tier.resolved",
        "detail_tool.selected",
        "detail_tool.started",
        "detail_tool.completed",
        "detail_tool.failed",
        "detail_merge.completed",
        "post_guided_completeness.evaluated",
        "clarification.requested",
        "planner_handoff.created",
        "planner_handoff.consumed",
        "resource_plan.commit_reused",
        "execution.completed",
        "response.validated",
        "response.generated",
        "request.completed",
    }
)


class DiagnosticTelemetryPersistenceDegraded(Exception):
    """Diagnostic planning telemetry failed to persist — chat may continue."""

    def __init__(self, *, event: str | None, reason: str, detail: str) -> None:
        self.event = event
        self.reason = reason
        self.detail = detail
        super().__init__(detail)


class AuditCriticalTelemetryPersistenceError(Exception):
    """Audit-critical planning telemetry could not be durably persisted."""

    def __init__(
        self,
        reason: str,
        *,
        event: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.reason = reason
        self.event = event
        self.detail = detail or reason
        super().__init__(self.reason)


def is_audit_critical_planning_event(event: str | None) -> bool:
    return bool(event) and event in AUDIT_CRITICAL_PLANNING_EVENTS


def is_diagnostic_planning_event(event: str | None) -> bool:
    return bool(event) and event in DIAGNOSTIC_PLANNING_EVENTS


def diagnostic_planning_telemetry_to_db_enabled(settings: Settings | None = None) -> bool:
    """Whether diagnostic planning events may be written to ``canonical_planning_events``."""
    from app.config import settings as live_settings

    cfg = settings or live_settings
    mode = cfg.telemetry_mode.strip().lower()
    sink = cfg.ai_soc_telemetry_sink.strip().lower()
    if mode == "none":
        return False
    return sink == "db"


def should_persist_planning_event_to_db(
    event: str | None,
    *,
    settings: Settings | None = None,
) -> bool:
    if is_audit_critical_planning_event(event):
        return True
    return diagnostic_planning_telemetry_to_db_enabled(settings)


def validate_canonical_planning_telemetry_config(settings: Settings) -> None:
    """Reject startup configs that would discard audit-critical planning telemetry."""
    from app.config import ConfigError

    mode = settings.telemetry_mode.strip().lower()
    sink = settings.ai_soc_telemetry_sink.strip().lower()
    if settings.mcp_global_execution_enabled and mode == "none" and sink == "none":
        raise ConfigError(
            "MCP_GLOBAL_EXECUTION_ENABLED=true cannot be combined with "
            "TELEMETRY_MODE=none and AI_SOC_TELEMETRY_SINK=none: audit-critical "
            "canonical planning telemetry would be discarded with no persistence path."
        )
