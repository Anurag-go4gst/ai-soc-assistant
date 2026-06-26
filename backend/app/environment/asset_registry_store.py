"""Local COE-managed asset registry store.

The registry is advisory environment knowledge. It may fill review-only SPL
placeholders, but it never writes Splunk lookups and never authorizes execution.
"""
from __future__ import annotations

import csv
import ipaddress
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

_store_lock = Lock()
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "asset_registry.json"
_MAX_RECORDS = 5000
_MAX_IMPORT_BYTES = 1_000_000
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _store_path() -> Path:
    configured = (getattr(settings, "ai_soc_asset_registry_store_path", "") or "").strip()
    return Path(configured) if configured else _DEFAULT_PATH


def _empty_document() -> dict[str, Any]:
    return {"assets": [], "updated_at": None, "updated_by": None, "source": "local_json"}


def _clean_cell(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def _validate_ip(value: str) -> str:
    text = _clean_cell(value)
    if not text:
        raise ValueError("ip is required")
    try:
        ipaddress.ip_address(text)
    except ValueError as exc:
        raise ValueError(f"invalid ip: {text}") from exc
    return text


def _normalize_asset(record: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "ip": _validate_ip(str(record.get("ip") or "")),
        "mac": _clean_cell(record.get("mac")),
        "asset_name": _clean_cell(record.get("asset_name")),
        "asset_type": _clean_cell(record.get("asset_type")),
        "purdue_layer": _clean_cell(record.get("purdue_layer")),
        "criticality": _clean_cell(record.get("criticality")),
        "substation_id": _clean_cell(record.get("substation_id")),
        "region": _clean_cell(record.get("region")),
        "is_master_station": bool(record.get("is_master_station")),
        "expected_firmware": _clean_cell(record.get("expected_firmware")),
        "notes": _clean_cell(record.get("notes")),
    }
    if not normalized["asset_name"]:
        normalized["asset_name"] = normalized["ip"]
    return normalized


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
    assets = parsed.get("assets")
    if not isinstance(assets, list):
        assets = []
    cleaned: list[dict[str, Any]] = []
    for item in assets[:_MAX_RECORDS]:
        if isinstance(item, dict):
            try:
                cleaned.append(_normalize_asset(item))
            except ValueError:
                continue
    return {
        "assets": cleaned,
        "updated_at": parsed.get("updated_at"),
        "updated_by": parsed.get("updated_by"),
        "source": parsed.get("source") or "local_json",
    }


def load_asset_registry_document() -> dict[str, Any]:
    with _store_lock:
        return _read_document()


def save_asset_registry(assets: list[dict[str, Any]], *, updated_by: str = "coe_ui", source: str = "coe_ui") -> dict[str, Any]:
    if len(assets) > _MAX_RECORDS:
        raise ValueError(f"asset registry record limit exceeded: {_MAX_RECORDS}")
    normalized = [_normalize_asset(item) for item in assets]
    document = {
        "assets": normalized,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": updated_by,
        "source": source,
    }
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def import_asset_registry_payload(payload: str, *, content_type: str = "application/json", updated_by: str = "coe_ui") -> dict[str, Any]:
    if len(payload.encode("utf-8")) > _MAX_IMPORT_BYTES:
        raise ValueError("asset registry import payload too large")
    if "csv" in content_type.lower():
        reader = csv.DictReader(StringIO(payload))
        assets = [dict(row) for row in reader]
        return save_asset_registry(assets, updated_by=updated_by, source="csv_import")
    parsed = json.loads(payload)
    if isinstance(parsed, dict):
        assets = parsed.get("assets")
    else:
        assets = parsed
    if not isinstance(assets, list):
        raise ValueError("asset registry JSON must be a list or object with assets[]")
    return save_asset_registry([item for item in assets if isinstance(item, dict)], updated_by=updated_by, source="json_import")


def build_asset_registry_profile(required_slots: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Derive safe placeholder lists from the local registry.

    Values are comma-separated quoted IPs intended for `IN (...)` placeholder
    substitution in lab drafts. They are advisory and review-only.
    """
    requested = set(required_slots)
    if not requested:
        return {}
    assets = load_asset_registry_document().get("assets") or []
    profile: dict[str, str] = {}
    if "phase1_rtu_ips" in requested or "rtu_ips" in requested:
        ips = [
            str(asset["ip"])
            for asset in assets
            if str(asset.get("asset_type", "")).strip().lower() == "rtu"
            or "rtu" in str(asset.get("asset_name", "")).lower()
        ]
        if ips:
            value = ",".join(f'"{ip}"' for ip in sorted(set(ips)))
            profile["phase1_rtu_ips"] = value
            profile["rtu_ips"] = value
    if "master_station_ips" in requested:
        ips = [str(asset["ip"]) for asset in assets if bool(asset.get("is_master_station"))]
        if ips:
            profile["master_station_ips"] = ",".join(f'"{ip}"' for ip in sorted(set(ips)))
    if "ot_asset_ips" in requested:
        ips = [str(asset["ip"]) for asset in assets if str(asset.get("criticality", "")).lower() in {"cii", "critical"}]
        if ips:
            profile["ot_asset_ips"] = ",".join(f'"{ip}"' for ip in sorted(set(ips)))
    return profile

