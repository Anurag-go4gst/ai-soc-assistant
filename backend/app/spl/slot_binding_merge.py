"""LLM slot supplementation and precedence-conflict filtering for bindings."""

from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING, Any

from app.spl.spl_slot_binding_validator import (
    SLOT_TYPES,
    SlotValidationOutcome,
    load_slot_binding_policy,
    normalize_slot_key_aliases,
    validate_slot_value,
)
if TYPE_CHECKING:
    from app.spl.user_constraint_bindings import UserConstraintBindings

_SLOT_SOURCE_LLM = "llm"
_SLOT_SOURCE_USER_EXPLICIT = "user_explicit"
_SLOT_SOURCE_DETERMINISTIC = "deterministic"
_SLOT_SOURCE_SOURCE_PROFILE = "source_profile"

_LLM_SUPPLEMENT_BLOCKED_REASON = "llm_supplement_blocked_by_deterministic_rejection"

_AUTHORITATIVE_SLOT_SOURCES = frozenset(
    {
        _SLOT_SOURCE_USER_EXPLICIT,
        _SLOT_SOURCE_DETERMINISTIC,
        _SLOT_SOURCE_SOURCE_PROFILE,
    }
)

_BLOCK_REJECTION_MARKERS = (
    "slot_injection_blocked",
    "not_allowlisted",
    "result_limit_exceeds_policy",
    "rejected_by_policy",
    "unsafe_pattern",
    "conflicts_with_user_explicit",
    "conflicts_with_source_profile",
)

_ALLOW_REJECTION_MARKERS = (
    "slot_pattern_invalid",
    "slot_ip_invalid",
    "slot_cidr_invalid",
    "slot_port_not_numeric",
    "slot_port_out_of_range",
    "slot_time_window_unbounded",
    "slot_empty",
    "slot_validation_failed",
    "unsupported_slot",
    "ambiguous_value",
    "normalization_failed",
    "unsupported_format",
    "parse_failed",
)

_CIDR_PATTERN = re.compile(
    r"^\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?$",
    re.IGNORECASE,
)


def canonical_scope_value(value: Any) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    if text in {"substation_subnet", "substation_subnets"}:
        return "substation_subnet"
    return text

_SERVICE_PORT_MAP = {"smb": 445, "ssh": 22, "rdp": 3389, "dns": 53, "http": 80, "https": 443}
_ALLOW_ACTION_MARKERS = ("permit", "allow", "accept")
_DENY_ACTION_MARKERS = ("deny", "block", "fail", "reject")


def canonical_slot_family(slot: str) -> str:
    from app.spl.spl_slot_binding_validator import canonical_slot_key

    return canonical_slot_key(slot)


def _normalize_user_value(value: Any) -> str:
    text = str(value).strip().lower()
    if "\\" in text:
        text = text.rsplit("\\", 1)[-1]
    return text


def _normalize_code_values(raw: Any) -> frozenset[str]:
    from app.spl.numeric_code_filter import split_code_list

    return frozenset(split_code_list(raw))


def _normalize_port_token(value: Any) -> int | str:
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text.isdigit():
        return int(text)
    return _SERVICE_PORT_MAP.get(text, text)


def _ports_semantically_equal(left: Any, right: Any) -> bool:
    left_token = _normalize_port_token(left)
    right_token = _normalize_port_token(right)
    if left_token == right_token:
        return True
    left_port = left_token if isinstance(left_token, int) else _SERVICE_PORT_MAP.get(str(left_token), None)
    right_port = right_token if isinstance(right_token, int) else _SERVICE_PORT_MAP.get(str(right_token), None)
    if left_port is not None and right_port is not None:
        return left_port == right_port
    return False


def _action_semantic_group(value: Any) -> str:
    text = str(value).strip().lower()
    if any(marker in text for marker in _ALLOW_ACTION_MARKERS):
        return "allow"
    if any(marker in text for marker in _DENY_ACTION_MARKERS):
        return "deny"
    return text


def _protocol_tokens(raw: Any) -> frozenset[str]:
    from app.spl.numeric_code_filter import split_code_list

    tokens = {str(item).strip().lower() for item in split_code_list(raw)}
    return frozenset(token for token in tokens if token)


