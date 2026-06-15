"""Lightweight LLM endpoint health ping for settings/status (green / red).

Hits ``/v1/models`` (cheap reachability, no generation) on the active failover
endpoints. Results are TTL-cached so a settings page can poll on a schedule
without hammering the model server. Qwen is probed only when its flag is on;
otherwise it reports ``wired_disabled`` ("wired, disabled").

Stdlib-only (urllib) to avoid importing the heavy settings/route chain.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.llm.clients.endpoint_resolver import (
    ResolvedEndpoint,
    resolve_foundation_sec_instruct_endpoint,
    resolve_foundation_sec_reasoning_endpoint,
    resolve_local_primary_endpoint,
    resolve_qwen_primary_endpoint,
)

STATUS_GREEN = "green"
STATUS_RED = "red"
STATUS_WIRED_DISABLED = "wired_disabled"

_PROBE_TIMEOUT_SECONDS = 5
_CACHE_TTL_SECONDS = 30.0

_LATENCY_HINT = (
    "On-prem single-slot model: the first answer of a turn can take ~60s while the "
    "model generates. Long waits are expected, not errors — the answer falls back to "
    "a deterministic summary if the model is unreachable."
)

_cache: dict[str, Any] = {"checked_at": 0.0, "payload": None}


@dataclass(frozen=True)
class EndpointHealth:
    role: str
    label: str
    status: str
    model_configured: bool = False
    latency_ms: int | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "label": self.label,
            "status": self.status,
            "model_configured": self.model_configured,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
        }


def _probe(endpoint: ResolvedEndpoint) -> EndpointHealth:
    url = endpoint.base_url.rstrip("/") + "/models"
    headers = {"Accept": "application/json"}
    if endpoint.api_key.strip():
        headers["Authorization"] = "Bearer " + endpoint.api_key.strip()
    request = urllib.request.Request(url, method="GET", headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=_PROBE_TIMEOUT_SECONDS) as response:  # noqa: S310
            response.read(4096)
    except urllib.error.HTTPError as exc:
        # Reached the server, but /models errored — still counts as reachable.
        return EndpointHealth(
            role="", label=endpoint.label, status=STATUS_GREEN, model_configured=True,
            latency_ms=int((time.monotonic() - started) * 1000), detail=f"http_{exc.code}",
        )
    except Exception as exc:  # noqa: BLE001 — never raise from a health probe
        return EndpointHealth(
            role="", label=endpoint.label, status=STATUS_RED, model_configured=True,
            detail=type(exc).__name__,
        )
    return EndpointHealth(
        role="", label=endpoint.label, status=STATUS_GREEN, model_configured=True,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def _qwen_health() -> EndpointHealth:
    if not settings.ai_soc_llm_qwen_primary_enabled:
        return EndpointHealth(
            role="qwen_primary", label="qwen_primary", status=STATUS_WIRED_DISABLED,
            detail="Qwen wired but disabled (AI_SOC_LLM_QWEN_PRIMARY_ENABLED=false).",
        )
    endpoint = resolve_qwen_primary_endpoint()
    if endpoint is None:
        return EndpointHealth(
            role="qwen_primary", label="qwen_primary", status=STATUS_RED,
            detail="Qwen enabled but QWEN_BASE_URL/MODEL not configured.",
        )
    probed = _probe(endpoint)
    return EndpointHealth(
        role="qwen_primary", label=probed.label, status=probed.status,
        model_configured=True, latency_ms=probed.latency_ms, detail=probed.detail,
    )


def _resolved_health(role: str, endpoint: ResolvedEndpoint | None) -> EndpointHealth | None:
    if endpoint is None:
        return None
    probed = _probe(endpoint)
    return EndpointHealth(
        role=role, label=probed.label, status=probed.status,
        model_configured=True, latency_ms=probed.latency_ms, detail=probed.detail,
    )


def llm_endpoint_health(*, force: bool = False) -> dict[str, Any]:
    """Return cached health for the active LLM endpoints (TTL 30s)."""
    now = time.monotonic()
    if not force and _cache["payload"] is not None and (now - _cache["checked_at"]) < _CACHE_TTL_SECONDS:
        return _cache["payload"]

    endpoints: list[EndpointHealth] = [_qwen_health()]
    for role, resolver in (
        ("local_primary", resolve_local_primary_endpoint),
        ("foundation_sec_instruct_fallback", resolve_foundation_sec_instruct_endpoint),
        ("foundation_sec_reasoning", resolve_foundation_sec_reasoning_endpoint),
    ):
        health = _resolved_health(role, resolver())
        if health is not None:
            endpoints.append(health)

    active = [e for e in endpoints if e.status != STATUS_WIRED_DISABLED]
    any_green = any(e.status == STATUS_GREEN for e in active)
    payload = {
        "overall": STATUS_GREEN if any_green else STATUS_RED,
        "expected_latency_hint": _LATENCY_HINT,
        "ttl_seconds": int(_CACHE_TTL_SECONDS),
        "endpoints": [e.to_dict() for e in endpoints],
    }
    _cache["checked_at"] = now
    _cache["payload"] = payload
    return payload
