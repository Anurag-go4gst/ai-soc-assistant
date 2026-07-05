"""Deterministic grounding for advisory evidence-observer claims."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from app.llm.evidence_observer import WITHHELD_ROW_TEXT
from app.synthesis.models import GovernedEvidenceObservation

_QUOTED = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"\b[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){2,7}\b")
_HOSTNAME = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)+\b")
_DOMAIN = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)+\b")
_FIELD_VALUE = re.compile(r"\b(?:user|host|src|dest|src_ip|dest_ip)=([^\s,;]+)", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


@dataclass(frozen=True)
class DroppedObservation:
    observation: GovernedEvidenceObservation
    reason: str
    detail: str | None = None


@dataclass(frozen=True)
class ObservationGroundingResult:
    grounded_observations: list[GovernedEvidenceObservation] = field(default_factory=list)
    dropped: list[DroppedObservation] = field(default_factory=list)

    @property
    def grounded_count(self) -> int:
        return len(self.grounded_observations)

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)


def ground_evidence_observations(
    observations: list[GovernedEvidenceObservation],
    *,
    row_text_by_index: Mapping[int, str],
) -> ObservationGroundingResult:
    grounded: list[GovernedEvidenceObservation] = []
    dropped: list[DroppedObservation] = []
    for observation in observations:
        reason = _drop_reason(observation, row_text_by_index)
        if reason is None:
            grounded.append(observation)
        else:
            dropped.append(DroppedObservation(observation=observation, reason="grounding_failed", detail=reason))
    return ObservationGroundingResult(grounded_observations=grounded, dropped=dropped)


def _drop_reason(
    observation: GovernedEvidenceObservation,
    row_text_by_index: Mapping[int, str],
) -> str | None:
    missing_refs = [ref for ref in observation.row_refs if ref not in row_text_by_index]
    if missing_refs:
        return f"missing_row_ref:{missing_refs[0]}"

    referenced_rows = [row_text_by_index[ref] for ref in observation.row_refs]
    if any(WITHHELD_ROW_TEXT in row for row in referenced_rows):
        return "withheld_row_ref"

    haystack = "\n".join(referenced_rows).lower()
    claim = observation.claim
    claim_lower = claim.lower()

    for token in _candidate_tokens(claim, referenced_rows):
        if token.lower() not in haystack:
            return f"ungrounded_token:{token}"

    for number in _NUMBER.findall(claim):
        if number not in haystack and number != str(len(observation.row_refs)):
            return f"ungrounded_number:{number}"

    return None


def _candidate_tokens(claim: str, referenced_rows: list[str]) -> list[str]:
    tokens: list[str] = []
    for match in _QUOTED.finditer(claim):
        token = (match.group(1) or match.group(2) or "").strip()
        if token:
            tokens.append(token)
    tokens.extend(_IPV4.findall(claim))
    tokens.extend(_IPV6.findall(claim))
    tokens.extend(_HOSTNAME.findall(claim))
    tokens.extend(_DOMAIN.findall(claim))

    claim_lower = claim.lower()
    for row in referenced_rows:
        for value in _FIELD_VALUE.findall(row):
            clean = value.strip()
            if clean and clean.lower() in claim_lower:
                tokens.append(clean)

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(token)
    return deduped
