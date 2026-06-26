from __future__ import annotations

import re

from app.coverage.question_runtime_map import match_question_runtime_entry, nearest_question_runtime_entry
from app.coverage.semantic_question_index import semantic_question_match
from app.query_understanding.models import OutputTemplate, QueryEntities, QueryUnderstandingResult, RequestedOutputType
from app.query_understanding.soc_investigation_shape import (
    detect_investigation_hypothesis_guidance,
    detect_soc_investigation_shape,
    prefers_guided_investigation_over_catalog,
)
from app.query_understanding.time_window import normalize_time_window
from app.use_cases.registry import load_use_case_catalog, match_use_cases
from app.use_cases.routing_authority import catalog_authority_row, llm_advisory_recommended

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
INDEX_RE = re.compile(r"\bindex=([^\s|]+)", re.IGNORECASE)
SOURCETYPE_RE = re.compile(r"\bsourcetype=([^\s|]+)", re.IGNORECASE)
ALERT_RE = re.compile(r"\b(?:alert_id|alert|notable|event_id|eventid)[:=]\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
HOST_RE = re.compile(r"\b(?:host|asset)[:=]\s*([A-Za-z0-9_.:-]+)", re.IGNORECASE)
USER_RE = re.compile(r"\buser[:=]\s*([A-Za-z0-9_.@-]+)", re.IGNORECASE)
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
MITRE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
PORT_RE = re.compile(r"\b(?:port|on port)\s+(\d{1,5})\b", re.IGNORECASE)
PURDUE_LAYER_RE = re.compile(r"\b(?:purdue\s+)?layer\s+(?:L)?([0-5])\b", re.IGNORECASE)
PURDUE_L_RE = re.compile(r"\bL([0-5])\b")
ZONE_RE = re.compile(r"\b(?:zone|vlan)\s+([A-Za-z0-9_.-]{2,40})\b", re.IGNORECASE)
OBSERVATION_WINDOW_RE = re.compile(
    r"\b(?:observation window(?:\s+of)?|over the (?:past|last)|during the (?:past|last))\s+"
    r"(\d+\s*(?:minute|minutes|min|mins|hour|hours|hr|hrs|day|days|h|m|d)s?)\b",
    re.IGNORECASE,
)

_MITRE_KEYWORDS = ("mitre", "att&ck", "attack technique", "map this alert", "map the alert")
_ALERT_CONTEXT_MARKERS = ("index=", "sourcetype=", "rule:", "rule ", "alert:", "notable", "signature=", "event id", "eventid")


def understand_query(query: str) -> QueryUnderstandingResult:
    normalized = " ".join(query.lower().split())
    use_cases = match_use_cases(query)
    primary_use_case = use_cases[0] if use_cases else None
    exact_question_registry_entry = match_question_runtime_entry(query)
    near_question_registry_entry = None if exact_question_registry_entry else nearest_question_runtime_entry(query)
    semantic_question_registry_entry = (
        None
        if (exact_question_registry_entry or near_question_registry_entry)
        else semantic_question_match(query)
    )
    question_registry_entry = (
        exact_question_registry_entry or near_question_registry_entry or semantic_question_registry_entry
    )
    requested_output_type, output_template = _requested_output(normalized, primary_use_case.output_template if primary_use_case else None)
    ambiguity_flags = _ambiguity_flags(normalized)
    registry_warnings = _registry_warnings(primary_use_case, question_registry_entry)
    clarification_needed = bool(ambiguity_flags)
    clarification_question = _clarification_question(ambiguity_flags)
    mapped_primary_skill = _mapped_primary_skill(primary_use_case, question_registry_entry)
    deterministic_match_path = _deterministic_match_path(
        exact_question_registry_entry=exact_question_registry_entry,
        near_question_registry_entry=near_question_registry_entry,
        semantic_question_registry_entry=semantic_question_registry_entry,
        primary_use_case=primary_use_case,
    )

    result = QueryUnderstandingResult(
        raw_query=query,
        normalized_query=normalized,
        primary_intent=mapped_primary_skill,
        secondary_intents=[item.primary_skill for item in use_cases[1:] if item.primary_skill != (primary_use_case.primary_skill if primary_use_case else None)],
        requested_output_type=requested_output_type,
        output_template=output_template,
        entities=_entities(query),
        ambiguity_flags=ambiguity_flags,
        confidence=primary_use_case.confidence if primary_use_case else (0.55 if question_registry_entry else 0.2),
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
        mapped_use_case_ids=[item.use_case_id for item in use_cases],
        mapped_question_ref=_registry_str(question_registry_entry, "question_ref"),
        mapped_question_number=_registry_int(question_registry_entry, "question_number"),
        mapped_coverage_id=_registry_str(question_registry_entry, "manifest_coverage_id"),
        mapped_pattern_type=_registry_str(question_registry_entry, "pattern_type"),
        mapped_primary_skill=_registry_str(question_registry_entry, "proposed_primary_skill"),
        mapped_operation_type=_registry_str(question_registry_entry, "proposed_operation_type"),
        question_registry_match_source=_question_registry_match_source(
            exact_question_registry_entry, near_question_registry_entry, semantic_question_registry_entry
        ),
        question_registry_match_score=_registry_score(near_question_registry_entry or semantic_question_registry_entry),
        question_registry_observation_only=True,
        use_case_catalog_size=len(load_use_case_catalog()),
        use_case_match_source="expanded_catalog" if primary_use_case else None,
        deterministic_match_path=deterministic_match_path,
        registry_consistency=_registry_consistency(primary_use_case, question_registry_entry),
        registry_warnings=registry_warnings,
        llm_advisory_recommended=_llm_advisory_recommended(
            deterministic_match_path,
            registry_warnings,
            catalog_row=catalog_authority_row(primary_use_case.use_case_id if primary_use_case else None),
        ),
    )
    shaped = (
        detect_investigation_hypothesis_guidance(query)
        or detect_soc_investigation_shape(
            query,
            exact_105_match=deterministic_match_path in {"exact_105_question", "exact_105_plus_use_case_catalog"},
        )
    ) and deterministic_match_path in {"out_of_registry", "use_case_catalog"}
    rescue_guided = shaped and (
        deterministic_match_path == "out_of_registry"
        or prefers_guided_investigation_over_catalog(query)
    )
    return result.model_copy(
        update={
            "soc_investigation_shaped": shaped,
            "route_skill_candidate": "guided_investigation" if rescue_guided else None,
            "intent_candidate": "guided_investigation" if rescue_guided else None,
            "triage_signals": {
                "soc_investigation_shaped": shaped,
                "block_or_contain": False,
                "explicit_run_spl": False,
            },
        }
    )


def _requested_output(normalized: str, use_case_template: str | None) -> tuple[RequestedOutputType, OutputTemplate]:
    if any(
        term in normalized
        for term in (
            "generate spl",
            "write spl",
            "produce spl",
            "create spl",
            "spl query",
            "optimize spl",
            "draft spl",
            "draft a splunk search",
            "draft splunk search",
            "search logs",
            "search firewall logs",
            "search proxy logs",
            "search endpoint logs",
        )
    ):
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
        observation_window=_observation_window_phrase(query),
        index=INDEX_RE.findall(query),
        sourcetype=SOURCE_TYPE_CLEANUP(SOURCETYPE_RE.findall(query)),
        alert_id=ALERT_RE.findall(query),
        event_type=_event_types(query),
        cve_ids=_unique_preserve_order(CVE_RE.findall(query)),
        mitre_techniques=_unique_preserve_order(MITRE_RE.findall(query)),
        port_numbers=_extract_port_numbers(query),
        purdue_layers=_extract_purdue_layers(query),
        zone_labels=_unique_preserve_order(ZONE_RE.findall(query)),
    )


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _observation_window_phrase(query: str) -> str | None:
    match = OBSERVATION_WINDOW_RE.search(query)
    if not match:
        return None
    return match.group(0).strip()


