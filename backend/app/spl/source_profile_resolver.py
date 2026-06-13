"""Static source-profile resolution (SPL audit Phase H0).

Maps placeholder stems (`auth_index`, `dns_sourcetype`, …) to configured
index/sourcetype values from explicit env JSON and `SPL_ALLOWED_*` policy.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.config import settings
from app.safeguards.spl_validator import load_spl_policy

_PLACEHOLDER_RE = re.compile(r"<([a-zA-Z0-9_]+)>")

_INDEX_STEMS = (
    "auth_index",
    "windows_index",
    "network_index",
    "dns_index",
    "endpoint_index",
    "firewall_index",
    "vpn_index",
    "sysmon_index",
    "notable_index",
    "monitored_index",
    "scada_firewall_index",
    "ot_firewall_index",
)

_SOURCETYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("auth_sourcetype", ("auth", "wineventlog", "win:auth")),
    ("windows_security_sourcetype", ("windows", "security", "wineventlog")),
    ("windows_security_or_system_sourcetype", ("windows", "security", "system")),
    ("network_traffic_sourcetype", ("traffic", "network", "flow", "conn")),
    ("dns_sourcetype", ("dns", "resolution")),
    ("endpoint_process_sourcetype", ("sysmon", "edr", "endpoint", "process")),
    ("firewall_sourcetype", ("firewall", "pan", "asa", "palo")),
    ("vpn_sourcetype", ("vpn",)),
    ("sysmon_sourcetype", ("sysmon",)),
    ("notable_or_risk_sourcetype", ("notable", "risk")),
    ("proxy_or_firewall_sourcetype", ("proxy", "firewall", "web")),
    ("internal_traffic_sourcetype", ("traffic", "network", "flow")),
)


def extract_placeholder_slots(spl: str) -> list[str]:
    return list(dict.fromkeys(_PLACEHOLDER_RE.findall(spl or "")))


def substitute_placeholders(spl: str, profile: dict[str, str]) -> tuple[str, list[str]]:
    missing: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = profile.get(key)
        if value:
            return value
        missing.append(key)
        return match.group(0)

    resolved = _PLACEHOLDER_RE.sub(_replace, spl or "")
    return resolved, list(dict.fromkeys(missing))


@lru_cache(maxsize=1)
def _explicit_profile_map() -> dict[str, str]:
    raw = (settings.ai_soc_source_profile_map or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if value}


def _stem_matches_index(stem: str, index_name: str) -> bool:
    stem_key = stem.replace("_index", "")
    lowered = index_name.lower()
    if stem_key in lowered:
        return True
    aliases = {
        "auth": ("auth", "winevent", "identity"),
        "windows": ("windows", "winevent", "win"),
        "network": ("network", "traffic", "flow", "conn"),
        "dns": ("dns", "resolution"),
        "endpoint": ("endpoint", "edr", "sysmon"),
        "firewall": ("firewall", "fw", "perimeter"),
        "vpn": ("vpn",),
        "sysmon": ("sysmon",),
        "notable": ("notable", "risk"),
        "monitored": ("monitored", "inventory"),
        "scada_firewall": ("scada", "ot", "ics"),
        "ot_firewall": ("ot", "ics", "scada"),
    }
    for token in aliases.get(stem_key, (stem_key,)):
        if token in lowered:
            return True
    return False


def _pick_sourcetype(sourcetypes: list[str], keywords: tuple[str, ...]) -> str | None:
    for sourcetype in sourcetypes:
        lowered = sourcetype.lower()
        if any(keyword in lowered for keyword in keywords):
            return sourcetype
    return sourcetypes[0] if sourcetypes else None


def build_policy_derived_profile() -> dict[str, str]:
    policy = load_spl_policy()
    indexes = list(policy.allowed_indexes)
    sourcetypes = list(policy.allowed_sourcetypes)
    profile: dict[str, str] = {}

    if len(indexes) == 1:
        for stem in _INDEX_STEMS:
            profile[stem] = indexes[0]
    else:
        for stem in _INDEX_STEMS:
            for index_name in indexes:
                if _stem_matches_index(stem, index_name):
                    profile[stem] = index_name
                    break

    for stem, keywords in _SOURCETYPE_RULES:
        picked = _pick_sourcetype(sourcetypes, keywords)
        if picked:
            profile.setdefault(stem, picked)

    return profile


def load_static_source_profile(*, session_slots: dict[str, str] | None = None) -> dict[str, str]:
    profile = build_policy_derived_profile()
    profile.update(_explicit_profile_map())
    if session_slots:
        profile.update({key: value for key, value in session_slots.items() if value})
    return profile


def resolve_static_slots(
    required_slots: list[str],
    *,
    session_slots: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    profile = load_static_source_profile(session_slots=session_slots)
    resolved = {slot: profile[slot] for slot in required_slots if slot in profile and profile[slot]}
    missing = [slot for slot in required_slots if slot not in resolved]
    return resolved, missing


def merge_profiles(*profiles: dict[str, str] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for profile in profiles:
        if not profile:
            continue
        merged.update({key: value for key, value in profile.items() if value})
    return merged
