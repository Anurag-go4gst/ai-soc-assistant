"""Deterministic saved-search-first preference before SPL generation (plan item 15)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.chat.canonical_facts_spine import harvest_canonical_facts_from_state
from app.orchestration.saved_search_allowlist import saved_search_name_allowed

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_TOKEN_LEN = 3
_MIN_OVERLAP = 2


@dataclass(frozen=True)
class SavedSearchHarvest:
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "description": self.description}


@dataclass
class SavedSearchPreference:
    status: str
    matched_name: str | None = None
    allowlisted: bool = False
    match_overlap: int = 0
    planned_tool: str | None = None
    advisory_names: list[str] = field(default_factory=list)
    analyst_message: str | None = None
    fallback_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "matched_name": self.matched_name,
            "allowlisted": self.allowlisted,
            "match_overlap": self.match_overlap,
            "planned_tool": self.planned_tool,
            "advisory_names": list(self.advisory_names),
            "analyst_message": self.analyst_message,
            "fallback_role": self.fallback_role,
        }


def tokenize_for_match(*texts: str | None) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        if not text:
            continue
        for raw in _TOKEN_RE.findall(str(text).lower()):
            if len(raw) >= _MIN_TOKEN_LEN:
                tokens.add(raw)
    return tokens


def saved_searches_from_knowledge_result(result: dict[str, Any]) -> list[SavedSearchHarvest]:
    if not isinstance(result, dict):
        return []
    rows: list[dict[str, Any]] = []
    objects = result.get("objects")
    if isinstance(objects, list):
        rows.extend(item for item in objects if isinstance(item, dict))
    for key in ("saved_searches", "rows"):
        raw = result.get(key)
        if isinstance(raw, list):
            rows.extend(item for item in raw if isinstance(item, dict))
    harvested: list[SavedSearchHarvest] = []
    seen: set[str] = set()
    for row in rows:
        object_type = str(row.get("object_type") or row.get("type") or row.get("kind") or "").lower()
        if object_type and object_type not in {"savedsearch", "saved_search", "saved search"}:
            continue
        name = str(row.get("name") or row.get("title") or row.get("saved_search") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        description = str(row.get("description") or row.get("search") or row.get("summary") or "").strip()
        harvested.append(SavedSearchHarvest(name=name, description=description))
    return harvested


def _overlap_score(query_tokens: set[str], candidate_tokens: set[str]) -> int:
    return len(query_tokens & candidate_tokens)


def evaluate_saved_search_preference(
    *,
    query: str,
    harvested: list[SavedSearchHarvest],
    extra_match_texts: list[str] | None = None,
) -> SavedSearchPreference:
    if not harvested:
        return SavedSearchPreference(status="no_harvest")

    query_tokens = tokenize_for_match(query, *(extra_match_texts or []))
    if not query_tokens:
        return SavedSearchPreference(
            status="advisory_only",
            advisory_names=[item.name for item in harvested],
            analyst_message="Harvested saved searches are listed for analyst context; SPL generation remains primary.",
        )

    best: SavedSearchHarvest | None = None
    best_overlap = 0
    for item in harvested:
        candidate_tokens = tokenize_for_match(item.name, item.description)
        overlap = _overlap_score(query_tokens, candidate_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best = item

    if best is None or best_overlap < _MIN_OVERLAP:
        return SavedSearchPreference(
            status="spl_generation",
            advisory_names=[item.name for item in harvested],
            analyst_message="No confident saved-search match; SPL generation remains primary.",
        )

    allowlisted = saved_search_name_allowed(best.name)
    if allowlisted:
        return SavedSearchPreference(
            status="primary_saved_search",
            matched_name=best.name,
            allowlisted=True,
            match_overlap=best_overlap,
            planned_tool="splunk_run_saved_search",
            advisory_names=[item.name for item in harvested if item.name != best.name],
            analyst_message=f"Existing corporate detection found: {best.name}",
            fallback_role="generated_spl_fallback",
        )

    return SavedSearchPreference(
        status="spl_generation",
        matched_name=best.name,
        allowlisted=False,
        match_overlap=best_overlap,
        advisory_names=[item.name for item in harvested],
        analyst_message=(
            f"Saved search '{best.name}' matches the turn intent but is not allowlisted; "
            "SPL generation remains primary."
        ),
    )


def harvest_texts_from_state(state: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    facts = harvest_canonical_facts_from_state(state)
    for fact in facts.facts:
        if fact.kind not in {"entity", "timeframe"}:
            continue
        payload = fact.payload if isinstance(fact.payload, dict) else {}
        for value in payload.values():
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
    intent = state.get("intent_classification")
    if isinstance(intent, dict):
        for key in ("primary_intent", "intent_family", "operation_type"):
            value = intent.get(key)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
    return texts


def preference_from_discovery_context(
    *,
    query: str,
    discovery_context: Mapping[str, Any] | None,
    state: Mapping[str, Any] | None = None,
) -> SavedSearchPreference | None:
    if not isinstance(discovery_context, Mapping):
        return None
    raw_items = discovery_context.get("harvested_saved_searches")
    if not isinstance(raw_items, list) or not raw_items:
        return None
    harvested = [
        SavedSearchHarvest(
            name=str(item.get("name") or ""),
            description=str(item.get("description") or ""),
        )
        for item in raw_items
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    if not harvested:
        return None
    extra = harvest_texts_from_state(state) if state is not None else []
    return evaluate_saved_search_preference(query=query, harvested=harvested, extra_match_texts=extra)


def apply_saved_search_preference_to_spl(
    preference: SavedSearchPreference,
    *,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Demote generated SPL to fallback when an allowlisted saved search is primary."""
    if preference.status != "primary_saved_search" or not preference.allowlisted or not preference.matched_name:
        return candidate_spl, spl_validation

    fallback_candidate = dict(candidate_spl) if isinstance(candidate_spl, dict) else None
    fallback_validation = dict(spl_validation) if isinstance(spl_validation, dict) else None

    primary_candidate: dict[str, Any] = {
        "source": "saved_search_preference",
        "saved_search_name": preference.matched_name,
        "planned_tool": preference.planned_tool or "splunk_run_saved_search",
        "generation_mode": "saved_search_primary",
        "fallback_candidate_spl": fallback_candidate,
        "fallback_spl_validation": fallback_validation,
        "analyst_message": preference.analyst_message,
    }
    if fallback_candidate and fallback_candidate.get("candidate_spl"):
        primary_candidate["candidate_spl"] = None
        primary_candidate["fallback_note"] = "Generated SPL available as fallback if saved search is rejected."

    primary_validation: dict[str, Any] = {
        "approved": True,
        "normalized_spl": None,
        "saved_search_name": preference.matched_name,
        "reject_reasons": [],
        "warnings": [],
        "policy_version": "saved-search-preference-v1",
        "execution_path": "saved_search_execution",
    }
    return primary_candidate, primary_validation
