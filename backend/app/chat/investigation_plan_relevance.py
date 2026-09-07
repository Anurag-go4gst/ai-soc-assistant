"""Semantic relevance checks for rendered investigation plans.

This is a deterministic QA helper, not a second planner. It does not route,
authorize execution, or invent evidence. Catalogue/compound investigation
contracts must not be replaced by unrelated OT/network-beacon checklists.
"""

from __future__ import annotations

import re
from typing import Any

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
        "Network session telemetry correlated to the same host/user/time window as the process or authentication events."
    ),
    "dns": "DNS query telemetry for the same host/time window, only if a prior evidence step justifies a name/reputation pivot.",
    "egress": "Outbound transfer volume and destinations for the same host/user after the correlated events.",
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
}


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
