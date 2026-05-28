"""Stage 3K-Q3 detection registry loader and family index."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.detections.detection_models import DetectionRecord, DetectionRegistryDocument, VettingStatus

_REGISTRY_CACHE: dict[str, "_LoadedDetectionRegistry"] = {}


class _LoadedDetectionRegistry:
    def __init__(self, document: DetectionRegistryDocument) -> None:
        self.document = document
        self.by_ref: dict[str, DetectionRecord] = {record.detection_ref: record for record in document.detections}
        self.by_family: dict[str, list[DetectionRecord]] = {}
        for record in document.detections:
            self.by_family.setdefault(record.family, []).append(record)


def load_detection_registry(path: str | Path, *, reload: bool = False) -> _LoadedDetectionRegistry:
    resolved = str(Path(path).resolve())
    if not reload and resolved in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[resolved]

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    document = DetectionRegistryDocument.model_validate(raw)
    loaded = _LoadedDetectionRegistry(document)
    _REGISTRY_CACHE[resolved] = loaded
    return loaded


def clear_detection_registry_cache() -> None:
    _REGISTRY_CACHE.clear()


def validate_detection_registry_payload(payload: dict[str, Any]) -> list[str]:
    try:
        DetectionRegistryDocument.model_validate(payload)
        return []
    except ValidationError as exc:
        return [f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg')}" for error in exc.errors()]


def get_detection(registry: _LoadedDetectionRegistry, detection_ref: str) -> DetectionRecord | None:
    return registry.by_ref.get(detection_ref)


def list_family(registry: _LoadedDetectionRegistry, family: str) -> list[DetectionRecord]:
    return list(registry.by_family.get(family, []))


def is_registered_detection_ref(registry: _LoadedDetectionRegistry, detection_ref: str) -> bool:
    return detection_ref in registry.by_ref


def is_bindable_detection_ref(registry: _LoadedDetectionRegistry, detection_ref: str) -> bool:
    record = registry.by_ref.get(detection_ref)
    return record is not None and record.vetting_status == VettingStatus.APPROVED
