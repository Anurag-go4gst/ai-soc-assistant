"""LLM slot supplementation and precedence-conflict filtering for bindings."""

from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING, Any

from app.spl.spl_slot_binding_validator import (
    SLOT_TYPES,
    load_slot_binding_policy,
    normalize_slot_key_aliases,
    validate_slot_value,
)
if TYPE_CHECKING:
    from app.spl.user_constraint_bindings import UserConstraintBindings

_SLOT_SOURCE_LLM = "llm"
_SLOT_SOURCE_USER_EXPLICIT = "user_explicit"

_CIDR_PATTERN = re.compile(
    r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?$",
    re.IGNORECASE,
)


def canonical_scope_value(value: Any) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    if text in {"substation_subnet", "substation_subnets"}:
        return "substation_subnet"
    return text


def _is_cidr_like(value: Any) -> bool:
    text = str(value).strip()
    if not text:
        return False
    if _CIDR_PATTERN.fullmatch(text):
        return True
    try:
        ipaddress.ip_network(text, strict=False)
        return True
    except ValueError:
        return False


_SCOPE_PROFILE_CIDR_SLOT: dict[str, str] = {
    "src_scope": "approved_source_cidr",
    "dest_scope": "approved_destination_cidr",
}


def _is_natural_language_scope_label(value: Any) -> bool:
    text = str(value).strip() if value is not None else ""
    return bool(text) and not _is_cidr_like(text)


def _cidr_values_equal(left: Any, right: Any) -> bool:
    left_text = str(left).strip()
    right_text = str(right).strip()
    if not left_text or not right_text:
        return False
    try:
        return ipaddress.ip_network(left_text, strict=False) == ipaddress.ip_network(
            right_text, strict=False
        )
    except ValueError:
        return left_text == right_text


def _is_scope_label_profile_cidr_resolution(
    slot: str,
    kept: Any,
    dropped: Any,
    merged_raw: dict[str, Any],
) -> bool:
    """True when a scope-label vs CIDR conflict is label resolving to the profile CIDR."""
    profile_cidr_slot = _SCOPE_PROFILE_CIDR_SLOT.get(slot)
    if not profile_cidr_slot:
        return False
    profile_cidr = merged_raw.get(profile_cidr_slot)
    if not profile_cidr:
        return False
    for label_value, cidr_value in ((kept, dropped), (dropped, kept)):
        if not _is_natural_language_scope_label(label_value):
            continue
        if not _is_cidr_like(cidr_value):
            continue
        if _cidr_values_equal(cidr_value, profile_cidr):
            return True
    return False


def _is_false_positive_scope_conflict(
    conflict: dict[str, Any],
    merged_raw: dict[str, Any],
) -> bool:
    slot = str(conflict.get("slot") or "")
    if slot not in {"src_scope", "dest_scope"}:
        return False
    kept = conflict.get("kept_value")
    dropped = conflict.get("dropped_value")
    if canonical_scope_value(kept) == canonical_scope_value(dropped):
        return True
    if _is_scope_label_profile_cidr_resolution(slot, kept, dropped, merged_raw):
        return True
    return False


def filter_slot_conflicts(
    conflicts: list[dict[str, Any]],
    merged_raw: dict[str, Any],
) -> list[dict[str, Any]]:
    """Drop false-positive scope conflicts when canonical scope values match."""
    return [
        conflict
        for conflict in conflicts
        if not _is_false_positive_scope_conflict(conflict, merged_raw)
    ]


