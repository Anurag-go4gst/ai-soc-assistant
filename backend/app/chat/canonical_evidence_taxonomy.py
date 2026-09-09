"""One canonical SOC evidence taxonomy, and semantic sourcing of evidence legs.

Why this module exists
----------------------
Evidence legs for an out-of-registry (T4) investigation used to be reconstructed
by matching domain keywords against the *whole* query — which, after T4, is the
normalized goal. A normalized goal contains both what the analyst **reported**
("an archive file was created locally") and what they **asked the system to do**
("correlate endpoint, DNS/proxy, and network evidence"). Matching over both meant:

* the instruction clause manufactured legs for domains no reported event needed, and
* reported events whose telemetry domain the analyst never named were dropped.

That is semantic destruction *after* the LLM already understood the question
correctly. This module restores the intended authority flow:

    original query -> T4 SemanticT4Proposal -> deterministic normalization
    -> canonical evidence requirements -> existing EvidencePlan -> Resource Planner

T4 stays advisory: it proposes meaning, and everything here is deterministic
validation that maps that meaning onto a **closed** category vocabulary. A
semantic requirement that matches no canonical category is reported as
unsupported rather than becoming an invented tool or capability. Nothing here
grants MCP execution, SourceEvidence admission, RBAC, HIL, or write authority.

The vocabulary is deliberately the same one the known (T1-T3) path already uses,
extended with general SOC evidence categories. There is no second evidence
schema and no second planner: the composition returned here has exactly the
shape ``compose_multi_leg_evidence`` returns.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

#: Origins, most authoritative first. Only observation-backed origins may state a
#: compound "same activity chain" hypothesis: an analyst asking us to *check* a
#: domain is not a report that something happened in it.
ORIGIN_SEMANTIC = "semantic_requirement"
ORIGIN_OBSERVATION = "reported_observation"
ORIGIN_GOVERNED = "governed_contract"
ORIGIN_HYPOTHESIS = "semantic_hypothesis"
ORIGIN_REQUESTED = "analyst_requested"

#: Origins that represent something the analyst actually reported (or a governed
#: contract for this ask). Only these may be stated as one activity chain.
#: A competing hypothesis is a possibility, so it earns an evidence question but
#: is deliberately NOT observation-backed: "lateral movement" proposed as a
#: hypothesis must not become "the access to the second host event" in a chain
#: claim when no second host was ever reported.
_OBSERVATION_BACKED = (ORIGIN_SEMANTIC, ORIGIN_OBSERVATION, ORIGIN_GOVERNED)

#: Imperative verbs — general request vocabulary, not scenario wording. One source
#: of truth for "is this clause the analyst instructing the system?".
_IMPERATIVE_VERBS = (
    r"do\s+not|don'?t|never|avoid|investigate|check|correlate|tell|determine|distinguish|recommend|analy[sz]e|review|show|find|hunt|assess|evaluate|verify|confirm|explain|summari[sz]e|identify|list|report|provide|give|help|look|search|query|examine|inspect|compare|trace|map|escalate|advise|suggest|propose|outline|describe"
)

#: A clause that begins with an imperative is the analyst instructing the system,
#: not reporting an event.
_INSTRUCTION_LEAD_RE = re.compile(
    r"^(?:and\s+|then\s+|also\s+|please\s+|finally\s+|next\s+|now\s+)*"
    r"(?:" + _IMPERATIVE_VERBS + r")\b",
    re.IGNORECASE,
)

#: The leading imperative verb phrase of an instruction clause. Stripping it
#: exposes any event the analyst *reported inside* the instruction — "investigate
#: whether a newly created scheduled task is suspicious" reports a scheduled task.
_INSTRUCTION_HEAD_RE = re.compile(
    r"^(?:and\s+|then\s+|also\s+|please\s+|finally\s+|next\s+|now\s+)*"
    r"(?:" + _IMPERATIVE_VERBS + r")\b[^,.;]{0,24}?\b(?:me|whether|if|that|for)?\b",
    re.IGNORECASE,
)

#: An enumeration of telemetry domains headed by a source noun — "endpoint,
#: DNS/proxy, and network evidence". This is the analyst naming *where to look*,
#: never a report that something happened there. Removed from the whole text
#: before clause splitting, so an enumeration spanning a comma is not torn in half.
_EVIDENCE_REQUEST_SPAN_RE = re.compile(
    r"(?:[\w/&.-]+\s*[,/]?\s*(?:and\s+|or\s+)?){1,6}"
    r"(?:evidence|logs?|telemetry|records?|sources?|context|activity)\b",
    re.IGNORECASE,
)

#: The canonical evidence categories. ``id`` is shared with the known-path domain
#: vocabulary so both paths normalize into one EvidencePlan. Patterns are general
#: SOC telemetry vocabulary; they are matched against **reported observations and
#: T4's structured semantic output**, never against instruction wording alone.
_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str], tuple[str, ...]], ...] = (
    ("phishing", re.compile(r"\b(phish(?:ing|ed)?|clicked (?:a )?link|malicious (?:email|attachment))\b", re.I), ("user", "host", "url", "message_id", "_time")),
    ("vpn_auth", re.compile(r"\b(vpn|remote access|remote (?:log|sign)[- ]?(?:in|on)|remotely (?:accessed|logged))\b", re.I), ("user", "src_ip", "action", "session_id", "_time")),
    ("ot_jump_host", re.compile(r"\b(jump[- ]?host|rdp)\b", re.I), ("user", "src_ip", "dest_host", "session_id", "_time")),
    ("relay_change", re.compile(r"\b(relay|ied)\b.{0,48}\b(config|firmware|change|push)\b|\b(config|firmware)\b.{0,48}\b(relay|ied)\b", re.I), ("user", "asset", "change_id", "firmware_hash", "_time")),
    ("firewall_network", re.compile(r"\b(firewall|network sessions?|network connections?|network activity|outbound connections?|connections? (?:attempts?|sequences?)|(?:denied|blocked|allowed|permitted|dropped) .{0,24}connections?|traffic)\b", re.I), ("src_ip", "dest_ip", "dest_port", "action", "_time")),
    ("auth_failure", re.compile(r"\b(fail(?:ed|ure)s? (?:login|logon|auth\w*|sign[- ]?in|attempts?)|authentication failures?|unsuccessful (?:login|sign[- ]?in))\b", re.I), ("user", "src_ip", "host", "action", "_time")),
    ("auth_success", re.compile(r"\b(success(?:ful|fully)? (?:login|logon|auth\w*|sign(?:ed)?[- ]?in)|logged (?:in|into)|signed in|then succeeded|success after)\b", re.I), ("user", "src_ip", "host", "action", "_time")),
    ("post_login_activity", re.compile(r"\b(?:after the successful login|post[- ]login|subsequent (?:account |sign-?in )?activity|suspicious activity after|shortly afterward|subsequent activity)\b", re.I), ("user", "src_ip", "host", "_time")),
    ("endpoint_process", re.compile(r"\b(endpoint|process execution|process (?:creation|was observed|lineage)|new process|launched|spawned|command[- ]line|powershell|cmd\.exe|edr)\b", re.I), ("user", "host", "process_name", "process_hash", "_time")),
    ("dns", re.compile(r"\b(dns|proxy|external domain|domain (?:resolution|lookup|reputation)|resolved (?:a )?domain)\b", re.I), ("src_ip", "host", "query", "answer", "_time")),
    ("egress", re.compile(r"\b(exfil\w*|data staging|staged data|outbound (?:transfer|data|volume|traffic)|data transfer|transferr?ed .{0,40}\bdata\b|upload(?:ed|s)?|bytes[_ ]out|data volumes?|data transfers?)\b", re.I), ("user", "src_ip", "dest_ip", "bytes_out", "_time")),
    # General SOC evidence domains the known path already reasons about in prose
    # but had no category for, so a reported event in one of them was dropped.
    ("file_activity", re.compile(r"\b(archive|zip|rar|7z|tarball|compress(?:ed|ion)?|file (?:creation|created|write|written|staged|added)|created .{0,24}file)\b", re.I), ("user", "host", "file_name", "file_path", "_time")),
    ("scheduled_task", re.compile(r"\b(scheduled task|schtasks|cron(?:job|tab)?|at\.exe|autorun|run key|startup (?:item|entry)|new service|service creation|persistence)\b", re.I), ("user", "host", "task_name", "task_command", "_time")),
    ("lateral_access", re.compile(r"\b(lateral movement|another (?:internal )?(?:server|host|system|machine|workstation)|second (?:host|server)|pivot(?:ed|ing)?|moved (?:to|onto) )\b", re.I), ("user", "src_host", "dest_host", "logon_type", "_time")),
)

_CATEGORY_IDS = tuple(rule[0] for rule in _CATEGORY_RULES)
_FIELDS_BY_CATEGORY = {rule[0]: rule[2] for rule in _CATEGORY_RULES}

#: Sentence/clause boundaries. Clauses are split on sentence punctuation and on
#: ", and"-style coordination so a single sentence carrying both a report and an
#: instruction ("X happened, and tell me whether Y") is classified per half.
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<=[.!?;])\s+|\s*;\s*"
    r"|\s*,\s+(?=(?:and\s+|then\s+|but\s+)?(?:" + _IMPERATIVE_VERBS + r")\b)",
    re.IGNORECASE,
)

#: The leading imperative verb phrase of an instruction clause. Stripping it
#: exposes any event the analyst *reported inside* the instruction — "investigate
#: whether a newly created scheduled task is suspicious" reports a scheduled task.
_INSTRUCTION_HEAD_RE = re.compile(
    r"^(?:and\s+|then\s+|also\s+|please\s+|finally\s+|next\s+|now\s+)*"
    r"(?:do\s+not|don'?t|never|avoid|investigate|check|correlate|tell|determine"
    r"|distinguish|recommend|analy[sz]e|review|show|find|hunt|assess|evaluate|verify"
    r"|confirm|explain|summari[sz]e|identify|list|report|provide|give|help|look"
    r"|search|query|examine|inspect|compare|trace|map|escalate|advise|suggest"
    r"|propose|outline|describe)\b[^,.;]{0,24}?\b(?:me|whether|if|that|for)?\b",
    re.IGNORECASE,
)

#: An enumeration of telemetry domains headed by a source noun — "endpoint,
#: DNS/proxy, and network evidence". This is the analyst naming *where to look*,
#: never a report that something happened there, so it is removed before an
#: instruction clause is re-scanned for embedded reports.
_EVIDENCE_REQUEST_SPAN_RE = re.compile(
    r"(?:[\w/&.-]+\s*[,/]?\s*(?:and\s+|or\s+)?){1,6}"
    r"(?:evidence|logs?|telemetry|records?|sources?|context|activity)\b",
    re.IGNORECASE,
)


def _embedded_report_text(clause: str) -> str:
    """An instruction clause with its imperative head removed.

    Evidence-request enumerations are already stripped from the whole text before
    clause splitting, so what remains here is genuine reported content.
    """
    return _INSTRUCTION_HEAD_RE.sub(" ", clause, count=1)


def split_reported_observations(text: str) -> tuple[list[str], list[str]]:
    """Split text into (reported observations, analyst instructions).

    An imperative clause is the analyst telling the system what to do. Everything
    else is treated as a report of something that happened.
    """
    observations: list[str] = []
    instructions: list[str] = []
    for raw in _CLAUSE_SPLIT_RE.split(text or ""):
        clause = raw.strip(" \t\n,;")
        if not clause:
            continue
        if _INSTRUCTION_LEAD_RE.match(clause):
            instructions.append(clause)
        else:
            observations.append(clause)
    return observations, instructions


def categories_in_text(text: str) -> list[str]:
    """Canonical categories evidenced by ``text``, in canonical order."""
    if not text:
        return []
    return [cid for cid, pattern, _ in _CATEGORY_RULES if pattern.search(text)]


def _add(
    into: dict[str, str],
    categories: Iterable[str],
    origin: str,
) -> None:
    """Record ``origin`` for each category, keeping the most authoritative one."""
    order = {
        ORIGIN_SEMANTIC: 0,
        ORIGIN_OBSERVATION: 1,
        ORIGIN_GOVERNED: 2,
        ORIGIN_HYPOTHESIS: 3,
        ORIGIN_REQUESTED: 4,
    }
    for category in categories:
        current = into.get(category)
        if current is None or order[origin] < order[current]:
            into[category] = origin


def unsupported_semantic_requirements(requirements: Iterable[str]) -> list[str]:
    """Semantic requirements that map to no canonical category.

    Surfaced honestly as unsupported rather than invented as a tool or capability.
    """
    unsupported: list[str] = []
    for requirement in requirements or []:
        text = str(requirement or "").strip()
        if text and not categories_in_text(text):
            unsupported.append(text)
    return unsupported


def build_semantic_evidence_composition(
    *,
    raw_query: str,
    normalized_goal: str | None,
    semantic_evidence_requirements: Iterable[str] | None,
    semantic_hypotheses: Iterable[str] | None,
    governed_categories: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    """Compose evidence legs from structured semantics, not instruction wording.

    Precedence, highest first:

    1. accepted structured semantic evidence requirements / competing hypotheses
    2. canonical explicit event facts (the reported-observation clauses)
    3. an existing governed evidence contract for this ask
    4. analyst-requested investigation domains, additive hints only

    Returns ``None`` when fewer than two legs are observation-backed, matching the
    existing compound-investigation threshold. Analyst-requested legs never make a
    composition compound on their own: asking to check a domain is not a report.
    """
    origins: dict[str, str] = {}

    requirement_text = " . ".join(
        str(item).strip() for item in (semantic_evidence_requirements or []) if str(item or "").strip()
    )
    _add(origins, categories_in_text(requirement_text), ORIGIN_SEMANTIC)

    hypothesis_text = " . ".join(
        str(item).strip() for item in (semantic_hypotheses or []) if str(item or "").strip()
    )
    _add(origins, categories_in_text(hypothesis_text), ORIGIN_HYPOTHESIS)

    # Reported observations from BOTH the analyst's own words and the normalized
    # goal: T4 may phrase an event the raw query stated differently, and the raw
    # query holds detail the goal compressed away. Instruction clauses from either
    # source are held back as requested-only hints.
    observation_clauses: list[str] = []
    instruction_clauses: list[str] = []
    requested_spans: list[str] = []
    for source in (raw_query, normalized_goal):
        if not source:
            continue
        text = str(source)
        # Pull the "where to look" enumerations out first so a comma inside one
        # cannot split it across an instruction/observation boundary.
        requested_spans.extend(m.group(0) for m in _EVIDENCE_REQUEST_SPAN_RE.finditer(text))
        observed, instructed = split_reported_observations(
            _EVIDENCE_REQUEST_SPAN_RE.sub(" ", text)
        )
        observation_clauses.extend(observed)
        instruction_clauses.extend(instructed)

    _add(origins, categories_in_text(" . ".join(observation_clauses)), ORIGIN_OBSERVATION)
    # An event reported inside an instruction ("investigate whether a newly created
    # scheduled task is suspicious") is still a reported event.
    _add(
        origins,
        categories_in_text(" . ".join(_embedded_report_text(c) for c in instruction_clauses)),
        ORIGIN_OBSERVATION,
    )
    _add(origins, [str(c) for c in (governed_categories or []) if c in _CATEGORY_IDS], ORIGIN_GOVERNED)
    _add(
        origins,
        categories_in_text(" . ".join([*instruction_clauses, *requested_spans])),
        ORIGIN_REQUESTED,
    )

    backed = [cid for cid in _CATEGORY_IDS if origins.get(cid) in _OBSERVATION_BACKED]
    # At least one leg must be observation-backed, so instruction wording is never
    # the sole source of investigation semantics; requested domains may then be
    # correlated against it as additive hints.
    if not backed or len(origins) < 2:
        return None

    ordered = [cid for cid in _CATEGORY_IDS if cid in origins]
    legs = [
        {
            "domain": cid,
            "entity": entity_for_category(cid),
            "fields": list(_FIELDS_BY_CATEGORY[cid]),
            "origin": origins[cid],
        }
        for cid in ordered
    ]
    join_key, window = _correlation_for(backed, legs)
    return {
        "evidence_legs": legs,
        "correlation": {
            "join_key": join_key,
            "window": window,
            "honesty": (
                "Temporal correlation is not proof of causation; validate identity, "
                "asset, and change provenance."
            ),
        },
        "observation_backed_domains": backed,
    }


def entity_for_category(category: str) -> str:
    if category in {"firewall_network", "dns"}:
        return "src_ip/host"
    if category == "relay_change":
        return "asset/user"
    if category == "lateral_access":
        return "user/src_host/dest_host"
    return "user/host"


def _correlation_for(backed: list[str], legs: list[dict[str, Any]]) -> tuple[str, str]:
    domains = set(backed)
    if {"auth_failure", "auth_success"} <= domains:
        return "user,src_ip,host", "30m"
    if "relay_change" in domains:
        return "user", "4h"
    if "egress" in domains:
        return "user,host", "24h"
    backed_legs = [leg for leg in legs if leg["domain"] in domains]
    return (_shared_fields(backed_legs) or "user"), "8h"


def _shared_fields(legs: list[dict[str, Any]]) -> str:
    if not legs:
        return ""
    field_sets = [
        {str(f) for f in (leg.get("fields") or []) if str(f) != "_time"} for leg in legs
    ]
    if any(not s for s in field_sets):
        return ""
    shared = set.intersection(*field_sets)
    if not shared:
        return ""
    return ",".join(
        str(f) for f in (legs[0].get("fields") or []) if str(f) in shared and str(f) != "_time"
    )
