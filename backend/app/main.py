import hashlib
import logging
import traceback
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import parse_cors_allowed_origins, settings
from app.connectors.telemetry import get_telemetry_connector
from app.connectors.telemetry.log_context import (
    REQUEST_ID_HEADER,
    TRACE_ID_HEADER,
    coerce_request_id,
    current_trace_id,
    install_trace_id_log_factory,
    reset_trace_id,
    set_trace_id,
)

# Stamp every log record with the active chat trace_id (Phase 4 observability).
install_trace_id_log_factory()

from app.api.routes_actions import router as actions_router
from app.api.routes_debug import router as debug_router
from app.api.routes_chat import router as chat_router
from app.api.routes_chat_stream import router as chat_stream_router
from app.api.routes_health import router as health_router
from app.api.routes_investigations import router as investigations_router
from app.api.routes_knowledge import router as knowledge_router
from app.api.routes_llm_lab import router as llm_lab_router
from app.api.routes_quality import router as quality_router
from app.api.routes_scenarios import demo_router, router as scenarios_router
from app.api.routes_settings import router as settings_router
from app.auth.routes_auth import router as auth_router
from app.db.migration_readiness import log_startup_migration_readiness


app = FastAPI(title="AI SOC Assistant")

# Apply any UI-persisted LLM connection override onto the live settings before
# the first request, so the endpoint resolver / sidecars / Ask LLM honor it.
try:
    from app.llm.connection_store import apply_to_settings as _apply_llm_connection_override

    _apply_llm_connection_override()
except Exception:  # noqa: BLE001 - never block startup on an optional override
    logging.getLogger("ai_soc.llm").warning("llm_connection_override_apply_failed", exc_info=True)

try:
    from app.connectors.mcp.connection_store import apply_to_settings as _apply_mcp_connection_override

    _apply_mcp_connection_override()
except Exception:  # noqa: BLE001 - never block startup on an optional override
    logging.getLogger("ai_soc.mcp").warning("mcp_connection_override_apply_failed", exc_info=True)

log_startup_migration_readiness()

_telemetry_logger = logging.getLogger("ai_soc.telemetry")

# Stable, public-safe error code returned to clients for any unhandled exception.
# It carries no information about the internal failure beyond "the server failed",
# so it is safe to log/correlate without leaking implementation detail.
UNHANDLED_ERROR_CODE = "internal_error"


@app.middleware("http")
async def _request_trace_context(request: Request, call_next):
    """Adopt the client-known request id as the turn trace id and echo it back.

    Honors a valid ``X-Request-ID`` (else mints one), exposes it on
    ``request.state`` and the contextvar for async-context logging / the exception
    handler, and stamps ``X-Trace-ID`` on every response. The sync route re-derives
    the same id from the same header into its own worker-thread context (the
    BaseHTTPMiddleware contextvar does not propagate into the threadpool), so the
    pipeline, the response header, and the error envelope all carry one id.
    """
    trace_id = coerce_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.trace_id = trace_id
    token = set_trace_id(trace_id)
    try:
        response = await call_next(request)
    finally:
        reset_trace_id(token)
    response.headers[TRACE_ID_HEADER] = trace_id
    return response


def _stack_fingerprint(exc: BaseException) -> str:
    """Short, redacted fingerprint of where an exception originated.

    Uses only the last traceback frame's ``file:lineno`` plus the exception type
    — never the exception message or any argument values — and hashes it so the
    log line is correlatable without exposing source paths to clients. The value
    is logged server-side only; it is not returned in the response envelope.
    """
    try:
        frames = traceback.extract_tb(exc.__traceback__)
        last = frames[-1] if frames else None
        location = f"{last.filename}:{last.lineno}" if last is not None else "unknown"
        raw = f"{type(exc).__name__}@{location}"
        digest = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:12]
        return f"{type(exc).__name__}:{digest}"
    except Exception:  # noqa: BLE001 - fingerprinting must never raise
        return "fingerprint_unavailable"


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fail-closed backstop: any unhandled exception returns a sanitized envelope.

    Never leaks stack traces, exception message text, secrets, or the request body
    to the client. Logs the exception class, a redacted stack fingerprint, and the
    trace_id server-side for diagnosis. Logging itself never raises.
    """
    trace_id = str(getattr(exc, "_ai_soc_trace_id", "") or current_trace_id() or "")
    if not trace_id or trace_id == "-":
        trace_id = str(getattr(request.state, "trace_id", "") or uuid4())
    fingerprint = _stack_fingerprint(exc)
    try:
        _telemetry_logger.error(
            "unhandled_exception trace_id=%s path=%s exc_type=%s fingerprint=%s",
            trace_id,
            getattr(request.url, "path", "unknown"),
            type(exc).__name__,
            fingerprint,
        )
    except Exception:  # noqa: BLE001 - error logging must never raise
        pass
    try:
        telemetry = get_telemetry_connector()
        telemetry.start_trace(
            trace_id,
            entrypoint="chat" if request.url.path == "/chat" else "http",
            status="error",
            metadata={"error_code": UNHANDLED_ERROR_CODE},
        )
        telemetry.record_step(
            trace_id,
            "unhandled_exception",
            "failed",
            exception_type=type(exc).__name__,
            stack_fingerprint=fingerprint,
            path=request.url.path,
        )
        telemetry.end_trace(
            trace_id,
            status="error",
            metadata={"error": True, "error_code": UNHANDLED_ERROR_CODE},
        )
    except Exception:  # noqa: BLE001 - diagnostics must not replace the response
        _telemetry_logger.warning(
            "unhandled_exception_telemetry_failed trace_id=%s", trace_id, exc_info=True
        )
    # Set X-Trace-ID here too: this handler runs outside the trace middleware
    # (which never set the header because call_next raised), so it is the only place
    # that can echo the correlation id on an error response.
    return JSONResponse(
        status_code=500,
        content={
            "trace_id": trace_id,
            "error_code": UNHANDLED_ERROR_CODE,
            "message": "An internal error occurred.",
        },
        headers={TRACE_ID_HEADER: trace_id},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_allowed_origins(settings.ai_soc_cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router)
app.include_router(auth_router, prefix="/api")
app.include_router(chat_router)
app.include_router(chat_router, prefix="/api")
app.include_router(chat_stream_router)
app.include_router(chat_stream_router, prefix="/api")
app.include_router(investigations_router)
app.include_router(investigations_router, prefix="/api")
app.include_router(knowledge_router)
app.include_router(knowledge_router, prefix="/api")
app.include_router(scenarios_router)
app.include_router(scenarios_router, prefix="/api")
app.include_router(demo_router)
app.include_router(demo_router, prefix="/api")
app.include_router(settings_router)
app.include_router(settings_router, prefix="/api")
app.include_router(quality_router)
app.include_router(quality_router, prefix="/api")
app.include_router(debug_router)
app.include_router(debug_router, prefix="/api")
app.include_router(llm_lab_router)
app.include_router(llm_lab_router, prefix="/api")
app.include_router(actions_router)
app.include_router(actions_router, prefix="/api")
