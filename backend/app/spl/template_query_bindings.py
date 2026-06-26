"""Query-aware adjustments for governed raw-search SPL templates."""

from __future__ import annotations

import re
from typing import Any

from app.spl.spl_slot_binding_validator import (
    SlotValidationOutcome,
    escape_spl_quoted_string,
    validate_template_query_slots,
)
from app.spl.template_slot_bindings import customize_template_spl_with_bindings, render_spl_with_bindings
from app.spl.user_constraint_bindings import UserConstraintBindings, build_user_constraint_bindings

_TIME_BOUNDS_RE = re.compile(r"\bearliest=[^\s|]+(?:\s+latest=[^\s|]+)?")
_ALERT_ID_RE = re.compile(
    r"\b(?:alert_id|alert|alt)[\s:=]+([A-Za-z0-9][\w.-]*)",
    re.IGNORECASE,
)


def customize_template_spl(
    template_id: str,
    spl_text: str,
    user_query: str,
    *,
    normalized_slots: dict[str, str] | None = None,
    user_constraint_bindings: UserConstraintBindings | None = None,
) -> str:
    bindings = user_constraint_bindings or build_user_constraint_bindings(user_query)
    slots = normalized_slots or bindings.normalized_slots
    outcome = customize_template_spl_with_bindings(
        template_id,
        spl_text,
        bindings,
        normalized_slots=slots,
    )
    return outcome.spl


def customize_template_spl_with_trace(
    template_id: str,
    spl_text: str,
    user_query: str,
    *,
    normalized_slots: dict[str, str] | None = None,
    user_constraint_bindings: UserConstraintBindings | None = None,
    force_user_skeleton: bool = False,
) -> tuple[str, dict[str, Any]]:
    bindings = user_constraint_bindings or build_user_constraint_bindings(user_query)
    slots = normalized_slots or bindings.normalized_slots
    outcome = render_spl_with_bindings(
        template_id,
        spl_text,
        bindings,
        normalized_slots=slots,
        force_user_skeleton=force_user_skeleton,
    )
    trace = {
        "bound_slots": dict(outcome.bound_slots),
        "unbound_constraints": list(outcome.unbound_constraints),
        "used_user_bound_skeleton": outcome.used_user_bound_skeleton,
        "user_constraint_bindings": bindings.to_dict(),
    }
    return outcome.spl, trace


def _resolve_time_bounds(
    normalized_slots: dict[str, str] | None,
    template_id: str,
    user_query: str,
    spl_text: str,
) -> str | None:
    if normalized_slots and normalized_slots.get("time_window"):
        return normalized_slots["time_window"]
    outcome = validate_template_query_slots(template_id, user_query)
    if outcome.valid and outcome.normalized_slots.get("time_window"):
        return outcome.normalized_slots["time_window"]
    return _extract_time_bounds(spl_text)


def validate_template_slots_for_render(
    template_id: str,
    user_query: str,
    *,
    extra_slots: dict[str, object] | None = None,
    slot_source: str = "user",
    user_constraint_bindings: UserConstraintBindings | None = None,
) -> SlotValidationOutcome:
    bindings = user_constraint_bindings
    if bindings is None:
        bindings = build_user_constraint_bindings(
            user_query,
            extra_slots=extra_slots,
        )
    merged_slots = bindings_to_extra_slots(bindings)
    return validate_template_query_slots(
        template_id,
        user_query,
        extra_slots=merged_slots,
        slot_source=slot_source,
    )


def bindings_to_extra_slots(bindings: UserConstraintBindings) -> dict[str, Any]:
    from app.spl.user_constraint_bindings import bindings_to_extra_slots as _bindings_to_extra_slots

    return _bindings_to_extra_slots(bindings)


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