def _apply_accepted_slot(bindings: UserConstraintBindings, slot_type: str, value: str) -> None:
    bindings.normalized_slots[slot_type] = value
    if slot_type == "sourcetype" and value not in bindings.explicit_sourcetypes:
        bindings.explicit_sourcetypes.append(value)
    elif slot_type == "host" and value not in bindings.explicit_hosts:
        bindings.explicit_hosts.append(value)
    elif slot_type == "user" and value not in bindings.explicit_users:
        bindings.explicit_users.append(value)
    elif slot_type == "src_ip" and value not in bindings.explicit_src_ips:
        bindings.explicit_src_ips.append(value)
    elif slot_type == "dest_ip" and value not in bindings.explicit_dest_ips:
        bindings.explicit_dest_ips.append(value)
    elif slot_type == "cidr" and value not in bindings.explicit_cidrs:
        bindings.explicit_cidrs.append(value)
    elif slot_type == "src_zone" and value not in bindings.explicit_src_zones:
        bindings.explicit_src_zones.append(value)
    elif slot_type == "dest_zone" and value not in bindings.explicit_dest_zones:
        bindings.explicit_dest_zones.append(value)
    elif slot_type == "lookup" and value not in bindings.explicit_lookups:
        bindings.explicit_lookups.append(value)
    elif slot_type == "protocol" and value not in bindings.explicit_protocols:
        bindings.explicit_protocols.append(value)
    elif slot_type == "service" and value not in bindings.explicit_services:
        bindings.explicit_services.append(value)
    elif slot_type == "event_code" and value not in bindings.explicit_event_codes:
        bindings.explicit_event_codes.append(value)
    elif slot_type == "function_code":
        bindings.explicit_function_codes.extend(
            [part.strip() for part in str(value).split(",") if part.strip()]
        )
    elif slot_type == "port":
        try:
            port = int(value)
            if port not in bindings.explicit_ports:
                bindings.explicit_ports.append(port)
        except ValueError:
            pass
    elif slot_type == "time_window":
        bindings.explicit_time_window = value
    elif slot_type == "threshold":
        bindings.explicit_thresholds["threshold"] = value
    elif slot_type == "threshold_comparison":
        bindings.explicit_thresholds["comparison"] = value
    elif slot_type == "unexpected_ip_direction":
        bindings.explicit_directionality["unexpected_ip_direction"] = value
    elif slot_type == "allowlist_semantic":
        bindings.explicit_allowlist_semantics["allowlist_semantic"] = value
    elif slot_type == "action_semantic" and value not in bindings.explicit_action_semantics:
        bindings.explicit_action_semantics.append(value)


def supplement_accepted_llm_entity_slots(
    bindings: UserConstraintBindings,
    llm_slots: dict[str, Any],
    *,
    allowed_indexes: tuple[str, ...],
    allowed_sourcetypes: tuple[str, ...] | None = None,
) -> None:
    """Validate LLM entity slots per-slot and merge accepted values into bindings."""
    if not llm_slots:
        return
    policy = load_slot_binding_policy()
    indexes = allowed_indexes or policy.allowed_indexes
    sourcetypes = allowed_sourcetypes or policy.allowed_sourcetypes
    normalized_llm = normalize_slot_key_aliases(dict(llm_slots))

    for slot_type, raw_value in normalized_llm.items():
        if raw_value is None or raw_value == "" or raw_value == []:
            continue
        if slot_type not in SLOT_TYPES:
            continue
        if slot_type in {"index", "indexes"}:
            continue
        if bindings.slot_sources.get(slot_type) == _SLOT_SOURCE_USER_EXPLICIT:
            continue
        if slot_type in bindings.normalized_slots and bindings.validation_status.get(slot_type) in {
            "accepted",
            "user_explicit_preserved",
            "user_explicit_partial_preserved",
            "user_explicit_rejected_preserved",
        }:
            continue

        if slot_type == "function_code" and isinstance(raw_value, list):
            raw_value = ",".join(str(item) for item in raw_value)
        if slot_type == "protocols" and isinstance(raw_value, list):
            raw_value = ",".join(str(item).lower() for item in raw_value)
            slot_type = "protocol"

        value, errors = validate_slot_value(
            slot_type,
            raw_value,
            allowed_indexes=indexes,
            allowed_sourcetypes=sourcetypes,
            policy=policy,
        )
        if errors or value is None:
            continue

        bindings.slot_sources[slot_type] = _SLOT_SOURCE_LLM
        bindings.validation_status[slot_type] = "accepted"
        _apply_accepted_slot(bindings, slot_type, value)
