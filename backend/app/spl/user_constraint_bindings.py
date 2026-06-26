"""Normalized user constraint bindings for SPL fidelity across template/draft paths."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.query_understanding.models import QueryEntities, QueryUnderstandingResult
from app.spl.slot_binding_merge import (
    filter_slot_conflicts,
    slot_values_semantically_equal,
    supplement_accepted_llm_entity_slots,
)
from app.spl.spl_slot_binding_validator import (
    SlotValidationOutcome,
    extract_natural_language_slots,
    extract_query_slots,
    load_slot_binding_policy,
    normalize_slot_key_aliases,
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
    effective_allowed_indexes = allowed_indexes or load_slot_binding_policy().allowed_indexes

    merged_raw = normalize_slot_key_aliases(merged_raw)
    validated = validate_slot_map(
        merged_raw,
        allowed_indexes=allowed_indexes,
        allowed_sourcetypes=allowed_sourcetypes,
        slot_source="user",
    )
    bindings = _bindings_from_slots(validated.normalized_slots, slot_sources)
    supplement_accepted_llm_entity_slots(
        bindings,
        llm_slots,
        allowed_indexes=effective_allowed_indexes,
        allowed_sourcetypes=allowed_sourcetypes,
    )
    # Multi-index user-explicit slots are owned by _preserve_user_explicit_indexes
    # (review-only preserve symmetric with single-index), so skip them here to avoid
    # double-recording rejected/unbound rows.
    _preserve_user_explicit_indexes(
        bindings,
        merged_raw,
        slot_sources=slot_sources,
        allowed_indexes=effective_allowed_indexes,
        preserve=preserve_user_explicit_indexes,
    )

    for slot_type, raw_value in merged_raw.items():
        if slot_type == "indexes":
            continue
        if slot_type in validated.normalized_slots:
            bindings.validation_status[slot_type] = "accepted"
            continue
        if (
            bindings.slot_sources.get(slot_type) == SLOT_SOURCE_LLM
            and bindings.validation_status.get(slot_type) == "accepted"
            and slot_type in bindings.normalized_slots
        ):
            continue
        reason = _rejection_reason(validated, slot_type)
        if slot_sources.get(slot_type) == SLOT_SOURCE_USER_EXPLICIT and preserve_user_explicit_indexes:
            if slot_type == "index" and raw_value:
                text = str(raw_value).strip().lower()
                if text:
                    # Fold the single-index slot into explicit_indexes; when the
                    # multi-index slot already preserved this value (NL extraction
                    # emits both) we must not re-record it as an unbound conflict.
                    if text not in bindings.explicit_indexes:
                        bindings.explicit_indexes.append(text)
                    bindings.normalized_slots.setdefault("index", text)
                    bindings.slot_sources["index"] = SLOT_SOURCE_USER_EXPLICIT
                    bindings.validation_status["index"] = "user_explicit_preserved"
                    continue
            if slot_type == "sourcetype" and raw_value:
                text = str(raw_value).strip()
                if text and text not in bindings.explicit_sourcetypes:
                    bindings.explicit_sourcetypes.append(text)
                    bindings.validation_status["sourcetype"] = "user_explicit_rejected_preserved"
                    bindings.unbound_constraints.append(
                        {
                            "slot": "sourcetype",
                            "value": raw_value,
                            "reason": reason,
                            "source": slot_sources.get(slot_type),
                        }
                    )
                    continue
        bindings.rejected_slots[slot_type] = [reason]
        bindings.unbound_constraints.append(
            {
                "slot": slot_type,
                "value": raw_value,
                "reason": reason,
                "source": slot_sources.get(slot_type),
            }
        )

    for conflict in filter_slot_conflicts(conflicts, merged_raw):
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
    _append_scope_unbound_constraints(bindings, merged_raw, source_profile_slots)
    if source_profile_trace:
        bindings.debug_trace.update(source_profile_trace)
    return bindings


def _append_scope_unbound_constraints(
    bindings: UserConstraintBindings,
    merged_raw: dict[str, Any],
    source_profile_slots: dict[str, Any],
) -> None:
    src_scope = merged_raw.get("src_scope")
    if src_scope == "substation_subnet" and not (
        source_profile_slots.get("substation_mapping_lookup")
        or source_profile_slots.get("approved_source_cidr")
    ):
        if not any(item.get("slot") == "src_scope" for item in bindings.unbound_constraints):
            bindings.unbound_constraints.append(
                {
                    "slot": "src_scope",
                    "value": src_scope,
                    "reason": "missing_source_profile_scope_binding",
                    "source": bindings.slot_sources.get("src_scope"),
                }
            )


def _preserve_user_explicit_indexes(
    bindings: UserConstraintBindings,
    merged_raw: dict[str, Any],
    *,
    slot_sources: dict[str, str],
    allowed_indexes: tuple[str, ...] | None,
    preserve: bool,
) -> None:
    """Bind the user-explicit multi-index slot for review-only drafts.

    Symmetric with single-index preservation: every syntactically valid
    user-specified index renders into the draft, while any index outside the
    deployment allowlist is recorded as an unbound constraint (never silently
    dropped). Drafts remain non-executable, so preserving a not-yet-allowlisted
    index for analyst review does not relax governance. When ``preserve`` is
    false the path fails closed and keeps only allowlisted indexes.
    """
    raw_value = merged_raw.get("indexes")
    if raw_value in (None, "", []):
        return
    if slot_sources.get("indexes") != SLOT_SOURCE_USER_EXPLICIT:
        return
    allowed = {str(idx).strip().lower() for idx in (allowed_indexes or ())}
    values = raw_value if isinstance(raw_value, list) else str(raw_value).split(",")

    preserved: list[str] = []
    not_allowlisted: list[str] = []
    invalid: list[str] = []
    for part in values:
        text = str(part).strip()
        if not text:
            continue
        lowered = text.lower()
        if not _INDEX_PATTERN_OK(text):
            if lowered not in invalid:
                invalid.append(lowered)
            continue
        if allowed and lowered not in allowed:
            if lowered not in not_allowlisted:
                not_allowlisted.append(lowered)
            if not preserve:
                continue
        if lowered not in preserved:
            preserved.append(lowered)

    if preserved:
        bindings.explicit_indexes = list(dict.fromkeys([*bindings.explicit_indexes, *preserved]))
        bindings.normalized_slots["indexes"] = ",".join(bindings.explicit_indexes)
        bindings.slot_sources["indexes"] = SLOT_SOURCE_USER_EXPLICIT
        bindings.validation_status["indexes"] = (
            "user_explicit_partial_preserved" if not_allowlisted else "accepted"
        )

    for lowered in not_allowlisted:
        _append_index_unbound(bindings, lowered, f"slot_index_not_allowlisted:{lowered}")
    for lowered in invalid:
        _append_index_unbound(bindings, lowered, f"slot_pattern_invalid:indexes:{lowered}")


def _append_index_unbound(bindings: UserConstraintBindings, value: str, reason: str) -> None:
    row = {
        "slot": "indexes",
        "value": value,
        "reason": reason,
        "source": SLOT_SOURCE_USER_EXPLICIT,
    }
    if row not in bindings.unbound_constraints:
        bindings.unbound_constraints.append(row)



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
            if _slot_values_equal(merged[slot_type], value, slot_type=slot_type):
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


def _slot_values_equal(left: Any, right: Any, *, slot_type: str | None = None) -> bool:
    return slot_values_semantically_equal(slot_type, left, right)


def _canonical_scope_value(value: Any) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    if text in {"substation_subnet", "substation_subnets"}:
        return "substation_subnet"
    return text


def _llm_entity_slots(advisory: LLMIntentAdvisory | dict[str, Any] | None) -> dict[str, Any]:
    """Extract LLM entity slots regardless of route/use-case adjudication status."""
    if advisory is None:
        return {}
    if isinstance(advisory, LLMIntentAdvisory):
        raw = dict(advisory.entity_slots_candidate or {})
    else:
        raw_candidate = advisory.get("entity_slots_candidate")
        raw = dict(raw_candidate) if isinstance(raw_candidate, dict) else {}
    return normalize_llm_entity_slots(raw)


def normalize_llm_entity_slots(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM advisory slot aliases before precedence merge."""
    return normalize_slot_key_aliases(raw)


def _INDEX_PATTERN_OK(text: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_][a-z0-9_*-]{0,63}", text, re.IGNORECASE))


def _entities_to_slots(entities: QueryEntities) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    if entities.index:
        if len(entities.index) == 1:
            slots["index"] = entities.index[0]
        else:
            slots["indexes"] = list(entities.index)
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
        if len(entities.zone_labels) >= 2:
            slots["src_zone"] = entities.zone_labels[0]
            slots["dest_zone"] = entities.zone_labels[1]
        else:
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

    indexes_val = normalized_slots.get("indexes")
    if indexes_val and is_explicit("indexes"):
        bindings.explicit_indexes = [part.strip() for part in str(indexes_val).split(",") if part.strip()]
    elif normalized_slots.get("index") and is_explicit("index"):
        bindings.explicit_indexes = [normalized_slots["index"]]
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
