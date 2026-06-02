from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.use_cases.models import UseCaseDefinition, UseCaseSelection

CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_use_case_catalog() -> list[UseCaseDefinition]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [UseCaseDefinition(**item) for item in payload.get("use_cases", [])]


def get_use_case(use_case_id: str) -> UseCaseDefinition | None:
    return next((item for item in load_use_case_catalog() if item.use_case_id == use_case_id), None)


def match_use_cases(query: str, *, limit: int = 3) -> list[UseCaseSelection]:
    normalized = " ".join(query.lower().split())
    matches: list[UseCaseSelection] = []
    for use_case in load_use_case_catalog():
        matched = [pattern for pattern in _expanded_match_terms(use_case) if pattern.lower() in normalized]
        if not matched:
            continue
        confidence = min(
            0.95,
            0.62
            + (0.05 * len(matched))
            + _canonical_term_boost(matched, use_case.intent_patterns)
            + _intent_boost(normalized, use_case.use_case_id),
        )
        matches.append(
            UseCaseSelection(
                use_case_id=use_case.use_case_id,
                display_name=use_case.display_name,
                category=use_case.category,
                primary_skill=use_case.primary_skill,
                confidence=confidence,
                matched_patterns=matched,
                default_spl_template=use_case.default_spl_template,
                output_template=use_case.output_template,
                required_sources=use_case.required_sources,
                optional_sources=use_case.optional_sources,
                action_capability_tier=use_case.action_capability_tier,
            )
        )
    return sorted(matches, key=lambda item: item.confidence, reverse=True)[:limit]


def _expanded_match_terms(use_case: UseCaseDefinition) -> list[str]:
    terms = [
        *use_case.intent_patterns,
        use_case.display_name,
        *use_case.example_queries,
    ]
    normalized_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = " ".join(term.lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_terms.append(term)
    return normalized_terms


def _canonical_term_boost(matched: list[str], intent_patterns: list[str]) -> float:
    canonical = {" ".join(item.lower().split()) for item in intent_patterns}
    matched_canonical = {" ".join(item.lower().split()) for item in matched}
    return 0.06 if canonical & matched_canonical else 0.0


def _intent_boost(normalized_query: str, use_case_id: str) -> float:
    if use_case_id == "soc_show_sop" and any(term in normalized_query for term in ("sop", "playbook", "runbook")):
        return 0.18
    if use_case_id == "soc_generate_spl" and "spl" in normalized_query:
        return 0.18
    if use_case_id == "soc_map_alert_mitre" and any(term in normalized_query for term in ("mitre", "att&ck")):
        return 0.18
    return 0.0
