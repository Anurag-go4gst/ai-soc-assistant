"""Load Stage 3L-S6 question ↔ runtime operation mapping (read-only registry)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_MAP_PATH = Path(__file__).resolve().parent / "question_runtime_map_v1.json"
_CISCO_MAP_PATH = Path(__file__).resolve().parent / "cisco_question_runtime_map_v1.json"
_MAP_CACHE: dict[str, Any] | None = None
_CISCO_MAP_CACHE: dict[str, Any] | None = None
_NEAR_MATCH_THRESHOLD = 0.62
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "by",
    "for",
    "from",
    "had",
    "have",
    "in",
    "is",
    "of",
    "or",
    "show",
    "the",
    "to",
    "what",
    "which",
    "who",
}


def load_question_runtime_map(*, reload: bool = False) -> dict[str, Any]:
    global _MAP_CACHE
    if not reload and _MAP_CACHE is not None:
        return _MAP_CACHE
    payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    _MAP_CACHE = payload
    return payload


def clear_question_runtime_map_cache() -> None:
    global _MAP_CACHE, _CISCO_MAP_CACHE
    _MAP_CACHE = None
    _CISCO_MAP_CACHE = None


def load_cisco_question_runtime_map(*, reload: bool = False) -> dict[str, Any]:
    """Load the separate Cisco 50-question runtime map.

    Kept in its own file (never merged into the 105 map) to avoid exact-match
    precedence collisions — the Cisco map is consulted only after a 105 miss
    (Cisco plan §8.3 pitfall #3).
    """
    global _CISCO_MAP_CACHE
    if not reload and _CISCO_MAP_CACHE is not None:
        return _CISCO_MAP_CACHE
    if not _CISCO_MAP_PATH.exists():
        _CISCO_MAP_CACHE = {"entries": []}
        return _CISCO_MAP_CACHE
    payload = json.loads(_CISCO_MAP_PATH.read_text(encoding="utf-8"))
    _CISCO_MAP_CACHE = payload
    return payload


def list_question_runtime_entries(*, reload: bool = False) -> list[dict[str, Any]]:
    return list(load_question_runtime_map(reload=reload).get("entries", []))


def list_cisco_question_runtime_entries(*, reload: bool = False) -> list[dict[str, Any]]:
    """Return Cisco entries normalized to the shared registry-row shape.

    The Cisco map keys rows by `question_id`; downstream readers
    (`parser._registry_str`, route adjudication) expect `question_ref`. We mirror
    `question_id` into `question_ref` and stamp the registry source so the parser
    schema is identical to a 105 row.
    """
    normalized: list[dict[str, Any]] = []
    for entry in load_cisco_question_runtime_map(reload=reload).get("entries", []):
        row = dict(entry)
        if not row.get("question_ref"):
            row["question_ref"] = row.get("question_id")
        row.setdefault("manifest_coverage_id", None)
        row.setdefault("question_number", None)
        row["registry_source"] = "cisco_question_runtime_map_v1"
        normalized.append(row)
    return normalized


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


def match_question_runtime_entry(query: str, *, reload: bool = False) -> dict[str, Any] | None:
    """Return the canonical 105-question row for an exact normalized query match."""
    normalized = _normalize_question_text(query)
    if not normalized:
        return None
    for entry in list_question_runtime_entries(reload=reload):
        question = entry.get("question")
        if isinstance(question, str) and _normalize_question_text(question) == normalized:
            return entry
    # Cisco precision layer: consulted only after a 105 miss (never merged —
    # collision guard, Cisco plan §8.3 pitfall #3).
    for entry in list_cisco_question_runtime_entries(reload=reload):
        question = entry.get("question")
        if isinstance(question, str) and _normalize_question_text(question) == normalized:
            return entry
    return None


def nearest_question_runtime_entry(
    query: str,
    *,
    reload: bool = False,
    threshold: float = _NEAR_MATCH_THRESHOLD,
) -> dict[str, Any] | None:
    """Return the nearest 105-question row when token overlap is unambiguous."""
    query_tokens = _question_tokens(query)
    if not query_tokens:
        return None

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in list_question_runtime_entries(reload=reload):
        question = entry.get("question")
        if not isinstance(question, str):
            continue
        score = _token_similarity(query_tokens, _question_tokens(question))
        if score >= threshold:
            scored.append((score, entry))

    # Cisco precision layer is consulted only when the 105 map yields no nearest
    # match, preserving 105 precedence (never merged — Cisco plan §8.3 #3).
    if not scored:
        for entry in list_cisco_question_runtime_entries(reload=reload):
            question = entry.get("question")
            if not isinstance(question, str):
                continue
            score = _token_similarity(query_tokens, _question_tokens(question))
            if score >= threshold:
                scored.append((score, entry))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.08:
        return None
    match = dict(scored[0][1])
    match["_near_match_score"] = round(scored[0][0], 4)
    return match


def manifest_coverage_ids_from_map(*, reload: bool = False) -> frozenset[str]:
    ids: set[str] = set()
    for entry in list_question_runtime_entries(reload=reload):
        coverage_id = entry.get("manifest_coverage_id")
        if isinstance(coverage_id, str) and coverage_id:
            ids.add(coverage_id)
    return frozenset(ids)


def _normalize_question_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _question_tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(value.lower()) if token not in _STOP_WORDS and len(token) > 1}


def _token_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    jaccard = overlap / len(left | right)
    containment = overlap / min(len(left), len(right))
    return (0.65 * containment) + (0.35 * jaccard)
