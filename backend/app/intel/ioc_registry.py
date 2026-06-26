"""Stage 3K-Q2 IOC registry loader and normalized index."""

from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from app.intel.ioc_models import IocRecord, IocRegistryDocument, IocSourceRecord, IocType

_REGISTRY_CACHE: dict[str, "_LoadedIocRegistry"] = {}


class _LoadedIocRegistry:
    def __init__(self, document: IocRegistryDocument) -> None:
        self.document = document
        self.sources_by_id = {source.source_id: source for source in document.sources}
        self.index: dict[tuple[str, str], IocRecord] = {}
        for record in document.iocs:
            key = (record.ioc_type.value, _normalize_ioc_value(record.value, record.ioc_type))
            self.index[key] = record


def load_ioc_registry(path: str | Path, *, reload: bool = False) -> _LoadedIocRegistry:
    """Load and cache IOC registry from JSON document."""
    resolved = str(Path(path).resolve())
    if not reload and resolved in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[resolved]

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    document = IocRegistryDocument.model_validate(raw)
    loaded = _LoadedIocRegistry(document)
    _REGISTRY_CACHE[resolved] = loaded
    return loaded


def clear_ioc_registry_cache() -> None:
    _REGISTRY_CACHE.clear()

def resolve_ioc_registry_path(registry_path: str | Path | None = None) -> Path:
    """Resolve configured IOC registry path, falling back to packaged sample."""
    if registry_path:
        return Path(registry_path)
    from app.config import settings

    configured = settings.ioc_registry_path.strip()
    if configured:
        candidate = Path(configured)
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent / "fixtures" / "ioc_registry.sample.json"


def summarize_ioc_registry_for_settings(*, registry_path: str | Path | None = None) -> dict[str, Any]:
    """Build read-only settings summary for the IOC registry UI."""
    from app.config import settings
    from app.intel.ioc_lookup import evaluate_registry_staleness

    path = resolve_ioc_registry_path(registry_path)
    summary: dict[str, Any] = {
        "enabled": bool(settings.ioc_registry_enabled),
        "registry_path": str(path),
        "import_path_hint": settings.ioc_registry_path.strip() or str(path),
        "path_exists": path.exists(),
        "hash_count": 0,
        "hashes": [],
        "advisory_id": None,
        "imported_at": None,
        "staleness_status": None,
        "source_count": 0,
        "ioc_count": 0,
        "validation_errors": [],
    }
    if not path.exists():
        summary["validation_errors"] = ["registry_file_missing"]
        return summary
    try:
        loaded = load_ioc_registry(path, reload=True)
    except (OSError, ValueError, ValidationError) as exc:
        summary["validation_errors"] = [str(exc)]
        return summary

    document = loaded.document
    summary["source_count"] = len(document.sources)
    summary["ioc_count"] = len(document.iocs)
    if document.sources:
        primary = document.sources[0]
        summary["advisory_id"] = primary.source_id
        summary["imported_at"] = primary.last_refreshed.isoformat()
    summary["staleness_status"] = evaluate_registry_staleness(path).value

    hash_types = {IocType.HASH_MD5, IocType.HASH_SHA1, IocType.HASH_SHA256}
    hashes: list[dict[str, str]] = []
    for record in document.iocs:
        if record.ioc_type not in hash_types:
            continue
        hashes.append(
            {
                "value": record.value,
                "hash_type": record.ioc_type.value,
                "confidence": record.confidence,
                "tlp": record.tlp,
            }
        )
    summary["hash_count"] = len(hashes)
    summary["hashes"] = hashes[:500]
    return summary


def save_ioc_registry_document(payload: dict[str, Any], *, registry_path: str | Path | None = None) -> dict[str, Any]:
    """Validate and persist an IOC registry JSON document."""
    errors = validate_ioc_registry_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    path = resolve_ioc_registry_path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    clear_ioc_registry_cache()
    return summarize_ioc_registry_for_settings(registry_path=path)



def validate_ioc_registry_payload(payload: dict[str, Any]) -> list[str]:
    """Return validation error messages for a registry payload."""
    try:
        IocRegistryDocument.model_validate(payload)
        return []
    except ValidationError as exc:
        return [f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg')}" for error in exc.errors()]


def get_source(registry: _LoadedIocRegistry, source_id: str) -> IocSourceRecord | None:
    return registry.sources_by_id.get(source_id)


def get_ioc_record(registry: _LoadedIocRegistry, value: str, ioc_type: IocType | str) -> IocRecord | None:
    typed = IocType(ioc_type) if not isinstance(ioc_type, IocType) else ioc_type
    normalized = _normalize_ioc_value(value, typed)
    return registry.index.get((typed.value, normalized))


def _normalize_ioc_value(value: str, ioc_type: IocType) -> str:
    text = value.strip()
    if ioc_type == IocType.IP:
        return str(ipaddress.ip_address(text))
    if ioc_type in {IocType.HASH_MD5, IocType.HASH_SHA1, IocType.HASH_SHA256}:
        return text.lower()
    if ioc_type == IocType.DOMAIN:
        host = text.lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        return host
    if ioc_type == IocType.URL:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.hostname or text).lower().rstrip(".")
        return host
    return text.lower()


def infer_ioc_type(value: str) -> IocType | None:
    text = value.strip()
    try:
        ipaddress.ip_address(text)
        return IocType.IP
    except ValueError:
        pass
    lowered = text.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return IocType.URL
    if len(lowered) == 32 and all(char in "0123456789abcdef" for char in lowered):
        return IocType.HASH_MD5
    if len(lowered) == 40 and all(char in "0123456789abcdef" for char in lowered):
        return IocType.HASH_SHA1
    if len(lowered) == 64 and all(char in "0123456789abcdef" for char in lowered):
        return IocType.HASH_SHA256
    if "." in lowered and " " not in lowered:
        return IocType.DOMAIN
    return None
