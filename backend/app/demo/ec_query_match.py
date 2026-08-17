"""Fuzzy query matching for Experience Center scenario picker autocomplete."""

from __future__ import annotations

import re
from typing import Any

from app.demo.scenarios import SCENARIOS, _display_query, _normalize_query

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    normalized = _normalize_query(text)
    return {token for token in _TOKEN_RE.findall(normalized) if len(token) > 1}


def _phrase_entries() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for scenario in SCENARIOS.values():
        if scenario.fsm_step == 0:
            continue
        if getattr(scenario, "picker_tier", "leadership") not in {"leadership", "lab"}:
            continue
        phrases = [scenario.query, _display_query(scenario), *scenario.aliases]
        seen: set[str] = set()
        for phrase in phrases:
            if not phrase or phrase in seen:
                continue
            seen.add(phrase)
            rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "label": scenario.label,
                    "question": phrase,
                }
            )
    return rows


def score_query_match(user_text: str, candidate: str) -> float:
    """Token overlap + substring bonus; not exact-string only."""
    user_norm = _normalize_query(user_text)
    cand_norm = _normalize_query(candidate)
    if not user_norm:
        return 0.0
    if user_norm == cand_norm:
        return 1.0
    if cand_norm.startswith(user_norm) or user_norm in cand_norm:
        return 0.92
    user_tokens = _tokens(user_text)
    cand_tokens = _tokens(candidate)
    if not user_tokens or not cand_tokens:
        return 0.0
    overlap = len(user_tokens & cand_tokens)
    if overlap == 0:
        return 0.0
    recall = overlap / len(user_tokens)
    precision = overlap / len(cand_tokens)
    f1 = 2 * recall * precision / (recall + precision)
    return min(1.0, f1)


def suggest_ec_queries(prefix: str, *, limit: int = 8) -> list[dict[str, Any]]:
    trimmed = prefix.strip()
    if len(trimmed) < 2:
        return []
    scored: list[tuple[float, dict[str, str]]] = []
    for entry in _phrase_entries():
        score = score_query_match(trimmed, entry["question"])
        if score < 0.18:
            continue
        scored.append((score, entry))
    scored.sort(key=lambda row: (-row[0], row[1]["question"]))
    best_per_scenario: dict[str, tuple[float, dict[str, str]]] = {}
    for score, entry in scored:
        scenario_id = entry["scenario_id"]
        if scenario_id not in best_per_scenario or score > best_per_scenario[scenario_id][0]:
            best_per_scenario[scenario_id] = (score, entry)
    ranked = sorted(best_per_scenario.values(), key=lambda row: (-row[0], row[1]["question"]))
    return [
        {
            "scenario_id": entry["scenario_id"],
            "label": entry["label"],
            "question": entry["question"],
            "score": round(score, 3),
        }
        for score, entry in ranked[:limit]
    ]


def resolve_ec_query_fuzzy(query: str, *, min_score: float = 0.38) -> tuple[str | None, float]:
    trimmed = query.strip()
    if not trimmed:
        return None, 0.0
    best_id: str | None = None
    best_score = 0.0
    for entry in _phrase_entries():
        score = score_query_match(trimmed, entry["question"])
        if score > best_score:
            best_score = score
            best_id = entry["scenario_id"]
    if best_score < min_score:
        return None, best_score
    return best_id, best_score
