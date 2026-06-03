"""Resolve MITRE mappings from 105 registry mitre_permitted[] + use-case KB bridge."""

from __future__ import annotations

from typing import Any

from app.coverage.question_runtime_map import question_runtime_entry
from app.threat.mitre_kb import MitreMappingDecision, map_mitre_for_use_case

_STATUS_BY_KB_OVERLAP = "candidate"


def mitre_permitted_for_question_ref(question_ref: str | None) -> list[str]:
    if not question_ref:
        return []
    entry = question_runtime_entry(question_ref)
    if not entry:
        return []
    permitted = entry.get("mitre_permitted")
    if not isinstance(permitted, list):
        return []
    return [str(item).upper() for item in permitted if item]


def map_mitre_for_permitted_techniques(
    technique_ids: list[str],
    source_refs: list[str],
) -> list[MitreMappingDecision]:
    """Map explicit permitted technique IDs (subset already curated on registry row)."""
    if not technique_ids:
        return []
    from app.threat.mitre_kb import load_mitre_techniques

    by_id = {t.technique_id.upper(): t for t in load_mitre_techniques()}
    decisions: list[MitreMappingDecision] = []
    for tid in technique_ids:
        upper = tid.upper()
        technique = by_id.get(upper)
        if technique is None:
            continue
        decisions.append(
            MitreMappingDecision(
                technique_id=technique.technique_id,
                name=technique.name,
                tactic=technique.tactic,
                status=_STATUS_BY_KB_OVERLAP,
                why=f"Registry mitre_permitted[] entry (runtime KB overlap)",
                evidence_requirements=list(technique.evidence_requirements),
                source_refs=list(source_refs),
                recommended_pivots=list(technique.recommended_pivots),
            )
        )
    return decisions


def resolve_mitre_mappings_for_chat(
    *,
    question_ref: str | None,
    use_case_id: str | None,
    source_refs: list[str],
) -> list[MitreMappingDecision]:
    """Use-case KB bridge first; augment with 105 mitre_permitted[] KB overlaps."""
    seen: set[str] = set()
    merged: list[MitreMappingDecision] = []

    for item in map_mitre_for_use_case(use_case_id, source_refs):
        key = item.technique_id.upper()
        if key not in seen:
            seen.add(key)
            merged.append(item)

    permitted = mitre_permitted_for_question_ref(question_ref)
    for item in map_mitre_for_permitted_techniques(permitted, source_refs):
        key = item.technique_id.upper()
        if key not in seen:
            seen.add(key)
            merged.append(item)

    return merged
