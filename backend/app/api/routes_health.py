from fastapi import APIRouter

from app.connectors.telemetry import metrics

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Service liveness plus in-process telemetry counters.

    The counters are integer-only and never contain payload content;
    safe to expose unauthenticated alongside service status.
    """
    counters = metrics.snapshot()
    return {
        "status": "ok",
        "service": "ai-soc-assistant-backend",
        "telemetry": {
            "write_failures": counters.get("telemetry_write_failures", 0),
        },
    }
