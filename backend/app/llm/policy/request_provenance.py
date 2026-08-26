"""Eval-only capture of the system prompt actually placed on the provider request.

Production callers ignore this. The P8 A/B harness reads records after each live
hop. Live T4/planner hops run inside a ThreadPoolExecutor, so this store is
thread-safe module state rather than a ContextVar. Hashes only — never prompt
text, never secrets.
"""

from __future__ import annotations

import threading
from hashlib import sha256
from typing import Any

_LOCK = threading.Lock()
_SELECTED_PROMPTS: list[dict[str, Any]] = []
_PROVIDER_REQUESTS: list[dict[str, Any]] = []


def hash_prompt_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def record_selected_system_prompt(
    *,
    role_id: str,
    template_id: str,
    version: str,
    status: str,
    system_instruction: str,
    prefix_hash: str | None = None,
) -> None:
    record = {
        "role_id": role_id,
        "template_id": template_id,
        "version": version,
        "status": status,
        "instruction_sha256": hash_prompt_text(system_instruction),
        "prefix_hash": prefix_hash,
    }
    with _LOCK:
        _SELECTED_PROMPTS.append(record)


def record_provider_system_prompt(system_prompt: str) -> None:
    selected = last_selected_prompt() or {}
    record = {
        "role_id": selected.get("role_id"),
        "system_prompt_sha256": hash_prompt_text(system_prompt),
        "system_prompt_chars": len(system_prompt),
        "selected_instruction_sha256": selected.get("instruction_sha256"),
        "matches_selected_instruction": bool(
            selected.get("instruction_sha256")
            and hash_prompt_text(system_prompt) == selected.get("instruction_sha256")
        ),
    }
    with _LOCK:
        _PROVIDER_REQUESTS.append(record)


def last_selected_prompt() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_SELECTED_PROMPTS[-1]) if _SELECTED_PROMPTS else None


def last_provider_request() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_PROVIDER_REQUESTS[-1]) if _PROVIDER_REQUESTS else None


def selected_prompt_for_role(role_id: str) -> dict[str, Any] | None:
    with _LOCK:
        for record in reversed(_SELECTED_PROMPTS):
            if record.get("role_id") == role_id:
                return dict(record)
        return dict(_SELECTED_PROMPTS[-1]) if _SELECTED_PROMPTS else None


def provider_request_for_role(role_id: str) -> dict[str, Any] | None:
    with _LOCK:
        for record in reversed(_PROVIDER_REQUESTS):
            if record.get("role_id") == role_id:
                return dict(record)
        return dict(_PROVIDER_REQUESTS[-1]) if _PROVIDER_REQUESTS else None


def reset_prompt_provenance() -> None:
    with _LOCK:
        _SELECTED_PROMPTS.clear()
        _PROVIDER_REQUESTS.clear()
