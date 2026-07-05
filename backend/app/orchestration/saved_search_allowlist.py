"""Saved-search name allowlist — env list union catalogue-bound names (DG-5)."""
from __future__ import annotations

from app.config import settings
from app.coverage.catalogue_execution_map import load_catalogue_execution_map


def _env_allowlist_names() -> set[str]:
    raw = str(settings.splunk_allowed_saved_searches or "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _catalogue_bound_names() -> set[str]:
    catalog = load_catalogue_execution_map()
    names: set[str] = set()
    for entry in catalog.entries:
        if entry.saved_search_name:
            names.add(str(entry.saved_search_name).strip())
    return names


def saved_search_allow_set() -> set[str]:
    return _env_allowlist_names() | _catalogue_bound_names()


def saved_search_name_allowed(name: str) -> bool:
    normalized = str(name or "").strip()
    if not normalized:
        return False
    return normalized in saved_search_allow_set()
