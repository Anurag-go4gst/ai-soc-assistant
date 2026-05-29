"""Load Stage 3L-S6 question ↔ runtime operation mapping (read-only registry)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MAP_PATH = Path(__file__).resolve().parent / "question_runtime_map_v1.json"
_MAP_CACHE: dict[str, Any] | None = None


def load_question_runtime_map(*, reload: bool = False) -> dict[str, Any]:
    global _MAP_CACHE
    if not reload and _MAP_CACHE is not None:
        return _MAP_CACHE
    payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    _MAP_CACHE = payload
    return payload


def clear_question_runtime_map_cache() -> None:
    global _MAP_CACHE
    _MAP_CACHE = None


def list_question_runtime_entries(*, reload: bool = False) -> list[dict[str, Any]]:
    return list(load_question_runtime_map(reload=reload).get("entries", []))


def question_runtime_entry(question_ref: str, *, reload: bool = False) -> dict[str, Any] | None:
    ref = question_ref.strip().lower()
    if not ref.startswith("q0."):
        digits = "".join(ch for ch in ref if ch.isdigit())
        if digits:
            ref = f"q0.q{int(digits):03d}"
    for entry in list_question_runtime_entries(reload=reload):
        if entry.get("question_ref") == ref:
            return entry
    return None


def manifest_coverage_ids_from_map(*, reload: bool = False) -> frozenset[str]:
    ids: set[str] = set()
    for entry in list_question_runtime_entries(reload=reload):
        coverage_id = entry.get("manifest_coverage_id")
        if isinstance(coverage_id, str) and coverage_id:
            ids.add(coverage_id)
    return frozenset(ids)
