"""Semantic relevance checks for rendered investigation plans.

This is a deterministic QA helper, not a second planner. It does not route,
authorize execution, or invent evidence. Catalogue/compound investigation
contracts must not be replaced by unrelated OT/network-beacon checklists.
"""

from __future__ import annotations

import re
from typing import Any

from app.chat.canonical_evidence_taxonomy import categories_in_text
from app.query_understanding.success_after_failure import detect_success_after_failure

#: Primary concepts that are unjustified on a success-after-failure authentication
#: investigation unless a later evidence step has already established a pivot.
UNJUSTIFIED_AUTH_PIVOT_MARKERS: tuple[str, ...] = (
    "network beacon",
    "ot inventory",
    "ot asset is beaconing",
    "firewall sessions:",
    "dns/proxy context",
    "dns/proxy",
    "vendor access",
    "substation",
    "data diode",
    "ot protocol logs",
    "shift roster",
)

_AUTH_ANCHOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authentication_failure", re.compile(r"\b(fail(?:ed|ure)|mfa|ssh|login|logon|sign[- ]?in|auth)\b", re.I)),
    ("authentication_success", re.compile(r"\b(success(?:ful)?|succeeded|sign[- ]?in)\b", re.I)),
    ("same_source", re.compile(r"\b(same source|source ip|src_ip|same (?:account|user|host)|source/account)\b", re.I)),
    ("account_user", re.compile(r"\b(account|user|identity|username)\b", re.I)),
    ("temporal_relationship", re.compile(r"\b(after|followed by|subsequent|then|sequence|window|temporal)\b", re.I)),
    ("post_login_activity", re.compile(r"\b(post[- ]login|subsequent account|account activity|after (?:the )?success|privilege|lateral|process)\b", re.I)),
)

_DOMAIN_EVIDENCE: dict[str, str] = {
    "auth_failure": (
        "Authentication failure events (including MFA/VPN/SSH) for the reported source, user, and window."
    ),
    "auth_success": (
        "Authentication success events after those failures for the same source/account."
    ),
    "post_login_activity": (
        "Post-success account and host activity: processes, privilege changes, lateral movement, or unusual network use."
    ),
    "endpoint_process": (
        "Endpoint/process execution telemetry for the reported host, including parent/child process and command line where available."
    ),
    "firewall_network": (
        "Firewall / network session telemetry for the same host and time window, correlated with the other reported signals."
    ),
    "dns": (
        "DNS query telemetry for the same host and time window: resolved names, answers, query frequency and periodicity."
    ),
    "egress": "Outbound transfer volume and destinations for the same host/user after the correlated events.",
    "file_activity": (
        "File and archive activity on the reported host: creation time, path, size, and the "
        "process and account that wrote it."
    ),
    "scheduled_task": (
        "Scheduled task / persistence mechanism creation on the reported host: task name, "
        "command or action, author account, and creation time."
    ),
    "lateral_access": (
        "Access from the reported source to the second host: account, logon type, source and "
        "destination host, and the process context on the destination."
    ),
}

_DOMAIN_CATEGORIES: dict[str, tuple[str, ...]] = {
    "auth_failure": ("auth", "identity"),
    "auth_success": ("auth", "identity"),
    "post_login_activity": ("endpoint", "auth"),
    "endpoint_process": ("endpoint", "process_execution"),
    "firewall_network": ("network_flows", "firewall_sessions"),
    "dns": ("dns",),
    "egress": ("egress_flows",),
    "vpn_auth": ("auth", "identity"),
    "file_activity": ("endpoint", "file_activity"),
    "scheduled_task": ("endpoint", "persistence"),
    "lateral_access": ("auth", "endpoint", "identity"),
}


#: Surface markers that identify which evidence DOMAIN a plan item is about.
#: Symmetric by design: the repo already refused network/OT pivots on an
#: authentication investigation, but nothing refused authentication pivots on a
#: network investigation, so a case-blind proposal could add an auth checklist to
#: a DNS/firewall hunt. Markers are domain vocabulary, not per-query keywords.
_DOMAIN_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "auth",
        (
            "authentication",
            "auth event",
            "login",
            "logon",
            "sign-in",
            "sign in",
            "credential",
            "mfa",
            "password",
            "lockout",
        ),
    ),
    ("identity", ("identity provider", "directory account", "privileged account")),
    (
        "endpoint",
        ("endpoint", "process execution", "parent process", "child process", "powershell", "edr"),
    ),
    ("dns", ("dns", "resolved name", "domain resolution")),
    (
        "firewall_sessions",
        ("firewall", "network session", "session log", "denied connection", "rule name"),
    ),
    ("network_flows", ("network flow", "netflow", "traffic volume", "peer flow")),
    ("egress_flows", ("exfiltration", "outbound transfer", "bytes_out", "data egress")),
    ("email", ("phishing", "email message", "mail gateway")),
)

#: Categories that never identify a domain on their own.
_NEUTRAL_CATEGORIES = frozenset({"asset_context", "change_records"})


