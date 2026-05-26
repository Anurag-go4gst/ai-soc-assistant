from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

MITRE_PATH = Path(__file__).with_name("mitre_attack_subset.json")
MITRE_MAPPING_STATUSES = ("candidate", "supported", "requires_validation", "confirmed", "analyst_review")


class MitreTechnique(BaseModel):
    technique_id: str
    name: str
    tactic: str
    description: str
    detection_patterns: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    candidate_vs_confirmed_rules: dict[str, list[str]] = Field(default_factory=dict)
    related_use_cases: list[str] = Field(default_factory=list)
    recommended_pivots: list[str] = Field(default_factory=list)


class MitreMappingDecision(BaseModel):
    technique_id: str
    name: str
    tactic: str
    status: str
    why: str
    evidence_requirements: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    recommended_pivots: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _payload() -> dict[str, object]:
    return json.loads(MITRE_PATH.read_text(encoding="utf-8"))


def mitre_metadata() -> dict[str, object]:
    return dict(_payload().get("metadata") or {})


def load_mitre_techniques() -> list[MitreTechnique]:
    return [MitreTechnique(**item) for item in (_payload().get("techniques") or [])]


def map_mitre_for_use_case(use_case_id: str | None, source_refs: list[str]) -> list[MitreMappingDecision]:
    if not use_case_id:
        return []
    decisions: list[MitreMappingDecision] = []
    for technique in load_mitre_techniques():
        if use_case_id not in technique.related_use_cases:
            continue
        status = _status_for(use_case_id, technique.technique_id)
        decisions.append(
            MitreMappingDecision(
                technique_id=technique.technique_id,
                name=technique.name,
                tactic=technique.tactic,
                status=status,
                why=_why(status, technique.technique_id),
                evidence_requirements=technique.evidence_requirements,
                source_refs=source_refs,
                recommended_pivots=technique.recommended_pivots,
            )
        )
    return decisions


def _status_for(use_case_id: str, technique_id: str) -> str:
    if technique_id == "T1110.001" and use_case_id == "auth_failed_login_spike":
        return "supported"
    if technique_id == "T1078":
        return "candidate"
    return "requires_validation"


def _why(status: str, technique_id: str) -> str:
    if status == "supported":
        return f"{technique_id} is supported by the use-case pattern, but confirmation requires benign-cause validation."
    if status == "candidate":
        return f"{technique_id} is a candidate until success/account legitimacy evidence is reviewed."
    return f"{technique_id} requires additional validation evidence."
