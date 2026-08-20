"""File-backed override for the live LLM connection settings.

Lets an operator set the LLM endpoint from the Settings UI instead of editing
``.env`` + redeploying. The persisted values are applied onto the live
``settings`` singleton at startup and on every save, so every read site
(``settings.ai_soc_llm_*``) — the endpoint resolver, sidecars, runtime-health,
and the Ask LLM lab — honors them with no restart.

Only the connection-relevant keys are overridable here (enabled / mode / local
endpoint / model / api key / timeout, plus the Foundation-Sec reasoning hop).
Everything else stays env-governed. The api key is persisted to
``backend/data/llm_connection.json`` (git-ignored) and is never echoed back by the
API — only an ``api_key_configured`` boolean.

A saved override **shadows** ``.env`` on every startup, so editing the env profile
after a save changes nothing until the override is re-saved. An empty
``reasoning_base_url`` means the reasoning hop is **off** (the resolver's
``_configured()`` check drops it) — it does not revert that hop to the env value.
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
    # Reasoning hop — prepended to the failover chain for REASONING_ROLES only
    # (endpoint_resolver.py). Blank switches the hop off rather than falling back
    # to env, so a VPS<->COE switch cannot leave a dead endpoint in the chain.
    "reasoning_base_url": "ai_soc_llm_foundation_sec_reasoning_base_url",
    "reasoning_model": "ai_soc_llm_foundation_sec_reasoning_model",
}


# Operator-selectable endpoint presets for the Settings UI. These are deployment
# addresses already committed in env/profiles/*.env.example — not secrets, and not
# flags: choosing one only pre-fills the form, the operator still saves explicitly.
# Keep in sync with env/profiles/coe.env.example and development.env.example.
CONNECTION_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "vps_dev",
        "label": "VPS dev — llama-server on host (:8081)",
        "description": "Foundation-Sec 8B instruct GGUF on the VPS host. No reasoning hop.",
        "mode": "local",
        "base_url": "http://host.docker.internal:8081/v1",
        "model": "foundation-sec-1.1-8b-instruct-q8_0.gguf",
        "reasoning_base_url": "",
        "reasoning_model": "",
        "timeout_seconds": 120,
    },
    {
        "id": "coe_lan",
        "label": "COE Velocis LAN — instruct :8004 + reasoning :8003",
        "description": "Office-network vLLM. Reasoning roles use 10.52.1.13:8003; everything else 10.52.1.13:8004.",
        "mode": "local",
        "base_url": "http://10.52.1.13:8004/v1",
        "model": "foundation-sec-instruct",
        "reasoning_base_url": "http://10.52.1.13:8003/v1",
        "reasoning_model": "foundation-sec-reasoning",
        "timeout_seconds": 120,
    },
)


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
    reasoning_base_url: str = "",
    reasoning_model: str = "",
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
        "reasoning_base_url": str(reasoning_base_url or "").strip(),
        "reasoning_model": str(reasoning_model or "").strip(),
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
        "reasoning_base_url": settings.ai_soc_llm_foundation_sec_reasoning_base_url,
        "reasoning_model": settings.ai_soc_llm_foundation_sec_reasoning_model,
        "source": "override" if _read_document() else "env",
    }
