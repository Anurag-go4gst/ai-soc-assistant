"""Reference query qualification — deterministic signals + classifier hints."""

from __future__ import annotations

import re
from typing import Any

from app.chat.contracts.reference_qualification import ReferenceQueryQualification, RequestedScope

_REF_ID_RE = re.compile(
    r"\b(?:CVE-\d{4}-\d+|T\d{4}(?:\.\d{3})?|AML\.T\d{4})\b",
    re.IGNORECASE,
)

_KNOWLEDGE_ONLY_MARKERS = (
    "what is",
    "explain",
    "meaning of",
    "define",
    "describe",
    "details of",
    "tell me about",
)

_STATUS_MARKERS = (
    "are we affected",
    "are our systems",
    "check our",
    "which devices",
    "is it patched",
    "patched against",
    "vulnerable",
    "exposure",
    "affected by",
)

_CORRELATION_MARKERS = (
    "was this observed",
    "in alert",
    "alert id",
    "alert alt",
    "correlate",
    "seen in our",
)

_ACTION_MARKERS = (
    "remediate",
    "patch now",
    "block",
    "contain",
    "isolate",
    "execute",
    "run spl",
)

_INVESTIGATION_MARKERS = (
    "investigate",
    "hunt",
    "unusual",
    "anomaly",
    "suspicious",
)


def extract_reference_ids(query: str, entities: Any | None = None) -> list[str]:
    ids = [m.upper() for m in _REF_ID_RE.findall(query)]
    if entities is not None:
        for attr in ("cve_ids", "mitre_techniques"):
            values = getattr(entities, attr, None)
            if isinstance(values, list):
                ids.extend(str(v).upper() for v in values if v)
    return list(dict.fromkeys(ids))


def qualify_reference_query(
    query: str,
    *,
    intent_family: str | None = None,
    signals: dict[str, Any] | None = None,
    entities: Any | None = None,
) -> ReferenceQueryQualification:
    normalized = " ".join(query.lower().split())
    reference_ids = extract_reference_ids(query, entities)
    reference_types: list[str] = []
    for ref in reference_ids:
        if ref.startswith("CVE-"):
            reference_types.append("CVE")
        elif ref.startswith("AML."):
            reference_types.append("ATLAS")
        elif ref.startswith("T"):
            reference_types.append("MITRE")

    scopes: list[RequestedScope] = []
    status_check = any(m in normalized for m in _STATUS_MARKERS)
    evidence_corr = any(m in normalized for m in _CORRELATION_MARKERS)
    action = any(m in normalized for m in _ACTION_MARKERS)
    investigation = any(m in normalized for m in _INVESTIGATION_MARKERS)
    knowledge_only_phrase = any(normalized.startswith(m) or f" {m} " in f" {normalized} " for m in _KNOWLEDGE_ONLY_MARKERS)
    environment_scope = status_check or "our " in normalized or "our systems" in normalized

    if action:
        scopes.append("remediation_execution" if "remediate" in normalized or "patch now" in normalized else "remediation_recommendation")
    if status_check:
        scopes.append("environment_status")
    if evidence_corr:
        scopes.append("evidence_correlation")
    if investigation:
        scopes.append("investigation")
    if knowledge_only_phrase and not (status_check or evidence_corr or action or investigation):
        scopes.append("knowledge_only")

    if intent_family in {"reference_knowledge", "knowledge_only"} and not scopes:
        scopes.append("knowledge_only")

    if len(scopes) > 1:
        scopes = ["composite"]

    if not scopes and reference_ids and knowledge_only_phrase:
        scopes = ["knowledge_only"]
    elif not scopes and reference_ids:
        # Identifier alone is ambiguous — remain T4 until classifier confirms knowledge-only.
        scopes = ["composite"]

    confidence = 0.75
    source: str = "deterministic_rule"
    if intent_family in {"reference_knowledge", "knowledge_only"}:
        confidence = 0.9
        source = "classifier"

    return ReferenceQueryQualification(
        reference_types=list(dict.fromkeys(reference_types)),
        reference_ids=reference_ids,
        requested_scopes=scopes,
        status_check_required=status_check,
        evidence_correlation_required=evidence_corr,
        action_requested=action,
        environment_scope_present=environment_scope,
        confidence=confidence,
        qualification_source=source,  # type: ignore[arg-type]
    )