def _extract_port_numbers(query: str) -> list[str]:
    ports = _unique_preserve_order(PORT_RE.findall(query))
    return [port for port in ports if 0 < int(port) <= 65535]


def _extract_purdue_layers(query: str) -> list[str]:
    layers = _unique_preserve_order(PURDUE_LAYER_RE.findall(query) + PURDUE_L_RE.findall(query))
    return [f"L{layer}" if layer.isdigit() else layer.upper() for layer in layers]


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
    guidance_context = any(
        term in normalized
        for term in (
            "investigation steps",
            "evidence required",
            "required evidence",
            "analyst checklist",
            "review-only spl",
            "review only spl",
            "dns beaconing",
            "beaconing candidate",
        )
    )
    if (
        any(keyword in normalized for keyword in _MITRE_KEYWORDS)
        and not any(marker in normalized for marker in _ALERT_CONTEXT_MARKERS)
        and len(normalized) <= 160
        and not guidance_context
    ):
        flags.append("mitre_mapping_requires_alert_context")
    return flags


def _clarification_question(flags: list[str]) -> str | None:
    if "mitre_mapping_requires_alert_context" in flags:
        return "Share the alert title, detection rule, notable/event ID, or SPL with sample fields before MITRE mapping."
    if "question_registry_use_case_skill_conflict" in flags:
        return "This query matches known registry entries with different skill hints. Confirm whether you want investigation, SPL, SOP, summary, or action planning."
    return None


