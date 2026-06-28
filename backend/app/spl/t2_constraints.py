"""Semantic constraint extraction and SPL coverage validation for T2 / binding paths."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.source_profile_bindings import build_source_profile_binding_slots

_OFF_SHIFT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:outside|after)\s+(?:normal\s+)?shift\s+hours?\b", re.I),
    re.compile(r"\boff[\s-]?shift\b", re.I),
    re.compile(r"\bafter[\s-]?hours\b", re.I),
    re.compile(r"\boutside\s+business\s+hours?\b", re.I),
    re.compile(r"\boutside\s+(?:normal\s+)?working\s+hours?\b", re.I),
)

_EXPLICIT_SHIFT_RANGE_RE = re.compile(
    r"\boutside\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
    re.I,
)

_EVENT_CODE_RE = re.compile(r"\bevent\s*(?:id|code)?\s*[:#=]?\s*(\d{3,5})\b", re.I)
_SUBNET_RE = re.compile(r"\bsubstation\s+subnet", re.I)


@dataclass
class SplConstraint:
    constraint_type: str
    value: Any
    status: str = "requested"  # requested | implemented | missing_config | not_implemented

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_type": self.constraint_type,
            "value": self.value,
            "status": self.status,
        }


@dataclass
class ConstraintExtractionResult:
    constraints: list[SplConstraint] = field(default_factory=list)
    missing_bindings: list[str] = field(default_factory=list)


def _hour_to_24(hour: int, ampm: str | None) -> int:
    if not ampm:
        return hour
    token = ampm.lower()
    if token == "pm" and hour < 12:
        return hour + 12
    if token == "am" and hour == 12:
        return 0
    return hour


def _shift_config_from_slots(shift_config: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not shift_config:
        return None, None
    start = shift_config.get("shift_start_hour", shift_config.get("normal_shift_start_hour"))
    end = shift_config.get("shift_end_hour", shift_config.get("normal_shift_end_hour"))
    try:
        start_i = int(start) if start is not None and str(start).strip() != "" else None
    except ValueError:
        start_i = None
    try:
        end_i = int(end) if end is not None and str(end).strip() != "" else None
    except ValueError:
        end_i = None
    return start_i, end_i


def query_requests_off_shift(query: str) -> bool:
    """True when the analyst asked for off-shift / after-hours filtering."""
    text = query or ""
    if _EXPLICIT_SHIFT_RANGE_RE.search(text):
        return True
    return any(pattern.search(text) for pattern in _OFF_SHIFT_PATTERNS)


def resolve_shift_config_for_query(
    query: str,
    *,
    source_profile_slots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve shift-hour config from caller slots or Environment KB (fill blanks only)."""
    slots = dict(source_profile_slots or {})
    if query_requests_off_shift(query) and (
        not slots.get("normal_shift_start_hour") or not slots.get("normal_shift_end_hour")
    ):
        profile_slots = build_source_profile_binding_slots(query).slots
        for key in ("normal_shift_start_hour", "normal_shift_end_hour"):
            if key not in slots and profile_slots.get(key):
                slots[key] = profile_slots[key]
    return {
        "shift_start_hour": slots.get("normal_shift_start_hour"),
        "shift_end_hour": slots.get("normal_shift_end_hour"),
    }


def extract_semantic_constraints(
    query: str,
    *,
    shift_config: dict[str, Any] | None = None,
) -> ConstraintExtractionResult:
    """Extract analyst-requested constraints beyond hard index/field tokens."""
    text = query or ""
    result = ConstraintExtractionResult()

    event = _EVENT_CODE_RE.search(text)
    if event:
        result.constraints.append(
            SplConstraint("event_code_filter", event.group(1), status="requested")
        )

    if _SUBNET_RE.search(text):
        result.constraints.append(
            SplConstraint("subnet_filter", "substation_subnet", status="requested")
        )

    explicit = _EXPLICIT_SHIFT_RANGE_RE.search(text)
    if explicit:
        start = _hour_to_24(int(explicit.group(1)), explicit.group(3))
        end = _hour_to_24(int(explicit.group(4)), explicit.group(6))
        result.constraints.append(
            SplConstraint(
                "off_shift_filter",
                {"shift_start_hour": start, "shift_end_hour": end},
                status="requested",
            )
        )
        return result

    if any(pattern.search(text) for pattern in _OFF_SHIFT_PATTERNS):
        start, end = _shift_config_from_slots(shift_config)
        if start is not None and end is not None:
            result.constraints.append(
                SplConstraint(
                    "off_shift_filter",
                    {"shift_start_hour": start, "shift_end_hour": end},
                    status="requested",
                )
            )
        else:
            result.constraints.append(
                SplConstraint("off_shift_filter", {"shift_start_hour": None, "shift_end_hour": None}, status="missing_config")
            )
            result.missing_bindings.extend(["normal_shift_start_hour", "normal_shift_end_hour"])

    return result