def categories_for_evidence_needed(evidence_needed: list[str]) -> list[str]:
    """Map required-evidence prose onto the existing data_category vocabulary.

    This is downstream parity, not a second taxonomy. Canonical category IDs from
    ``categories_in_text`` are projected through ``categories_for_domains``. Phrases
    the closed taxonomy does not yet name (network source history, change-window
    context) map onto the existing ``network_flows`` / ``change_records`` labels
    already used by InvestigationPlan.
    """
    joined = " . ".join(str(item) for item in evidence_needed if str(item).strip())
    categories = list(categories_for_domains(categories_in_text(joined)))
    lowered = joined.lower()
    if any(
        term in lowered
        for term in (
            "network source",
            "source history",
            "connection history",
            "network history",
        )
    ):
        for item in ("network_flows", "firewall_sessions"):
            if item not in categories:
                categories.append(item)
    if any(
        term in lowered
        for term in (
            "change-window",
            "change window",
            "change history",
            "change records",
            "approved change",
            "recent change",
        )
    ):
        if "change_records" not in categories:
            categories.append("change_records")
    return categories


def _domains_in_text(text: str) -> set[str]:
    lowered = " ".join((text or "").lower().split())
    return {
        domain
        for domain, markers in _DOMAIN_MARKERS
        if any(marker in lowered for marker in markers)
    }


def plan_domain_scope(data_categories: list[str] | tuple[str, ...]) -> set[str]:
    """Domains the committed plan is actually about, from its data categories."""
    scope = {
        str(item).strip().lower()
        for item in data_categories
        if str(item).strip().lower() not in _NEUTRAL_CATEGORIES
    }
    # ``auth``/``identity`` and ``network_flows``/``firewall_sessions`` are
    # neighbours: an item about one must not be dropped because the plan named
    # the other.
    if scope & {"auth", "identity"}:
        scope |= {"auth", "identity"}
    if scope & {"network_flows", "firewall_sessions"}:
        scope |= {"network_flows", "firewall_sessions"}
    if scope & {"endpoint", "process_execution"}:
        scope |= {"endpoint", "process_execution"}
    return scope


def unjustified_domain_pivots(
    items: list[str],
    *,
    plan_domains: set[str],
) -> tuple[list[str], list[str]]:
    """Split proposal items into (kept, dropped-as-off-domain).

    An item that names no domain is kept: generic corroboration steps are not
    pivots. An item is dropped only when every domain it names sits outside the
    committed plan's scope — that is a *new primary* pivot the investigation has
    no justification for yet, not a refinement of one it already owns.
    """
    if not plan_domains:
        return list(items), []
    kept: list[str] = []
    dropped: list[str] = []
    for item in items:
        domains = _domains_in_text(item)
        if domains and not (domains & plan_domains):
            dropped.append(item)
            continue
        kept.append(item)
    return kept, dropped


def plan_text_blob(plan: Any) -> str:
    if plan is None:
        return ""
    if isinstance(plan, str):
        return plan
    payload = plan if isinstance(plan, dict) else getattr(plan, "model_dump", lambda **_: {})()
    if not isinstance(payload, dict):
        payload = {}
    parts: list[str] = [
        str(payload.get("investigation_objective") or ""),
        *[str(item) for item in (payload.get("hypotheses") or [])],
        *[str(item) for item in (payload.get("evidence_needed") or [])],
        *[str(item) for item in (payload.get("data_categories") or [])],
        *[str(item) for item in (payload.get("success_criteria") or [])],
    ]
    return "\n".join(parts)


def unjustified_primary_pivots(plan_text: str, *, query: str) -> list[str]:
    if not detect_success_after_failure(query):
        return []
    lowered = (plan_text or "").lower()
    return [marker for marker in UNJUSTIFIED_AUTH_PIVOT_MARKERS if marker in lowered]


def required_auth_anchors_present(plan_text: str) -> dict[str, bool]:
    text = plan_text or ""
    return {name: bool(pattern.search(text)) for name, pattern in _AUTH_ANCHOR_PATTERNS}


def filter_unjustified_auth_pivots(items: list[str], *, query: str) -> list[str]:
    if not detect_success_after_failure(query):
        return items
    filtered: list[str] = []
    for item in items:
        lowered = item.lower()
        if any(marker in lowered for marker in UNJUSTIFIED_AUTH_PIVOT_MARKERS):
            continue
        filtered.append(item)
    return filtered


def evidence_for_domains(domains: list[str] | set[str]) -> list[str]:
    items: list[str] = []
    for domain in domains:
        text = _DOMAIN_EVIDENCE.get(str(domain))
        if text and text not in items:
            items.append(text)
    return items


def categories_for_domains(domains: list[str] | set[str]) -> list[str]:
    categories: list[str] = []
    for domain in domains:
        for item in _DOMAIN_CATEGORIES.get(str(domain), ()):
            if item not in categories:
                categories.append(item)
    return categories
