"""Normalized user constraint bindings for SPL fidelity across template/draft paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.query_understanding.models import QueryEntities, QueryUnderstandingResult
from app.spl.spl_slot_binding_validator import (
    SlotValidationOutcome,
    extract_natural_language_slots,
    extract_query_slots,
    load_slot_binding_policy,
    validate_slot_map,
)

SLOT_SOURCE_USER_EXPLICIT = "user_explicit"
SLOT_SOURCE_DETERMINISTIC = "deterministic"
SLOT_SOURCE_LLM = "llm"
SLOT_SOURCE_SOURCE_PROFILE = "source_profile"
SLOT_SOURCE_TEMPLATE_DEFAULT = "template_default"

_SLOT_PRECEDENCE = (
    SLOT_SOURCE_USER_EXPLICIT,
    SLOT_SOURCE_DETERMINISTIC,
    SLOT_SOURCE_LLM,
    SLOT_SOURCE_SOURCE_PROFILE,
    SLOT_SOURCE_TEMPLATE_DEFAULT,
)


@dataclass
class UserConstraintBindings:
    explicit_indexes: list[str] = field(default_factory=list)
    explicit_sourcetypes: list[str] = field(default_factory=list)
    explicit_protocols: list[str] = field(default_factory=list)
    explicit_event_codes: list[str | int] = field(default_factory=list)
    explicit_function_codes: list[str | int] = field(default_factory=list)
    explicit_hosts: list[str] = field(default_factory=list)
    explicit_users: list[str] = field(default_factory=list)
    explicit_src_ips: list[str] = field(default_factory=list)
    explicit_dest_ips: list[str] = field(default_factory=list)
    explicit_cidrs: list[str] = field(default_factory=list)
    explicit_ports: list[int] = field(default_factory=list)
    explicit_services: list[str] = field(default_factory=list)
    explicit_src_zones: list[str] = field(default_factory=list)
    explicit_dest_zones: list[str] = field(default_factory=list)
    explicit_lookups: list[str] = field(default_factory=list)
    explicit_thresholds: dict[str, Any] = field(default_factory=dict)
    explicit_time_window: str | None = None
    explicit_directionality: dict[str, Any] = field(default_factory=dict)
    explicit_allowlist_semantics: dict[str, Any] = field(default_factory=dict)
    explicit_action_semantics: list[str] = field(default_factory=list)
    slot_sources: dict[str, str] = field(default_factory=dict)
    validation_status: dict[str, str] = field(default_factory=dict)
    unbound_constraints: list[dict[str, Any]] = field(default_factory=list)
    rejected_slots: dict[str, list[str]] = field(default_factory=dict)
    normalized_slots: dict[str, str] = field(default_factory=dict)
    debug_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "explicit_indexes": list(self.explicit_indexes),
            "explicit_sourcetypes": list(self.explicit_sourcetypes),
            "explicit_protocols": list(self.explicit_protocols),
            "explicit_event_codes": list(self.explicit_event_codes),
            "explicit_function_codes": list(self.explicit_function_codes),
            "explicit_hosts": list(self.explicit_hosts),
            "explicit_users": list(self.explicit_users),
            "explicit_src_ips": list(self.explicit_src_ips),
            "explicit_dest_ips": list(self.explicit_dest_ips),
            "explicit_cidrs": list(self.explicit_cidrs),
            "explicit_ports": list(self.explicit_ports),
            "explicit_services": list(self.explicit_services),
            "explicit_src_zones": list(self.explicit_src_zones),
            "explicit_dest_zones": list(self.explicit_dest_zones),
            "explicit_lookups": list(self.explicit_lookups),
            "explicit_thresholds": dict(self.explicit_thresholds),
            "explicit_time_window": self.explicit_time_window,
            "explicit_directionality": dict(self.explicit_directionality),
            "explicit_allowlist_semantics": dict(self.explicit_allowlist_semantics),
            "explicit_action_semantics": list(self.explicit_action_semantics),
            "slot_sources": dict(self.slot_sources),
            "validation_status": dict(self.validation_status),
            "unbound_constraints": list(self.unbound_constraints),
            "rejected_slots": dict(self.rejected_slots),
            "normalized_slots": dict(self.normalized_slots),
            "debug_trace": dict(self.debug_trace),
        }


def build_user_constraint_bindings(
    user_query: str,
    *,
    llm_intent_advisory: LLMIntentAdvisory | dict[str, Any] | None = None,
    query_understanding: QueryUnderstandingResult | None = None,
    extra_slots: dict[str, Any] | None = None,
    source_profile_trace: dict[str, Any] | None = None,
    allowed_indexes: tuple[str, ...] | None = None,
    allowed_sourcetypes: tuple[str, ...] | None = None,
    preserve_user_explicit_indexes: bool = True,
) -> UserConstraintBindings:
    user_explicit = extract_query_slots(user_query)
    for key, value in extract_natural_language_slots(user_query).items():
        if key not in user_explicit:
            user_explicit[key] = value

    deterministic: dict[str, Any] = {}
    if query_understanding is not None:
        deterministic.update(_entities_to_slots(query_understanding.entities))

    llm_slots = _llm_entity_slots(llm_intent_advisory)
    source_profile_slots = dict(extra_slots or {})
    merged_raw, slot_sources, conflicts = _merge_slots_with_precedence(
        {
            SLOT_SOURCE_USER_EXPLICIT: user_explicit,
            SLOT_SOURCE_DETERMINISTIC: deterministic,
            SLOT_SOURCE_LLM: llm_slots,
            SLOT_SOURCE_SOURCE_PROFILE: source_profile_slots,
        }
    )
    policy_for_source_profile = None
    if (
        (allowed_indexes is None and source_profile_slots.get("index"))
        or (allowed_sourcetypes is None and source_profile_slots.get("sourcetype"))
    ):
        policy_for_source_profile = load_slot_binding_policy()
    base_allowed_indexes = allowed_indexes or (
        policy_for_source_profile.allowed_indexes if policy_for_source_profile is not None else None
    )
    base_allowed_sourcetypes = allowed_sourcetypes or (
        policy_for_source_profile.allowed_sourcetypes if policy_for_source_profile is not None else None
    )
    allowed_indexes = _with_source_profile_allowed_value(
        base_allowed_indexes,
        source_profile_slots.get("index"),
    )
    allowed_sourcetypes = _with_source_profile_allowed_value(
        base_allowed_sourcetypes,
        source_profile_slots.get("sourcetype"),
    )

    validated = validate_slot_map(
        merged_raw,
        allowed_indexes=allowed_indexes,
        allowed_sourcetypes=allowed_sourcetypes,
        slot_source="user",
    )
    bindings = _bindings_from_slots(validated.normalized_slots, slot_sources)

    for slot_type, raw_value in merged_raw.items():
        if slot_type in validated.normalized_slots:
            bindings.validation_status[slot_type] = "accepted"
            continue
        reason = _rejection_reason(validated, slot_type)
        if slot_sources.get(slot_type) == SLOT_SOURCE_USER_EXPLICIT and preserve_user_explicit_indexes:
            if slot_type == "index" and raw_value:
                text = str(raw_value).strip().lower()
                if text and text not in bindings.explicit_indexes:
                    bindings.explicit_indexes.append(text)
                    bindings.normalized_slots["index"] = text
                    bindings.slot_sources["index"] = SLOT_SOURCE_USER_EXPLICIT
                    bindings.validation_status["index"] = "user_explicit_preserved"
                    continue
            if slot_type == "sourcetype" and raw_value:
                text = str(raw_value).strip()
                if text and text not in bindings.explicit_sourcetypes:
                    bindings.explicit_sourcetypes.append(text)
                    bindings.validation_status["sourcetype"] = "user_explicit_rejected_preserved"
        bindings.rejected_slots[slot_type] = [reason]
        bindings.unbound_constraints.append(
            {
                "slot": slot_type,
                "value": raw_value,
                "reason": reason,
                "source": slot_sources.get(slot_type),
            }
        )

    for conflict in conflicts:
        bindings.unbound_constraints.append(conflict)

    bindings.debug_trace = {
        "extracted_by_source": {
            SLOT_SOURCE_USER_EXPLICIT: dict(user_explicit),
            SLOT_SOURCE_DETERMINISTIC: dict(deterministic),
            SLOT_SOURCE_LLM: dict(llm_slots),
            SLOT_SOURCE_SOURCE_PROFILE: dict(source_profile_slots),
        },
        "accepted_slots": dict(validated.normalized_slots),
        "rejected_slots": dict(bindings.rejected_slots),
        "slot_conflicts": list(conflicts),
        "final_slot_precedence_decision": _final_slot_precedence_decisions(
            merged_raw,
            slot_sources,
            conflicts,
        ),
    }
    if source_profile_trace:
        bindings.debug_trace.update(source_profile_trace)
    return bindings


def _with_source_profile_allowed_value(
    allowed_values: tuple[str, ...] | None,
    value: Any,
) -> tuple[str, ...] | None:
    if not value:
        return allowed_values
    normalized = str(value).strip().lower()
    if not normalized:
        return allowed_values
    values = tuple(allowed_values or ())
    if normalized in values:
        return values
    return (*values, normalized)


def bindings_to_extra_slots(bindings: UserConstraintBindings) -> dict[str, Any]:
    extra: dict[str, Any] = dict(bindings.normalized_slots)
    if bindings.explicit_indexes and "index" not in extra:
        extra["index"] = bindings.explicit_indexes[0]
    if len(bindings.explicit_indexes) > 1:
        extra["indexes"] = bindings.explicit_indexes
    if bindings.explicit_protocols:
        extra["protocol"] = bindings.explicit_protocols[0]
    if bindings.explicit_function_codes:
        extra["function_code"] = bindings.explicit_function_codes
    if bindings.explicit_event_codes:
        extra["event_code"] = bindings.explicit_event_codes[0]
    if bindings.explicit_src_zones:
        extra["src_zone"] = bindings.explicit_src_zones[0]
    if bindings.explicit_dest_zones:
        extra["dest_zone"] = bindings.explicit_dest_zones[0]
    if bindings.explicit_services:
        extra["service"] = bindings.explicit_services[0]
    if bindings.explicit_lookups:
        extra["lookup"] = bindings.explicit_lookups[0]
    if bindings.explicit_thresholds:
        extra.update(bindings.explicit_thresholds)
    if bindings.explicit_directionality:
        extra.update(bindings.explicit_directionality)
    if bindings.explicit_allowlist_semantics:
        extra.update(bindings.explicit_allowlist_semantics)
    if bindings.explicit_action_semantics:
        extra["action_semantic"] = bindings.explicit_action_semantics[0]
    return extra


def _merge_slots_with_precedence(
    sources: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    merged: dict[str, Any] = {}
    slot_sources: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []

    for source_name in _SLOT_PRECEDENCE:
        bucket = sources.get(source_name) or {}
        for slot_type, value in bucket.items():
            if value is None or value == "" or value == []:
                continue
            if slot_type not in merged:
                merged[slot_type] = value
                slot_sources[slot_type] = source_name
                continue
            if _slot_values_equal(merged[slot_type], value):
                continue
            if _precedence_rank(source_name) < _precedence_rank(slot_sources[slot_type]):
                conflicts.append(
                    {
                        "slot": slot_type,
                        "reason": "conflicts_with_higher_precedence_slot",
                        "kept_source": source_name,
                        "dropped_source": slot_sources[slot_type],
                        "kept_value": value,
                        "dropped_value": merged[slot_type],
                    }
                )
                merged[slot_type] = value
                slot_sources[slot_type] = source_name
            else:
                conflicts.append(
                    {
                        "slot": slot_type,
                        "reason": "conflicts_with_user_explicit_slot",
                        "kept_source": slot_sources[slot_type],
                        "dropped_source": source_name,
                        "kept_value": merged[slot_type],
                        "dropped_value": value,
                    }
                )
    return merged, slot_sources, conflicts


def _precedence_rank(source: str) -> int:
    try:
        return _SLOT_PRECEDENCE.index(source)
    except ValueError:
        return len(_SLOT_PRECEDENCE)


def _final_slot_precedence_decisions(
    merged_raw: dict[str, Any],
    slot_sources: dict[str, str],
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions = [
        {
            "slot": slot,
            "value": value,
            "source": slot_sources.get(slot),
            "status": "kept",
        }
        for slot, value in sorted(merged_raw.items())
    ]
    for conflict in conflicts:
        decisions.append(
            {
                "slot": conflict.get("slot"),
                "value": conflict.get("dropped_value"),
                "source": conflict.get("dropped_source"),
                "status": "dropped",
                "reason": conflict.get("reason"),
                "kept_source": conflict.get("kept_source"),
                "kept_value": conflict.get("kept_value"),
            }
        )
    return decisions


def _slot_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return [str(item).lower() for item in left] == [str(item).lower() for item in right]
    return str(left).lower() == str(right).lower()


def _llm_entity_slots(advisory: LLMIntentAdvisory | dict[str, Any] | None) -> dict[str, Any]:
    if advisory is None:
        return {}
    if isinstance(advisory, LLMIntentAdvisory):
        return dict(advisory.entity_slots_candidate or {})
    raw = advisory.get("entity_slots_candidate")
    return dict(raw) if isinstance(raw, dict) else {}


def _entities_to_slots(entities: QueryEntities) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    if entities.index:
        slots["index"] = entities.index[0] if len(entities.index) == 1 else entities.index
    if entities.sourcetype:
        slots["sourcetype"] = entities.sourcetype[0]
    if entities.host:
        slots["host"] = entities.host[0]
    if entities.user:
        slots["user"] = entities.user[0]
    if entities.source_ip:
        slots["src_ip"] = entities.source_ip[0]
    if entities.destination_ip:
        slots["dest_ip"] = entities.destination_ip[0]
    if entities.port_numbers:
        slots["port"] = entities.port_numbers[0]
    if entities.time_window:
        slots["time_window"] = entities.time_window
    if entities.zone_labels:
        slots["zone"] = entities.zone_labels[0]
    return slots


def _bindings_from_slots(
    normalized_slots: dict[str, str],
    slot_sources: dict[str, str],
) -> UserConstraintBindings:
    bindings = UserConstraintBindings(
        normalized_slots=dict(normalized_slots),
        slot_sources=dict(slot_sources),
    )
    def is_explicit(slot: str) -> bool:
        return slot_sources.get(slot) != SLOT_SOURCE_SOURCE_PROFILE

    index_val = normalized_slots.get("index")
    if index_val and is_explicit("index"):
        bindings.explicit_indexes = [index_val]
    indexes_val = normalized_slots.get("indexes")
    if indexes_val and is_explicit("indexes"):
        bindings.explicit_indexes = [part.strip() for part in str(indexes_val).split(",") if part.strip()]
    for key, attr in (
        ("sourcetype", "explicit_sourcetypes"),
        ("host", "explicit_hosts"),
        ("user", "explicit_users"),
        ("src_ip", "explicit_src_ips"),
        ("dest_ip", "explicit_dest_ips"),
        ("cidr", "explicit_cidrs"),
        ("src_zone", "explicit_src_zones"),
        ("dest_zone", "explicit_dest_zones"),
        ("lookup", "explicit_lookups"),
    ):
        if normalized_slots.get(key) and is_explicit(key):
            getattr(bindings, attr).append(normalized_slots[key])
    if normalized_slots.get("protocol") and is_explicit("protocol"):
        bindings.explicit_protocols.append(normalized_slots["protocol"])
    if normalized_slots.get("service") and is_explicit("service"):
        bindings.explicit_services.append(normalized_slots["service"])
    if normalized_slots.get("event_code") and is_explicit("event_code"):
        bindings.explicit_event_codes.append(normalized_slots["event_code"])
    if normalized_slots.get("function_code") and is_explicit("function_code"):
        raw_fc = normalized_slots["function_code"]
        bindings.explicit_function_codes.extend(
            [part.strip() for part in str(raw_fc).split(",") if part.strip()]
        )
    if normalized_slots.get("port") and is_explicit("port"):
        try:
            bindings.explicit_ports.append(int(normalized_slots["port"]))
        except ValueError:
            pass
    if normalized_slots.get("time_window") and is_explicit("time_window"):
        bindings.explicit_time_window = normalized_slots["time_window"]
    if normalized_slots.get("threshold") and is_explicit("threshold"):
        bindings.explicit_thresholds["threshold"] = normalized_slots["threshold"]
    if normalized_slots.get("threshold_comparison") and is_explicit("threshold_comparison"):
        bindings.explicit_thresholds["comparison"] = normalized_slots["threshold_comparison"]
    if normalized_slots.get("unexpected_ip_direction") and is_explicit("unexpected_ip_direction"):
        bindings.explicit_directionality["unexpected_ip_direction"] = normalized_slots["unexpected_ip_direction"]
    if normalized_slots.get("allowlist_semantic") and is_explicit("allowlist_semantic"):
        bindings.explicit_allowlist_semantics["allowlist_semantic"] = normalized_slots["allowlist_semantic"]
    if normalized_slots.get("action_semantic") and is_explicit("action_semantic"):
        bindings.explicit_action_semantics.append(normalized_slots["action_semantic"])
    return bindings


def _rejection_reason(outcome: SlotValidationOutcome, slot_type: str) -> str:
    for reason in outcome.reject_reasons:
        if slot_type in reason:
            return reason
    if any("unsupported_slot" in reason for reason in outcome.reject_reasons):
        return "unsupported_slot_type"
    return "validation_failed"
