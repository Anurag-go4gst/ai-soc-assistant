from fastapi import APIRouter

from app.connectors.telemetry import metrics
from app.db.migration_readiness import build_migration_readiness

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Service liveness plus in-process telemetry counters.

    The counters are integer-only and never contain payload content;
    safe to expose unauthenticated alongside service status.
    """
    counters = metrics.snapshot()
    migration_readiness = build_migration_readiness()
    status = "ok" if migration_readiness.get("ready", True) else "degraded"
    return {
        "status": status,
        "service": "ai-soc-assistant-backend",
        "readiness": {
            "database_migrations": migration_readiness,
        },
        # Integer-only counters (no payload content); flat so each value stays an int.
        "telemetry": {
            "write_failures": counters.get("telemetry_write_failures", 0),
            **counters,
        },
    }