def slot_values_semantically_equal(slot: str, left: Any, right: Any) -> bool:
    """Return True when two slot values express the same constraint."""
    if left is None or right is None:
        return False

    family = canonical_slot_family(slot)

    if family == "user":
        return _normalize_user_value(left) == _normalize_user_value(right)

    if family in {"event_code", "function_code"}:
        return _normalize_code_values(left) == _normalize_code_values(right)

    if family == "port":
        return _ports_semantically_equal(left, right)

    if family in {"src_zone", "dest_zone", "zone"}:
        return str(left).strip().lower() == str(right).strip().lower()

    if family in {"protocol", "protocols"}:
        return _protocol_tokens(left) == _protocol_tokens(right)

    if family == "service":
        left_token = _normalize_port_token(left)
        right_token = _normalize_port_token(right)
        if _ports_semantically_equal(left, right):
            return True
        return str(left).strip().lower() == str(right).strip().lower()

    if family == "action_semantic":
        return _action_semantic_group(left) == _action_semantic_group(right)

    if family in {"host", "alert_id"}:
        return str(left).strip().lower() == str(right).strip().lower()

    if family == "index":
        return str(left).strip().lower() == str(right).strip().lower()

    if family == "time_window":
        from app.spl.spl_slot_binding_validator import _normalize_time_window

        left_norm = _normalize_time_window(str(left))
        right_norm = _normalize_time_window(str(right))
        return left_norm is not None and left_norm == right_norm

    if family in {"src_scope", "dest_scope"}:
        return canonical_scope_value(left) == canonical_scope_value(right)

    return str(left).strip() == str(right).strip()



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


def _is_false_positive_conflict(
    conflict: dict[str, Any],
    merged_raw: dict[str, Any],
) -> bool:
    slot = str(conflict.get("slot") or "")
    kept = conflict.get("kept_value")
    dropped = conflict.get("dropped_value")
    if _is_false_positive_scope_conflict(conflict, merged_raw):
        return True
    if slot and slot_values_semantically_equal(slot, kept, dropped):
        return True
    return False


