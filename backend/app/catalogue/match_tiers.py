"""Unified catalogue match tiers (T0–T4) — adapter over existing catalog surfaces.

This module does not replace the live router. It documents and tests how queries
map onto the reconciled catalogue layers:

- T0: reference knowledge (AML/CVE/MITRE ids)
- T1: exact 105 / frozen runtime-map rows
- T2: use-case catalog substring match
- T3: fuzzy/alias-normalized catalogue match
- T4: out-of-registry / no bind
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.query_understanding.parser import understand_query
from app.use_cases.registry import match_use_cases

CatalogueTier = Literal["T0", "T1", "T2", "T3", "T4"]
BindingCandidateTier = Literal["T1", "T2", "T3", "T4"]

_REFERENCE_ID_RE = re.compile(
    r"\b(?:AML\.T\d{4}|CVE-\d{4}-\d+|T\d{4}(?:\.\d{3})?)\b",
    re.IGNORECASE,
)

_T1_PATHS = frozenset({"exact_105_question", "exact_105_plus_use_case_catalog"})
_T2_PATHS = frozenset({"use_case_catalog"})
_T3_PATHS = frozenset({"near_105_question", "semantic_105_question"})

_TYPO_ALIASES: dict[str, str] = {
    "lgon": "login",
    "logn": "login",
    "logni": "login",
    "faield": "failed",
    "fialed": "failed",
    "faile": "failed",
    "spikee": "spike",
}


class CatalogueMatchResult(BaseModel):
    entry_id: str
    tier: CatalogueTier
    source: str
    match_path: str
    match_reason: str
    use_case_id: str | None = None
    question_ref: str | None = None
    skill_id: str | None = None
    spl_template_id: str | None = None
    alias_applied: bool = False
    matched_patterns: list[str] = Field(default_factory=list)


class CatalogueBindingCandidate(BaseModel):
    """Non-authoritative catalogue bind proposed to the canonical routing seam."""

    entry_id: str
    binding_candidate_tier: BindingCandidateTier
    source: str
    observed_match_path: str
    candidate_match_path: str
    effective_match_path: str
    match_reason: str
    decision_reason: str = "not_reconciled"
    accepted: bool = False
    use_case_id: str | None = None
    question_ref: str | None = None
    skill_id: str | None = None
    spl_template_id: str | None = None
    alias_applied: bool = False
    matched_patterns: list[str] = Field(default_factory=list)


def normalize_query_aliases(query: str) -> tuple[str, bool]:
    """Apply bounded typo aliases; returns normalized query and whether any alias fired."""
    tokens = query.split()
    changed = False
    normalized_tokens: list[str] = []
    for token in tokens:
        lowered = token.lower()
        replacement = _TYPO_ALIASES.get(lowered)
        if replacement is not None:
            normalized_tokens.append(replacement)
            changed = True
        else:
            normalized_tokens.append(token)
    return " ".join(normalized_tokens), changed


def _reference_match(query: str) -> CatalogueMatchResult | None:
    match = _REFERENCE_ID_RE.search(query)
    if not match:
        return None
    ref = match.group(0).upper()
    return CatalogueMatchResult(
        entry_id=f"reference:{ref}",
        tier="T0",
        source="reference_registry",
        match_path="reference_knowledge",
        match_reason="reference_id_detected",
        matched_patterns=[ref],
    )


def _tier_from_understanding(understanding: Any) -> CatalogueMatchResult | None:
    path = str(getattr(understanding, "deterministic_match_path", "") or "")
    use_case = getattr(understanding, "primary_use_case", None)
    use_case_id = str(getattr(use_case, "use_case_id", "") or "") or None
    question_ref = None
    registry_entry = getattr(understanding, "exact_question_registry_entry", None)
    if isinstance(registry_entry, dict):
        question_ref = str(registry_entry.get("question_ref") or "") or None

    if path in _T1_PATHS:
        entry_id = f"q105:{question_ref}" if question_ref else f"use_case:{use_case_id or 'unknown'}"
        return CatalogueMatchResult(
            entry_id=entry_id,
            tier="T1",
            source="cisco_question_runtime_map_v1",
            match_path=path,
            match_reason="exact_runtime_map",
            use_case_id=use_case_id,
            question_ref=question_ref,
            skill_id=str(getattr(use_case, "primary_skill", "") or "") or None,
            spl_template_id=str(getattr(use_case, "default_spl_template", "") or "") or None,
        )

    if path in _T2_PATHS and use_case_id:
        return CatalogueMatchResult(
            entry_id=f"use_case:{use_case_id}",
            tier="T2",
            source="use_cases_catalog",
            match_path=path,
            match_reason="use_case_catalog_match",
            use_case_id=use_case_id,
            skill_id=str(getattr(use_case, "primary_skill", "") or "") or None,
            spl_template_id=str(getattr(use_case, "default_spl_template", "") or "") or None,
        )

    if path in _T3_PATHS:
        return CatalogueMatchResult(
            entry_id=f"q105:{question_ref or 'near'}",
            tier="T3",
            source="cisco_question_runtime_map_v1",
            match_path=path,
            match_reason="near_or_semantic_105",
            use_case_id=use_case_id,
            question_ref=question_ref,
        )

    return None


def _use_case_catalog_match(query: str, *, alias_applied: bool) -> CatalogueMatchResult | None:
    selections = match_use_cases(query, limit=1)
    if not selections:
        return None
    top = selections[0]
    return CatalogueMatchResult(
        entry_id=f"use_case:{top.use_case_id}",
        tier="T3" if alias_applied else "T2",
        source="fuzzy_alias_adapter" if alias_applied else "use_cases_catalog",
        match_path="fuzzy_alias_catalog" if alias_applied else "use_case_catalog",
        match_reason="alias_normalized_use_case_match" if alias_applied else "use_case_catalog_match",
        use_case_id=top.use_case_id,
        skill_id=top.primary_skill,
        spl_template_id=top.default_spl_template,
        alias_applied=alias_applied,
        matched_patterns=list(top.matched_patterns),
    )


def build_catalogue_binding_candidate(
    query: str,
    *,
    understanding: Any | None = None,
) -> CatalogueBindingCandidate:
    """Build a catalogue candidate without granting canonical T0 authority."""
    understanding = understanding or understand_query(query)
    observed_match_path = str(
        getattr(understanding, "deterministic_match_path", "") or "out_of_registry"
    )
    mapped = _tier_from_understanding(understanding)
    if mapped is None:
        mapped = _use_case_catalog_match(query, alias_applied=False)
    if mapped is None:
        normalized, alias_applied = normalize_query_aliases(query)
        if alias_applied:
            mapped = _use_case_catalog_match(normalized, alias_applied=True)
    if mapped is None:
        mapped = CatalogueMatchResult(
            entry_id="out_of_registry",
            tier="T4",
            source="use_cases_catalog",
            match_path="out_of_registry",
            match_reason="no_catalogue_bind",
        )
    if mapped.tier == "T0":
        raise ValueError("catalogue binding candidates cannot grant T0")
    return CatalogueBindingCandidate(
        entry_id=mapped.entry_id,
        binding_candidate_tier=mapped.tier,
        source=mapped.source,
        observed_match_path=observed_match_path,
        candidate_match_path=mapped.match_path,
        effective_match_path=observed_match_path,
        match_reason=mapped.match_reason,
        use_case_id=mapped.use_case_id,
        question_ref=mapped.question_ref,
        skill_id=mapped.skill_id,
        spl_template_id=mapped.spl_template_id,
        alias_applied=mapped.alias_applied,
        matched_patterns=list(mapped.matched_patterns),
    )


def match_catalogue_tier(query: str, *, understanding: Any | None = None) -> CatalogueMatchResult:
    """Compatibility classifier for tests and non-production inspection surfaces."""
    reference = _reference_match(query)
    if reference is not None:
        return reference

    candidate = build_catalogue_binding_candidate(query, understanding=understanding)
    return CatalogueMatchResult(
        entry_id=candidate.entry_id,
        tier=candidate.binding_candidate_tier,
        source=candidate.source,
        match_path=candidate.candidate_match_path,
        match_reason=candidate.match_reason,
        use_case_id=candidate.use_case_id,
        question_ref=candidate.question_ref,
        skill_id=candidate.skill_id,
        spl_template_id=candidate.spl_template_id,
        alias_applied=candidate.alias_applied,
        matched_patterns=list(candidate.matched_patterns),
    )
