"""Reference query qualification — deterministic signals + classifier hints."""

from __future__ import annotations

import re
from functools import lru_cache
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
    "are we vulnerable",
    "check our",
    "which devices",
    "is our environment vulnerable",
    "are our systems vulnerable",
    "is it patched",
    "patched against",
    "our exposure",
    "exposure in our environment",
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

_KNOWLEDGE_DENIAL_SIGNALS = (
    "explicit_log_search",
    "live_data_request",
    "block_or_contain",
    "run_execution",
)


@lru_cache(maxsize=None)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(" ".join(phrase.lower().split())).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


def _contains_phrase(normalized: str, markers: tuple[str, ...]) -> bool:
    """Return whether any complete marker phrase occurs in normalized text."""
    return any(_phrase_pattern(marker).search(normalized) for marker in markers)


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
    status_check = _contains_phrase(normalized, _STATUS_MARKERS)
    evidence_corr = _contains_phrase(normalized, _CORRELATION_MARKERS)
    action = _contains_phrase(normalized, _ACTION_MARKERS)
    investigation = _contains_phrase(normalized, _INVESTIGATION_MARKERS)
    knowledge_only_phrase = _contains_phrase(normalized, _KNOWLEDGE_ONLY_MARKERS)
    environment_scope = status_check or _contains_phrase(normalized, ("our", "our systems"))
    signal_denies_knowledge_only = any(
        bool((signals or {}).get(name)) for name in _KNOWLEDGE_DENIAL_SIGNALS
    )

    if action:
        execution_action = _contains_phrase(normalized, ("remediate", "patch now"))
        scopes.append(
            "remediation_execution" if execution_action else "remediation_recommendation"
        )
    if status_check:
        scopes.append("environment_status")
    if evidence_corr:
        scopes.append("evidence_correlation")
    if investigation:
        scopes.append("investigation")
    if knowledge_only_phrase and not (
        status_check
        or evidence_corr
        or action
        or investigation
        or signal_denies_knowledge_only
    ):
        scopes.append("knowledge_only")

    if (
        intent_family in {"reference_knowledge", "knowledge_only"}
        and not scopes
        and not signal_denies_knowledge_only
    ):
        scopes.append("knowledge_only")

    if len(scopes) > 1:
        scopes = ["composite"]

    if (
        not scopes
        and reference_ids
        and knowledge_only_phrase
        and not signal_denies_knowledge_only
    ):
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
