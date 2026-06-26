"""COE debug API — read-only trace list, timeline, bundle, and readiness."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.session import require_auth
from app.auth.user_registry import user_has_debug_access
from app.config import settings
from app.connectors.telemetry.read_store import fetch_trace_bundle, fetch_trace_timeline, list_trace_runs
from app.debug.readiness import build_debug_readiness

router = APIRouter()
_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TIMELINE_EVENT_LIMIT = 500
_BUNDLE_EVENT_LIMIT = 200


def _require_debug_api_access(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if not settings.ai_soc_debug_api_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="debug_api_disabled")
    username = str(user.get("username") or "")
    if user_has_debug_access(username):
        return user
    allowlist = {
        item.strip() for item in settings.ai_soc_debug_api_user_allowlist.split(",") if item.strip()
    }
    if username in allowlist:
        return user
    if settings.ai_soc_debug_api_allow_any_authenticated:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="debug_api_forbidden")


@router.get("/debug/traces")
def debug_list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    entrypoint: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    since: str | None = Query(default=None),
    _user: dict[str, Any] = Depends(_require_debug_api_access),
) -> dict[str, Any]:
    since_dt = _parse_since(since)
    runs = list_trace_runs(limit=limit, entrypoint=entrypoint, status=status_filter, since=since_dt)
    return {"traces": runs, "count": len(runs)}


@router.get("/debug/traces/{trace_id}")
def debug_trace_timeline(
    trace_id: str,
    _user: dict[str, Any] = Depends(_require_debug_api_access),
) -> dict[str, Any]:
    _validate_trace_id(trace_id)
    timeline = fetch_trace_timeline(trace_id, max_events=_TIMELINE_EVENT_LIMIT)
    if timeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace_not_found")
    return timeline


@router.get("/debug/traces/{trace_id}/bundle")
def debug_trace_bundle(
    trace_id: str,
    _user: dict[str, Any] = Depends(_require_debug_api_access),
) -> dict[str, Any]:
    _validate_trace_id(trace_id)
    bundle = fetch_trace_bundle(trace_id, max_events=_BUNDLE_EVENT_LIMIT)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace_not_found")
    return bundle


@router.get("/debug/readiness")
def debug_readiness(_user: dict[str, Any] = Depends(_require_debug_api_access)) -> dict[str, Any]:
    return build_debug_readiness()


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_since_timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validate_trace_id(trace_id: str) -> None:
    if not _TRACE_ID_RE.fullmatch(trace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_trace_id")