def _mapped_primary_skill(primary_use_case: object | None, registry_entry: dict | None) -> str:
    if registry_entry:
        for key in ("legacy_router_intent_hint", "proposed_primary_skill"):
            value = registry_entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if primary_use_case is not None:
        return str(getattr(primary_use_case, "primary_skill", None) or "unknown")
    return "unknown"


def _registry_str(registry_entry: dict | None, key: str) -> str | None:
    if not registry_entry:
        return None
    value = registry_entry.get(key)
    return value if isinstance(value, str) and value else None


def _registry_int(registry_entry: dict | None, key: str) -> int | None:
    if not registry_entry:
        return None
    value = registry_entry.get(key)
    return value if isinstance(value, int) else None


def _registry_score(registry_entry: dict | None) -> float | None:
    if not registry_entry:
        return None
    value = registry_entry.get("_near_match_score")
    if value is None:
        value = registry_entry.get("_semantic_match_score")
    return float(value) if isinstance(value, float | int) else None


def _question_registry_match_source(
    exact_question_registry_entry: dict | None,
    near_question_registry_entry: dict | None,
    semantic_question_registry_entry: dict | None = None,
) -> str | None:
    if exact_question_registry_entry:
        return "question_runtime_map_105_exact"
    if near_question_registry_entry:
        return "question_runtime_map_105_near_token"
    if semantic_question_registry_entry:
        return "question_runtime_map_105_semantic"
    return None


def _deterministic_match_path(
    *,
    exact_question_registry_entry: dict | None,
    near_question_registry_entry: dict | None,
    primary_use_case: object | None,
    semantic_question_registry_entry: dict | None = None,
) -> str:
    if exact_question_registry_entry and primary_use_case:
        return "exact_105_plus_use_case_catalog"
    if exact_question_registry_entry:
        return "exact_105_question"
    if primary_use_case:
        return "use_case_catalog"
    if near_question_registry_entry:
        return "near_105_question"
    if semantic_question_registry_entry:
        return "semantic_105_question"
    return "out_of_registry"


def _registry_consistency(primary_use_case: object | None, registry_entry: dict | None) -> str:
    if not primary_use_case or not registry_entry:
        return "not_evaluated"
    catalog_skill = str(getattr(primary_use_case, "primary_skill", "") or "")
    registry_skill = _registry_str(registry_entry, "legacy_router_intent_hint") or _registry_str(registry_entry, "proposed_primary_skill")
    if not registry_skill:
        return "not_evaluated"
    return "consistent" if catalog_skill == registry_skill else "conflict"


def _registry_warnings(primary_use_case: object | None, registry_entry: dict | None) -> list[str]:
    if _registry_consistency(primary_use_case, registry_entry) == "conflict":
        return ["question_registry_use_case_skill_conflict"]
    return []


def _llm_advisory_recommended(
    deterministic_match_path: str,
    registry_warnings: list[str],
    *,
    catalog_row: dict | None = None,
) -> bool:
    return llm_advisory_recommended(
        deterministic_match_path,
        catalog_row=catalog_row,
        registry_warnings=registry_warnings,
    )
