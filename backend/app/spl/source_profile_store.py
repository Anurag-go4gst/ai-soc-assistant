"""Persisted COE source-profile map (UI-editable)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

_store_lock = Lock()
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "source_profile_map.json"


def _store_path() -> Path:
    configured = (getattr(settings, "ai_soc_source_profile_store_path", "") or "").strip()
    return Path(configured) if configured else _DEFAULT_PATH


def _empty_document() -> dict[str, Any]:
    return {
        "values": {},
        "field_sources": {},
        "updated_at": None,
        "updated_by": None,
    }


def _read_document() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _empty_document()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_document()
    if not isinstance(parsed, dict):
        return _empty_document()
    values = parsed.get("values")
    if not isinstance(values, dict):
        values = parsed if all(isinstance(k, str) for k in parsed) else {}
    field_sources = parsed.get("field_sources") if isinstance(parsed.get("field_sources"), dict) else {}
    return {
        "values": {str(k): str(v) for k, v in values.items() if v},
        "field_sources": {str(k): str(v) for k, v in field_sources.items()},
        "updated_at": parsed.get("updated_at"),
        "updated_by": parsed.get("updated_by"),
    }


def load_persisted_source_profile() -> dict[str, str]:
    with _store_lock:
        return dict(_read_document().get("values") or {})


def load_persisted_source_profile_document() -> dict[str, Any]:
    with _store_lock:
        return _read_document()


def _write_document(document: dict[str, Any], *, updated_by: str) -> dict[str, Any]:
    document = {
        **document,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": updated_by,
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def save_persisted_source_profile(
    values: dict[str, str],
    *,
    updated_by: str = "coe_ui",
    field_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    cleaned = {str(k): str(v).strip() for k, v in values.items() if str(v).strip()}
    with _store_lock:
        current = _read_document()
        sources = dict(current.get("field_sources") or {})
        if field_sources:
            sources.update({str(k): str(v) for k, v in field_sources.items() if v})
        for slot_id in cleaned:
            if slot_id not in sources:
                sources[slot_id] = "coe_ui"
        document = {
            "values": cleaned,
            "field_sources": sources,
        }
        return _write_document(document, updated_by=updated_by)


def merge_mcp_discovery_into_store(
    discovered: dict[str, str],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Merge MCP discovery values.

    COE/manual source-profile values are authoritative. MCP discovery may fill
    blanks, but it must not overwrite stored values unless a caller explicitly
    opts into that behavior for an admin remediation flow.
    """
    with _store_lock:
        current = _read_document()
        values = dict(current.get("values") or {})
        sources = dict(current.get("field_sources") or {})
        for slot_id, value in discovered.items():
            if not value:
                continue
            if overwrite or slot_id not in values:
                values[slot_id] = value
                sources[slot_id] = "mcp_discovery"
        document = {
            "values": values,
            "field_sources": sources,
        }
        return _write_document(document, updated_by="mcp_discovery")
