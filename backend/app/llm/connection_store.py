"""File-backed override for the live LLM connection settings.

Lets an operator set the LLM endpoint from the Settings UI instead of editing
``.env`` + redeploying. The persisted values are applied onto the live
``settings`` singleton at startup and on every save, so every read site
(``settings.ai_soc_llm_*``) — the endpoint resolver, sidecars, runtime-health,
and the Ask LLM lab — honors them with no restart.

Only the connection-relevant keys are overridable here (enabled / mode / local
endpoint / model / api key / timeout). Everything else stays env-governed. The
api key is persisted to ``backend/data/llm_connection.json`` (git-ignored) and is
never echoed back by the API — only an ``api_key_configured`` boolean.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_connection.json"

# Persisted key -> ``settings`` attribute it overrides.
_FIELD_TO_SETTING = {
    "enabled": "ai_soc_llm_enabled",
    "mode": "ai_soc_llm_mode",
    "base_url": "ai_soc_llm_local_base_url",
    "model": "ai_soc_llm_local_model",
    "api_key": "ai_soc_llm_local_api_key",
    "timeout_seconds": "ai_soc_llm_timeout_seconds",
}


def _store_path() -> Path:
    configured = (settings.ai_soc_llm_connection_store_path or "").strip()
    return Path(configured) if configured else _DEFAULT_PATH


def _read_document() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_connection_override() -> dict[str, Any]:
    """Return the persisted override document (may be empty)."""
    return _read_document()


def apply_to_settings() -> dict[str, Any]:
    """Apply the persisted override onto the live ``settings`` singleton.

    Safe to call at startup and after every save. Returns the applied subset.
    """
    document = _read_document()
    applied: dict[str, Any] = {}
    for field, attr in _FIELD_TO_SETTING.items():
        if field not in document:
            continue
        value = document[field]
        if value is None:
            continue
        try:
            setattr(settings, attr, value)
            applied[field] = value
        except (ValueError, TypeError):
            continue
    # Keep the Ask LLM model selector label in sync with the active model.
    model = document.get("model")
    if model:
        settings.ai_soc_llm_active_model = str(model)
        if str(model) not in (settings.ai_soc_llm_available_models or ""):
            settings.ai_soc_llm_available_models = str(model)
        settings.ai_soc_llm_default_model = str(model)
    # Point the default provider at the chosen mode so the connection Test and
    # role resolution exercise the same endpoint the operator just saved.
    mode = document.get("mode")
    if mode == "local":
        settings.ai_soc_llm_default_provider = "local"
    elif mode == "openai_compatible":
        settings.ai_soc_llm_default_provider = "openai_compatible"
    return applied


def save_connection(
    *,
    enabled: bool,
    mode: str,
    base_url: str,
    model: str,
    api_key: str | None,
    timeout_seconds: int,
    updated_by: str,
) -> dict[str, Any]:
    """Persist the connection override, then apply it to the live settings.

    A blank ``api_key`` preserves the previously stored key (so the UI need not
    re-enter the secret on every save). Pass an explicit empty sentinel via the
    route layer if a key must be cleared.
    """
    existing = _read_document()
    document: dict[str, Any] = {
        "enabled": bool(enabled),
        "mode": str(mode).strip().lower(),
        "base_url": str(base_url).strip(),
        "model": str(model).strip(),
        "timeout_seconds": int(timeout_seconds),
        "updated_by": str(updated_by or "unknown"),
    }
    if api_key:
        document["api_key"] = api_key
    elif existing.get("api_key"):
        document["api_key"] = existing["api_key"]

    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)

    apply_to_settings()
    return document


def effective_connection() -> dict[str, Any]:
    """Current effective connection config (override merged onto env). Redacted."""
    return {
        "enabled": bool(settings.ai_soc_llm_enabled),
        "mode": settings.ai_soc_llm_mode,
        "base_url": settings.ai_soc_llm_local_base_url,
        "model": settings.ai_soc_llm_local_model,
        "api_key_configured": bool((settings.ai_soc_llm_local_api_key or "").strip()),
        "timeout_seconds": settings.ai_soc_llm_timeout_seconds,
        "source": "override" if _read_document() else "env",
    }
