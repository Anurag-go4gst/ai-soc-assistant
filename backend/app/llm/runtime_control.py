"""Operator LLM service control via a host-applied sentinel queue.

The backend runs in Docker and must not be granted host systemd / docker-socket
access just to restart the llama-server. Instead, a control request is written as a
JSON sentinel into a shared volume (``AI_SOC_LLM_CONTROL_DIR``); a host watcher
(``scripts/llm_control_watcher.py``) reads it, runs ``systemctl``, and writes back a
result. The web app therefore holds NO host privileges — it only enqueues a request.

Gated by ``AI_SOC_LLM_CONTROL_ENABLED`` (default off) and the router's ``require_auth``.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import settings

ALLOWED_ACTIONS = ("restart", "stop", "start")
_REQUEST_PREFIX = "request-"
_RESULT_FILE = "last_result.json"


class LlmControlError(Exception):
    """Raised when control is disabled or misconfigured (never leaks host detail)."""


def _control_dir() -> Path:
    raw = (settings.ai_soc_llm_control_dir or "").strip()
    if not settings.ai_soc_llm_control_enabled:
        raise LlmControlError("llm_control_disabled")
    if not raw:
        raise LlmControlError("llm_control_dir_not_configured")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def control_available() -> bool:
    return bool(settings.ai_soc_llm_control_enabled and (settings.ai_soc_llm_control_dir or "").strip())


def request_control(action: str, *, requested_by: str | None = None) -> dict[str, Any]:
    """Enqueue a control request for the host watcher. Returns the accepted record."""
    action = (action or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise LlmControlError("invalid_action")
    directory = _control_dir()
    request_id = uuid.uuid4().hex
    record = {
        "request_id": request_id,
        "action": action,
        "requested_by": requested_by or "unknown",
        "requested_at": time.time(),
        "status": "pending",
    }
    target = directory / f"{_REQUEST_PREFIX}{request_id}.json"
    # Atomic write so the watcher never reads a half-written request.
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record), encoding="utf-8")
    os.replace(tmp, target)
    return record


def last_result() -> dict[str, Any] | None:
    """Return the most recent result the host watcher wrote, if any."""
    if not control_available():
        return None
    path = Path((settings.ai_soc_llm_control_dir or "").strip()) / _RESULT_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
