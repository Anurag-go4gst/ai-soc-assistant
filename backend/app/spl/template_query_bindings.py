"""Query-aware adjustments for governed raw-search SPL templates."""

from __future__ import annotations

import re

from app.spl.spl_slot_binding_validator import (
    SlotValidationOutcome,
    escape_spl_quoted_string,
    validate_template_query_slots,
)

_ALERT_ID_RE = re.compile(
    r"\b(?:alert_id|alert|alt)[\s:=]+([A-Za-z0-9][\w.-]*)",
    re.IGNORECASE,
)
_TIME_BOUNDS_RE = re.compile(r"\bearliest=[^\s|]+(?:\s+latest=[^\s|]+)?")


def customize_template_spl(
    template_id: str,
    spl_text: str,
    user_query: str,
    *,
    normalized_slots: dict[str, str] | None = None,
) -> str:
    if template_id == "auth_success_after_failure":
        slots = normalized_slots
        if slots is None:
            outcome = validate_template_query_slots(template_id, user_query)
            if not outcome.valid:
                return spl_text
            slots = outcome.normalized_slots
        return _auth_success_after_failure_spl(spl_text, user_query, slots)
    return spl_text


def validate_template_slots_for_render(
    template_id: str,
    user_query: str,
    *,
    extra_slots: dict[str, object] | None = None,
    slot_source: str = "user",
) -> SlotValidationOutcome:
    return validate_template_query_slots(
        template_id,
        user_query,
        extra_slots=extra_slots,
        slot_source=slot_source,
    )


def _auth_success_after_failure_spl(
    base_spl: str,
    user_query: str,
    normalized_slots: dict[str, str],
) -> str:
    alert_id = normalized_slots.get("alert_id") or _extract_alert_id(user_query)
    host = normalized_slots.get("host")
    time_bounds = normalized_slots.get("time_window") or _extract_time_bounds(base_spl) or "earliest=-60m latest=now"

    search_prefix = "search index=pgcil_soc sourcetype=pgcil:auth"
    if alert_id:
        safe_alert = escape_spl_quoted_string(alert_id) if alert_id not in normalized_slots else alert_id
        search_prefix = f'{search_prefix} alert_id="{safe_alert}"'
    if host:
        search_prefix = f'{search_prefix} host="{host}"'
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
