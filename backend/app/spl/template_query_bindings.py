"""Query-aware adjustments for governed raw-search SPL templates."""

from __future__ import annotations

import re

_ALERT_ID_RE = re.compile(
    r"\b(?:alert_id|alert|alt)[\s:=]+([A-Za-z0-9][\w.-]*)",
    re.IGNORECASE,
)
_HOST_RE = re.compile(r"\bhost=([A-Za-z0-9_.:-]+)", re.IGNORECASE)
_TIME_BOUNDS_RE = re.compile(r"\bearliest=[^\s|]+(?:\s+latest=[^\s|]+)?")


def customize_template_spl(template_id: str, spl_text: str, user_query: str) -> str:
    if template_id == "auth_success_after_failure":
        return _auth_success_after_failure_spl(spl_text, user_query)
    return spl_text


def _auth_success_after_failure_spl(base_spl: str, user_query: str) -> str:
    alert_id = _extract_alert_id(user_query)
    host = _extract_explicit_host(user_query)
    time_bounds = _extract_time_bounds(base_spl) or "earliest=-60m latest=now"

    search_prefix = "search index=pgcil_soc sourcetype=pgcil:auth"
    if alert_id:
        search_prefix = f'{search_prefix} alert_id="{alert_id}"'
    if host:
        search_prefix = f"{search_prefix} host={host}"
    search_prefix = f"{search_prefix} {time_bounds}"

    remainder = re.sub(r"^search\s+index=pgcil_soc\s+sourcetype=pgcil:auth(?:\s+\S+)*?\s+", "", base_spl, count=1)
    remainder = re.sub(r"^earliest=[^\s|]+(?:\s+latest=[^\s|]+)?\s+", "", remainder, count=1)
    return f"{search_prefix} {remainder}".strip()


def _extract_time_bounds(spl_text: str) -> str | None:
    match = _TIME_BOUNDS_RE.search(spl_text)
    if not match:
        return None
    return match.group(0).strip()


def _extract_alert_id(query: str) -> str | None:
    match = _ALERT_ID_RE.search(query)
    if not match:
        return None
    return match.group(1).strip()


def _extract_explicit_host(query: str) -> str | None:
    match = _HOST_RE.search(query)
    if not match:
        return None
    return match.group(1).strip()
