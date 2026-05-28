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