def partition_slot_conflicts(
    conflicts: list[dict[str, Any]],
    merged_raw: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split conflicts into unresolved rows and same-value suppressions."""
    unresolved: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for conflict in conflicts:
        if _is_false_positive_conflict(conflict, merged_raw):
            suppressed.append({**conflict, "resolution": "same_value_merged"})
        else:
            unresolved.append(conflict)
    return unresolved, suppressed


def filter_slot_conflicts(
    conflicts: list[dict[str, Any]],
    merged_raw: dict[str, Any],
) -> list[dict[str, Any]]:
    """Drop false-positive conflicts when canonical/semantic slot values match."""
    unresolved, _ = partition_slot_conflicts(conflicts, merged_raw)
    return unresolved


def _classify_slot_rejection(reason: str) -> str:
    """Return ``block`` or ``allow`` for whether LLM may supplement after this rejection."""
    lowered = str(reason).lower()
    for marker in _BLOCK_REJECTION_MARKERS:
        if marker in lowered:
            return "block"
    for marker in _ALLOW_REJECTION_MARKERS:
        if marker in lowered:
            return "allow"
    return "block"


def _rejection_reasons_for_slot(
    validated: SlotValidationOutcome,
    slot_type: str,
) -> list[str]:
    reasons: list[str] = []
    for reason in validated.reject_reasons:
        if reason.endswith(f":{slot_type}") or reason == f"slot_validation_failed:{slot_type}":
            reasons.append(reason)
    if slot_type == "index" and "slot_index_not_allowlisted" in validated.reject_reasons:
        reasons.append("slot_index_not_allowlisted")
    if slot_type == "indexes":
        for reason in validated.reject_reasons:
            if "slot_index_not_allowlisted" in reason or reason.startswith("slot_pattern_invalid:indexes"):
                reasons.append(reason)
        if not reasons and "slot_indexes_all_rejected" in validated.reject_reasons:
            reasons.append("slot_indexes_all_rejected")
    if slot_type == "sourcetype" and "slot_sourcetype_not_allowlisted" in validated.reject_reasons:
        reasons.append("slot_sourcetype_not_allowlisted")
    return list(dict.fromkeys(reasons))


def _llm_blocked_by_merge_conflict(
    slot_type: str,
    conflicts: list[dict[str, Any]] | None,
) -> tuple[bool, str | None]:
    for conflict in conflicts or []:
        if str(conflict.get("slot") or "") != slot_type:
            continue
        if conflict.get("dropped_source") != _SLOT_SOURCE_LLM:
            continue
        kept = str(conflict.get("kept_source") or "")
        if kept == _SLOT_SOURCE_USER_EXPLICIT:
            return True, "conflicts_with_user_explicit_slot"
        if kept == _SLOT_SOURCE_SOURCE_PROFILE:
            return True, "conflicts_with_source_profile"
    return False, None


def llm_supplement_blocked_by_deterministic_rejection(
    slot_type: str,
    *,
    validated: SlotValidationOutcome | None,
    merged_raw: dict[str, Any] | None,
    slot_sources: dict[str, str] | None,
    conflicts: list[dict[str, Any]] | None = None,
) -> tuple[bool, str | None]:
    """Return whether an authoritative pre-LLM slot failure blocks LLM supplementation."""
    if not validated or not merged_raw:
        return False, None
    if slot_type not in merged_raw:
        return False, None
    if slot_type in validated.normalized_slots:
        return False, None

    blocked_by_conflict, conflict_reason = _llm_blocked_by_merge_conflict(slot_type, conflicts)
    if blocked_by_conflict:
        return True, conflict_reason

    authoritative = (slot_sources or {}).get(slot_type)
    if authoritative not in _AUTHORITATIVE_SLOT_SOURCES:
        return False, None

    reasons = _rejection_reasons_for_slot(validated, slot_type)
    if not reasons:
        return True, "validation_failed"

    for reason in reasons:
        if _classify_slot_rejection(reason) == "block":
            return True, reason
    return False, None


def _record_llm_supplement_block(
    bindings: UserConstraintBindings,
    *,
    slot_type: str,
    llm_candidate: Any,
    deterministic_rejection: str,
) -> None:
    blocks = bindings.debug_trace.setdefault("llm_supplement_blocks", [])
    blocks.append(
        {
            "slot": slot_type,
            "reason": _LLM_SUPPLEMENT_BLOCKED_REASON,
            "deterministic_rejection": deterministic_rejection,
            "llm_candidate": llm_candidate,
        }
    )


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
    validated: SlotValidationOutcome | None = None,
    merged_raw: dict[str, Any] | None = None,
    slot_sources: dict[str, str] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
) -> None:
    """Validate LLM entity slots per-slot and merge accepted values into bindings."""
    if not llm_slots:
        return
    policy = load_slot_binding_policy()
    indexes = allowed_indexes or policy.allowed_indexes
    sourcetypes = allowed_sourcetypes or policy.allowed_sourcetypes
    normalized_llm = normalize_slot_key_aliases(dict(llm_slots))
    effective_slot_sources = dict(slot_sources or bindings.slot_sources)

    for slot_type, raw_value in normalized_llm.items():
        if raw_value is None or raw_value == "" or raw_value == []:
            continue
        if slot_type not in SLOT_TYPES:
            continue
        authoritative_source = effective_slot_sources.get(slot_type)
        if authoritative_source in {_SLOT_SOURCE_USER_EXPLICIT, _SLOT_SOURCE_SOURCE_PROFILE}:
            if (
                validated
                and merged_raw
                and slot_type in merged_raw
                and slot_type not in validated.normalized_slots
            ):
                slot_reasons = _rejection_reasons_for_slot(validated, slot_type)
                if authoritative_source == _SLOT_SOURCE_USER_EXPLICIT:
                    rejection = slot_reasons[0] if slot_reasons else "conflicts_with_user_explicit_slot"
                else:
                    rejection = slot_reasons[0] if slot_reasons else "conflicts_with_source_profile"
                _record_llm_supplement_block(
                    bindings,
                    slot_type=slot_type,
                    llm_candidate=raw_value,
                    deterministic_rejection=rejection,
                )
            continue
        if validated and slot_type in validated.normalized_slots:
            continue
        blocked, block_reason = llm_supplement_blocked_by_deterministic_rejection(
            slot_type,
            validated=validated,
            merged_raw=merged_raw,
            slot_sources=effective_slot_sources,
            conflicts=conflicts,
        )
        if blocked:
            _record_llm_supplement_block(
                bindings,
                slot_type=slot_type,
                llm_candidate=raw_value,
                deterministic_rejection=str(block_reason or "validation_failed"),
            )
            continue
        if slot_type in {"index", "indexes"}:
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
