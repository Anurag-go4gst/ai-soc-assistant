from __future__ import annotations

import re

from app.query_understanding.models import OutputTemplate, QueryEntities, QueryUnderstandingResult, RequestedOutputType
from app.query_understanding.time_window import normalize_time_window
from app.use_cases.registry import match_use_cases

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
INDEX_RE = re.compile(r"\bindex=([^\s|]+)", re.IGNORECASE)
SOURCETYPE_RE = re.compile(r"\bsourcetype=([^\s|]+)", re.IGNORECASE)
ALERT_RE = re.compile(r"\b(?:alert_id|alert|notable|event_id|eventid)[:=]\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
HOST_RE = re.compile(r"\b(?:host|asset)[:=]\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
USER_RE = re.compile(r"\buser[:=]\s*([A-Za-z0-9_.@-]+)", re.IGNORECASE)

_MITRE_KEYWORDS = ("mitre", "att&ck", "attack technique", "map this alert", "map the alert")
_ALERT_CONTEXT_MARKERS = ("index=", "sourcetype=", "rule:", "rule ", "alert:", "notable", "signature=", "event id", "eventid")


def understand_query(query: str) -> QueryUnderstandingResult:
    normalized = " ".join(query.lower().split())
    use_cases = match_use_cases(query)
    primary_use_case = use_cases[0] if use_cases else None
    requested_output_type, output_template = _requested_output(normalized, primary_use_case.output_template if primary_use_case else None)
    ambiguity_flags = _ambiguity_flags(normalized)
    clarification_needed = bool(ambiguity_flags)
    clarification_question = _clarification_question(ambiguity_flags)

    return QueryUnderstandingResult(
        raw_query=query,
        normalized_query=normalized,
        primary_intent=primary_use_case.primary_skill if primary_use_case else "unknown",
        secondary_intents=[item.primary_skill for item in use_cases[1:] if item.primary_skill != (primary_use_case.primary_skill if primary_use_case else None)],
        requested_output_type=requested_output_type,
        output_template=output_template,
        entities=_entities(query),
        ambiguity_flags=ambiguity_flags,
        confidence=primary_use_case.confidence if primary_use_case else 0.2,
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
        mapped_use_case_ids=[item.use_case_id for item in use_cases],
    )


def _requested_output(normalized: str, use_case_template: str | None) -> tuple[RequestedOutputType, OutputTemplate]:
    if any(term in normalized for term in ("generate spl", "write spl", "produce spl", "create spl", "spl query", "optimize spl")):
        return RequestedOutputType.SPL, OutputTemplate.SPL_RESPONSE
    if any(term in normalized for term in ("sop", "playbook", "runbook", "standard operating procedure")):
        return RequestedOutputType.SOP, OutputTemplate.SOP_RESPONSE
    if any(term in normalized for term in _MITRE_KEYWORDS):
        return RequestedOutputType.MITRE_MAPPING, OutputTemplate.MITRE_MAPPING_RESPONSE
    if any(term in normalized for term in ("investigation note", "draft ticket", "create ticket", "draft incident")):
        return RequestedOutputType.NOTE, OutputTemplate.NOTE_RESPONSE
    if any(term in normalized for term in ("next pivots", "recommend pivots", "action plan", "containment plan")):
        return RequestedOutputType.ACTION_PLAN, OutputTemplate.INVESTIGATION_ANSWER
    if any(term in normalized for term in ("summarize", "summary")):
        return RequestedOutputType.SUMMARY, OutputTemplate.INVESTIGATION_ANSWER
    if use_case_template:
        try:
            return RequestedOutputType.INVESTIGATION, OutputTemplate(use_case_template)
        except ValueError:
            return RequestedOutputType.INVESTIGATION, OutputTemplate.INVESTIGATION_ANSWER
    return RequestedOutputType.CLARIFICATION, OutputTemplate.CLARIFICATION_RESPONSE


def _entities(query: str) -> QueryEntities:
    ips = IP_RE.findall(query)
    hosts = HOST_RE.findall(query)
    users = USER_RE.findall(query)
    return QueryEntities(
        asset=hosts,
        host=hosts,
        user=users,
        source_ip=ips,
        destination_ip=[],
        time_window=normalize_time_window(query),
        index=INDEX_RE.findall(query),
        sourcetype=SOURCE_TYPE_CLEANUP(SOURCETYPE_RE.findall(query)),
        alert_id=ALERT_RE.findall(query),
        event_type=_event_types(query),
    )


def SOURCE_TYPE_CLEANUP(values: list[str]) -> list[str]:
    return [value.strip('"') for value in values]


def _event_types(query: str) -> list[str]:
    normalized = query.lower()
    types = []
    if "failure" in normalized or "failed login" in normalized:
        types.append("authentication_failure")
    if "success" in normalized or "successful login" in normalized:
        types.append("authentication_success")
    if "lockout" in normalized or "locked" in normalized:
        types.append("account_lockout")
    return types


def _ambiguity_flags(normalized: str) -> list[str]:
    flags = []
    if any(keyword in normalized for keyword in _MITRE_KEYWORDS) and not any(marker in normalized for marker in _ALERT_CONTEXT_MARKERS) and len(normalized) <= 160:
        flags.append("mitre_mapping_requires_alert_context")
    return flags


def _clarification_question(flags: list[str]) -> str | None:
    if "mitre_mapping_requires_alert_context" in flags:
        return "Share the alert title, detection rule, notable/event ID, or SPL with sample fields before MITRE mapping."
    return None
