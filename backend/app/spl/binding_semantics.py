"""Semantic labels for CIDR/lookup/profile bindings shown to analysts."""

from __future__ import annotations

from typing import Any

# slot or profile_key -> (semantic_label, analyst-facing meaning)
_BINDING_SEMANTICS: dict[str, tuple[str, str]] = {
    "approved_destination_cidr": (
        "approved_destination_cidr",
        "NOT cidrmatch means outside approved destination targets",
    ),
    "approved_ot_destination_cidr": (
        "approved_destination_cidr",
        "NOT cidrmatch means outside approved destination targets",
    ),
    "approved_source_cidr": (
        "approved_source_cidr",
        "NOT cidrmatch means outside approved source scope",
    ),
    "approved_destination_lookup": (
        "approved_target_lookup",
        "Lookup miss means destination is outside approved targets",
    ),
    "approved_modbus_targets_lookup": (
        "approved_target_lookup",
        "Lookup miss means destination is outside approved targets",
    ),
    "lookup": (
        "asset_inventory_lookup",
        "Lookup miss means asset is not in the configured inventory",
    ),
    "substation_mapping_lookup": (
        "subnet_scope_cidr",
        "Substation/network scope mapping for OT boundary review",
    ),
    "external_system_registry_lookup": (
        "asset_inventory_lookup",
        "External-system registry for approved remote-access mapping",
    ),
    "src_ip_field": ("field_mapping", "Source IP field mapping from source profile"),
    "dest_ip_field": ("field_mapping", "Destination IP field mapping from source profile"),
    "function_code_field": ("field_mapping", "Function/status code field mapping from source profile"),
}

_PROFILE_BINDING_SLOTS = frozenset(
    {
        "index",
        "sourcetype",
        "approved_destination_cidr",
        "approved_destination_lookup",
        "approved_source_cidr",
        "lookup",
        "src_ip_field",
        "dest_ip_field",
        "function_code_field",
        "firewall_index",
        "firewall_sourcetype",
        "vpn_index",
        "vpn_sourcetype",
        "jump_host_index",
        "jump_host_sourcetype",
        "pam_index",
        "pam_sourcetype",
        "substation_mapping_lookup",
        "external_system_registry_lookup",
    }
)

_EVENT_FIELD_SLOTS = frozenset(
    {
        "event_code",
        "function_code",
        "user",
        "host",
        "src_ip",
        "dest_ip",
        "src_zone",
        "dest_zone",
        "port",
        "service",
        "protocol",
        "threshold",
    }
)


def semantic_label_for_slot(slot: str) -> str | None:
    entry = _BINDING_SEMANTICS.get(slot)
    return entry[0] if entry else None


def semantic_meaning_for_slot(slot: str) -> str | None:
    entry = _BINDING_SEMANTICS.get(slot)
    return entry[1] if entry else None


def enrich_binding_record(record: dict[str, Any]) -> dict[str, Any]:
    slot = str(record.get("slot") or record.get("profile_key") or "")
    label = semantic_label_for_slot(slot)
    meaning = semantic_meaning_for_slot(slot)
    enriched = dict(record)
    if label:
        enriched["semantic_label"] = label
    if meaning:
        enriched["semantic_meaning"] = meaning
    return enriched


def is_profile_binding_slot(slot: str) -> bool:
    return slot in _PROFILE_BINDING_SLOTS


def is_event_field_slot(slot: str) -> bool:
    return slot in _EVENT_FIELD_SLOTS


def format_profile_binding_line(record: dict[str, Any]) -> str:
    slot = str(record.get("slot") or record.get("profile_key") or "").strip()
    value = str(record.get("value") or "").strip()
    source = str(record.get("source") or "source_profile").strip()
    label = str(record.get("semantic_label") or semantic_label_for_slot(slot) or slot)
    meaning = str(record.get("semantic_meaning") or semantic_meaning_for_slot(slot) or "").strip()
    line = f"- {label}: {value} ({source.replace('_', ' ')})"
    if meaning:
        line += f" — {meaning}"
    return line