def off_shift_filter_clause(shift_start: int, shift_end: int) -> str:
    return f"(login_hour < {shift_start} OR login_hour >= {shift_end})"


def apply_constraints_to_projection(
    projection: Any,
    constraints: list[SplConstraint | dict[str, Any]],
    slots: dict[str, str],
) -> list[SplConstraint]:
    """Mutate a FinalSplProjection with off-shift filters when configured."""
    normalized: list[SplConstraint] = []
    for item in constraints:
        if isinstance(item, SplConstraint):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(
                SplConstraint(
                    str(item.get("constraint_type") or ""),
                    item.get("value"),
                    status=str(item.get("status") or "requested"),
                )
            )

    for constraint in normalized:
        if constraint.constraint_type != "off_shift_filter":
            continue
        if constraint.status == "missing_config":
            continue
        value = constraint.value if isinstance(constraint.value, dict) else {}
        start = value.get("shift_start_hour")
        end = value.get("shift_end_hour")
        if start is None or end is None:
            continue
        if not any("login_hour" in line for line in projection.eval_lines):
            projection.eval_lines.append('| eval login_hour=tonumber(strftime(_time, "%H"))')
        clause = off_shift_filter_clause(int(start), int(end))
        if clause not in projection.where_clauses:
            projection.where_clauses.append(clause)
        if "login_hour" not in projection.table_fields:
            projection.table_fields.append("login_hour")
        projection.enriched_windows_spl = True  # type: ignore[attr-defined]
        constraint.status = "implemented"

    return normalized


def validate_constraint_coverage(
    constraints: list[SplConstraint | dict[str, Any]],
    spl: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Mark constraint implementation status against final SPL text."""
    spl_lower = (spl or "").lower()
    missing: list[str] = []
    serialized: list[dict[str, Any]] = []

    for item in constraints:
        if isinstance(item, SplConstraint):
            constraint = item
        else:
            constraint = SplConstraint(
                str(item.get("constraint_type") or ""),
                item.get("value"),
                status=str(item.get("status") or "requested"),
            )

        if constraint.constraint_type == "event_code_filter":
            code = str(constraint.value)
            if code in spl and ("event_code_norm" in spl_lower or f"eventcode={code.lower()}" in spl_lower):
                constraint.status = "implemented"
            elif constraint.status != "missing_config":
                constraint.status = "not_implemented"
                missing.append(f"event_code_filter:{code}")

        elif constraint.constraint_type == "subnet_filter":
            if "cidrmatch" in spl_lower or "substation_id" in spl_lower:
                constraint.status = "implemented"
            elif constraint.status != "missing_config":
                constraint.status = "not_implemented"
                missing.append("subnet_filter")

        elif constraint.constraint_type == "off_shift_filter":
            if constraint.status == "missing_config":
                missing.extend(["normal_shift_start_hour", "normal_shift_end_hour"])
            elif 'strftime(_time, "%h")' in spl_lower or 'strftime(_time, "%H")' in spl:
                value = constraint.value if isinstance(constraint.value, dict) else {}
                start = value.get("shift_start_hour")
                end = value.get("shift_end_hour")
                if start is not None and end is not None:
                    needle = f"login_hour < {start}"
                    if needle.lower() in spl_lower:
                        constraint.status = "implemented"
                    else:
                        constraint.status = "not_implemented"
                        missing.append("off_shift_filter")
                else:
                    constraint.status = "not_implemented"
                    missing.append("off_shift_filter")
            elif constraint.status != "missing_config":
                constraint.status = "not_implemented"
                missing.append("off_shift_filter")

        serialized.append(constraint.to_dict())

    return serialized, missing


def constraints_incomplete(constraints: list[dict[str, Any]]) -> bool:
    return any(
        c.get("status") in {"not_implemented", "missing_config", "requested"}
        for c in constraints
    )
