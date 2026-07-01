"""Guided hybrid safe SPL catalog allowlist (REV4 batch 2 P10)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.spl.template_registry import get_spl_template

CATALOG_PATH = Path(__file__).with_name("guided_safe_spl_catalog.json")


class GuidedSafeSplCatalogEntry(BaseModel):
    template_id: str
    max_lookback_hours: int = 24
    max_rows: int = 100
    allowed_commands: list[str] = Field(default_factory=list)
    required_source_profile_slots: list[str] = Field(default_factory=list)
    enabled: bool = True


class GuidedSafeSplCatalog(BaseModel):
    version: str = "1"
    coe_signed: bool = False
    description: str | None = None
    entries: list[GuidedSafeSplCatalogEntry] = Field(default_factory=list)


@lru_cache(maxsize=1)
def load_guided_safe_spl_catalog() -> GuidedSafeSplCatalog:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return GuidedSafeSplCatalog.model_validate(raw)


@lru_cache(maxsize=1)
def guided_safe_template_ids() -> frozenset[str]:
    """Template IDs approved for guided safe-catalog execution."""
    catalog = load_guided_safe_spl_catalog()
    ids: set[str] = set()
    for entry in catalog.entries:
        if not entry.enabled:
            continue
        template = get_spl_template(entry.template_id)
        if template is None or template.enabled is not True:
            continue
        ids.add(entry.template_id)
    return frozenset(ids)


def get_guided_safe_catalog_entry(template_id: str) -> GuidedSafeSplCatalogEntry | None:
    catalog = load_guided_safe_spl_catalog()
    for entry in catalog.entries:
        if entry.template_id == template_id and entry.enabled:
            return entry
    return None


def catalog_summary_for_trace() -> dict[str, Any]:
    catalog = load_guided_safe_spl_catalog()
    return {
        "version": catalog.version,
        "coe_signed": catalog.coe_signed,
        "template_ids": sorted(guided_safe_template_ids()),
    }
