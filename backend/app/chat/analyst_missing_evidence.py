"""Project internal evidence/control state onto analyst-safe missing-evidence language.

Internal keys such as ``rag``, ``spl``, ``mcp`` and ``collected_source_evidence``
are legitimate control state — the planner and the execution gate need them — but
they are implementation plumbing, not evidence an analyst can go and fetch.
Leaking them into the analyst surface produced lines like "Missing governed
evidence: mcp", which tells a responder nothing and buries the gaps that matter.

This is a projection at the display boundary, not a second evidence schema: it
neither adds nor removes internal requirements, it only decides what the analyst
is shown and in what words.

Two rules it must not break:

* real gaps stay visible. Absent authentication, process or network evidence is
  reported, never swallowed, so a blocked investigation can never read as complete.
* an internal key becomes visible only when a governed contract genuinely makes it
  an analyst-relevant requirement (the user asked for an SPL artifact; the ask
  itself is a knowledge/guidance question).
"""

from __future__ import annotations

from typing import Any, Iterable

#: Pure control/plumbing state. Never analyst-facing on its own.
_CONTROL_KEYS = frozenset(
    {
        "mcp",
        "collected_source_evidence",
        "approved_sop_guidance",
        "source_evidence",
        "evidence",
    }
)

#: Control keys that become analyst-relevant only under a governed contract.
_RAG_KEYS = frozenset({"rag", "rag:sop", "rag:playbook", "soc_kb", "knowledge"})
_SPL_KEYS = frozenset({"spl", "spl_artifact", "candidate_spl"})

#: Canonical evidence category -> the analyst-facing concept. Distinct analytic
#: meanings stay distinct: an authentication *event* is not identity *context* and
#: neither is an authorization/privilege change.
_ANALYST_CONCEPT: dict[str, str] = {
    "auth": "authentication evidence",
    "authentication": "authentication evidence",
    "auth_failure": "authentication evidence",
    "auth_success": "authentication evidence",
    "authentication logs": "authentication evidence",
    "authentication telemetry": "authentication evidence",
    "identity": "identity context",
    "identity_context": "identity context",
    "privilege": "authorization / privilege-change evidence",
    "authorization": "authorization / privilege-change evidence",
    "endpoint": "process and endpoint evidence",
    "process": "process and endpoint evidence",
    "process_execution": "process and endpoint evidence",
    "endpoint activity logs": "process and endpoint evidence",
    "network": "network connection records",
    "network_flows": "network connection records",
    "firewall_sessions": "network connection records",
    "network connection logs": "network connection records",
    "dns": "DNS / proxy resolution records",
    "egress_flows": "outbound transfer volume",
    "egress": "outbound transfer volume",
    "file_activity": "archive / file activity",
    "persistence": "scheduled-task and persistence details",
    "scheduled_task": "scheduled-task and persistence details",
    "lateral_access": "second-host access evidence",
    "lateral_movement": "second-host access evidence",
    "correlation": "host / user / time correlation",
    "asset_context": "asset ownership and criticality context",
    "change_records": "recent change records",
}

#: Shown when the read source itself is the blocker, instead of "missing mcp".
SOURCE_UNAVAILABLE_LIMITATION = (
    "The governed read source is unavailable or disabled, so no environment "
    "telemetry could be collected for this investigation."
)


def _normalize(item: Any) -> str:
    return str(item or "").strip().lower()


#: Free-text checklist items ("DNS/proxy logs", "authentication events for the
#: account") describe the same canonical requirements as the category keys. Match
#: on domain vocabulary so one requirement is not shown twice in two phrasings.
_CONCEPT_MARKERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("authentication", "auth event", "login", "logon", "sign-in", "credential"), "authentication evidence"),
    (("identity", "account details", "group membership"), "identity context"),
    (("privilege", "authorization"), "authorization / privilege-change evidence"),
    (("scheduled task", "task creation", "persistence", "autorun", "service creation"), "scheduled-task and persistence details"),
    (("archive", "file activity", "file creation"), "archive / file activity"),
    (("outbound transfer", "egress", "exfil", "data volume", "bytes"), "outbound transfer volume"),
    (("dns", "proxy", "domain resolution"), "DNS / proxy resolution records"),
    (("lateral", "second host", "destination host"), "second-host access evidence"),
    (("firewall", "connection", "network flow", "network session", "network", "traffic"), "network connection records"),
    (("process", "endpoint", "edr", "command line", "lineage"), "process and endpoint evidence"),
    (("correlat",), "host / user / time correlation"),
    (("asset", "criticality", "ownership"), "asset ownership and criticality context"),
)


def _concept_for(key: str, original: str) -> str:
    mapped = _ANALYST_CONCEPT.get(key)
    if mapped:
        return mapped
    # The marker fallback exists for natural-language checklist items ("DNS/proxy
    # logs"). A snake_case key that is not a known category is a FIELD-level
    # requirement -- parent_process, command_line -- which is already specific and
    # analyst-readable. Collapsing those into a coarse concept would destroy real
    # analytic detail, so they pass through untouched.
    if " " not in key and "/" not in key:
        return original.strip()
    for markers, concept in _CONCEPT_MARKERS:
        if any(marker in key for marker in markers):
            return concept
    return original.strip()


def project_missing_evidence(
    missing: Iterable[Any],
    *,
    spl_requested: bool = False,
    knowledge_contract_required: bool = False,
) -> tuple[list[str], bool]:
    """Return (analyst-facing missing evidence, source_unavailable).

    ``source_unavailable`` is true when a pure execution/collection key was the
    only thing standing in for "we could not read the environment" — the caller
    turns that into a source limitation rather than a fake evidence gap.
    """
    concepts: list[str] = []
    source_unavailable = False

    for raw in missing or []:
        key = _normalize(raw)
        if not key:
            continue
        if key in _CONTROL_KEYS or key.startswith("mcp:"):
            source_unavailable = True
            continue
        if key in _RAG_KEYS or key.startswith("rag:"):
            if knowledge_contract_required:
                _append(concepts, "approved knowledge / SOP guidance")
            continue
        if key in _SPL_KEYS:
            if spl_requested:
                _append(concepts, "a validated SPL artifact")
            continue
        _append(concepts, _concept_for(key, str(raw)))

    return concepts, source_unavailable


def _append(items: list[str], value: str) -> None:
    """Add a concept once. Canonical normalization, not string de-duplication:
    ``auth``/``authentication``/``authentication logs`` are one requirement."""
    text = (value or "").strip()
    if not text:
        return
    if any(existing.lower() == text.lower() for existing in items):
        return
    items.append(text)


def analyst_limitations(
    concepts: Iterable[str],
    *,
    source_unavailable: bool,
) -> list[str]:
    """Limitation lines for the analyst surface, in analyst language."""
    lines = [f"Not collected: {concept}." for concept in concepts]
    if source_unavailable:
        lines.append(SOURCE_UNAVAILABLE_LIMITATION)
    return lines
