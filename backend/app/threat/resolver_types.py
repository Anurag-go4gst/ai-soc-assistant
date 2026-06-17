"""Lightweight technique resolver protocol (import-safe for offline scripts)."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TechniqueResolver(Protocol):
    """Resolve a technique ID (ATT&CK Txxxx or ATLAS AML.Txxxx) to offline metadata."""

    def detail(self, technique_id: str) -> dict[str, Any] | None: ...


class NullTechniqueResolver:
    """No-op resolver — names/descriptions unavailable until a backend is onboarded."""

    operational = False

    def detail(self, technique_id: str) -> dict[str, Any] | None:  # noqa: ARG002
        return None
