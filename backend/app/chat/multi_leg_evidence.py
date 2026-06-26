"""Deterministic multi-domain evidence composition for T2 investigations (WS-4)."""

from __future__ import annotations

import re
from typing import Any


_DOMAIN_RULES: tuple[tuple[str, re.Pattern[str], tuple[str, ...]], ...] = (
    ("phishing", re.compile(r"\b(phish(?:ing|ed)?|clicked (?:a )?link|email (?:alert|event))\b", re.I), ("user", "host", "url", "message_id", "_time")),
    ("vpn_auth", re.compile(r"\b(vpn|remote access)\b", re.I), ("user", "src_ip", "action", "session_id", "_time")),
    ("ot_jump_host", re.compile(r"\b(jump[- ]?host|rdp)\b", re.I), ("user", "src_ip", "dest_host", "session_id", "_time")),
    ("relay_change", re.compile(r"\b(relay|ied)\b.{0,48}\b(config|firmware|change|push)\b|\b(config|firmware)\b.{0,48}\b(relay|ied)\b", re.I), ("user", "asset", "change_id", "firmware_hash", "_time")),
    ("firewall_network", re.compile(r"\b(firewall|network session|connection|traffic)\b", re.I), ("src_ip", "dest_ip", "dest_port", "action", "_time")),
    ("auth_failure", re.compile(r"\b(fail(?:ed|ure)? (?:login|auth)|authentication failures?)\b", re.I), ("user", "src_ip", "host", "action", "_time")),
    ("auth_success", re.compile(r"\b(success(?:ful)? (?:login|auth)|then succeeded|success after)\b", re.I), ("user", "src_ip", "host", "action", "_time")),
    ("endpoint_process", re.compile(r"\b(endpoint|process execution|powershell|edr)\b", re.I), ("user", "host", "process_name", "process_hash", "_time")),
    ("dns", re.compile(r"\b(dns|domain|query)\b", re.I), ("src_ip", "host", "query", "answer", "_time")),
    ("egress", re.compile(r"\b(exfil|outbound transfer|upload|bytes_out)\b", re.I), ("user", "src_ip", "dest_ip", "bytes_out", "_time")),
)


def compose_multi_leg_evidence(query: str) -> dict[str, Any] | None:
    """Return two-or-more evidence legs and a safe correlation hint.

    This is planning metadata only.  It neither generates executable SPL nor
    claims that temporal correlation proves causation.
    """
    legs: list[dict[str, Any]] = []
    for domain, pattern, fields in _DOMAIN_RULES:
        if pattern.search(query):
            legs.append({"domain": domain, "entity": _entity_for(domain), "fields": list(fields)})
    if len(legs) < 2:
        return None

    domains = {leg["domain"] for leg in legs}
    if domains == {"auth_failure", "auth_success"}:
        join_key = "user,src_ip,host"
        window = "30m"
    elif "relay_change" in domains:
        join_key = "user"
        window = "4h"
    elif "egress" in domains:
        join_key = "user,host"
        window = "24h"
    else:
        join_key = "user"
        window = "8h"
    return {
        "evidence_legs": legs,
        "correlation": {
            "join_key": join_key,
            "window": window,
            "honesty": "Temporal correlation is not proof of causation; validate identity, asset, and change provenance.",
        },
    }


def render_multi_leg_guidance(composition: dict[str, Any] | None) -> str:
    if not composition:
        return ""
    lines = ["Correlation evidence plan (review-only)"]
    for index, leg in enumerate(composition["evidence_legs"], start=1):
        fields = ", ".join(leg["fields"])
        lines.append(f"- Leg {index} — {leg['domain']}: collect {fields}.")
    correlation = composition["correlation"]
    lines.extend(
        [
            f"- Correlate on `{correlation['join_key']}` within `{correlation['window']}`; normalize identity and time first.",
            f"- Causality limit: {correlation['honesty']}",
        ]
    )
    return "\n".join(lines)


def _entity_for(domain: str) -> str:
    if domain in {"firewall_network", "dns"}:
        return "src_ip/host"
    if domain == "relay_change":
        return "asset/user"
    return "user/host"
