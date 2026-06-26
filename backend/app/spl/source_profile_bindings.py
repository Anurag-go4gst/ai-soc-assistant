"""Source-profile/environment slots for SPL construction.

These bindings are query-construction references, not telemetry evidence. They
feed ``UserConstraintBindings`` at the ``source_profile`` precedence tier so
user-explicit values still win while approved environment knowledge fills blanks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.source_profile_catalog import canonical_source_profile_slot
from app.spl.binding_semantics import enrich_binding_record
from app.spl.source_profile_store import load_persisted_source_profile_document


@dataclass
class SourceProfileBindingResult:
    slots: dict[str, Any] = field(default_factory=dict)
    found: list[dict[str, str]] = field(default_factory=list)
    applied: list[dict[str, str]] = field(default_factory=list)
    missing: list[dict[str, str]] = field(default_factory=list)
    source_profile_lookup_attempted: bool = True
    environment_knowledge_lookup_attempted: bool = True

    def trace(self) -> dict[str, Any]:
        return {
            "source_profile_lookup_attempted": self.source_profile_lookup_attempted,
            "environment_knowledge_lookup_attempted": self.environment_knowledge_lookup_attempted,
            "source_profile_bindings_found": list(self.found),
            "source_profile_bindings_applied": list(self.applied),
            "source_profile_bindings_missing": list(self.missing),
        }


def build_source_profile_binding_slots(
    user_query: str,
    *,
    family_id: str | None = None,
    template_id: str | None = None,
) -> SourceProfileBindingResult:
    document = load_persisted_source_profile_document()
    profile = {
        canonical_source_profile_slot(str(key)): str(value)
        for key, value in (document.get("values") or {}).items()
        if str(value).strip()
    }
    sources = {
        canonical_source_profile_slot(str(key)): str(value)
        for key, value in (document.get("field_sources") or {}).items()
        if str(value).strip()
    }
    result = SourceProfileBindingResult()

    modbus_context = _is_modbus_context(user_query, family_id=family_id, template_id=template_id)
    remote_access_context = _is_remote_access_context(user_query, family_id=family_id)

    if modbus_context:
        _bind(result, profile, sources, "ot_network_index", slot="index")
        _bind(result, profile, sources, "ot_modbus_sourcetype", slot="sourcetype")
        _bind(result, profile, sources, "approved_modbus_targets_lookup", slot="approved_destination_lookup")
        # CIDR is a fallback when no precise approved-target lookup is configured.
        if "approved_destination_lookup" not in result.slots:
            _bind(
                result,
                profile,
                sources,
                "approved_ot_destination_cidr",
                slot="approved_destination_cidr",
                fallback_profile_key="ot_asset_cidr",
            )
        _bind(result, profile, sources, "src_ip_field", slot="src_ip_field")
        _bind(result, profile, sources, "dest_ip_field", slot="dest_ip_field")
        _bind(result, profile, sources, "function_code_field", slot="function_code_field")

    winevent_context = _is_winevent_context(user_query)
    firewall_context = _is_firewall_context(user_query)
    substation_scope_context = _is_substation_scope_context(user_query)

    if winevent_context:
        _bind(result, profile, sources, "windows_security_sourcetype", slot="sourcetype", required=False)
        _bind(result, profile, sources, "windows_index", slot="index", required=False)
        if _is_off_shift_context(user_query):
            _bind(result, profile, sources, "normal_shift_start_hour", slot="normal_shift_start_hour", required=False)
            _bind(result, profile, sources, "normal_shift_end_hour", slot="normal_shift_end_hour", required=False)

    if firewall_context:
        _bind(result, profile, sources, "firewall_index", slot="index", required=False)
        _bind(result, profile, sources, "firewall_sourcetype", slot="sourcetype", required=False)
        _bind(result, profile, sources, "cisco_firewall_sourcetype", slot="sourcetype", required=False)

    if substation_scope_context:
        _bind(result, profile, sources, "substation_mapping_lookup", slot="substation_mapping_lookup", required=False)
        _bind(result, profile, sources, "ot_asset_cidr", slot="approved_source_cidr", required=False)

    if remote_access_context:
        for profile_key, slot in (
            ("firewall_index", "firewall_index"),
            ("firewall_sourcetype", "firewall_sourcetype"),
            ("vpn_index", "vpn_index"),
            ("vpn_sourcetype", "vpn_sourcetype"),
            ("jump_host_index", "jump_host_index"),
            ("jump_host_sourcetype", "jump_host_sourcetype"),
            ("pam_index", "pam_index"),
            ("pam_sourcetype", "pam_sourcetype"),
            ("substation_mapping_lookup", "substation_mapping_lookup"),
            ("external_system_registry_lookup", "external_system_registry_lookup"),
        ):
            _bind(result, profile, sources, profile_key, slot=slot, required=True)

    return result


def _bind(
    result: SourceProfileBindingResult,
    profile: dict[str, str],
    sources: dict[str, str],
    profile_key: str,
    *,
    slot: str,
    required: bool = True,
    fallback_profile_key: str | None = None,
) -> None:
    keys = [canonical_source_profile_slot(profile_key)]
    if fallback_profile_key:
        keys.append(canonical_source_profile_slot(fallback_profile_key))
    for key in keys:
        value = profile.get(key)
        if not value:
            continue
        source = sources.get(key) or "source_profile"
        record = enrich_binding_record(
            {"slot": slot, "profile_key": key, "value": value, "source": source}
        )
        result.slots[slot] = value
        result.found.append(record)
        result.applied.append(record)
        return
    if required:
        result.missing.append(
            {
                "slot": slot,
                "profile_key": canonical_source_profile_slot(profile_key),
                "reason": "missing_source_profile",
            }
        )


def _is_modbus_context(
    user_query: str,
    *,
    family_id: str | None,
    template_id: str | None,
) -> bool:
    text = user_query.lower()
    return (
        "modbus" in text
        or family_id == "scada_dnp3_modbus_write"
        or template_id == "scada_dnp3_modbus_write"
    )


def _is_remote_access_context(user_query: str, *, family_id: str | None) -> bool:
    text = user_query.lower()
    if family_id in {"esp_it_to_ot_connection", "firewall_vendor_vpn_jump"}:
        return True
    return bool(
        re.search(r"\b(remote access|vpn|jump[- ]?host|bastion|pam|external connections?)\b", text)
        and re.search(r"\b(substation|ot|scada|control center|network)\b", text)
    )


def _is_winevent_context(user_query: str) -> bool:
    text = user_query.lower()
    return bool(re.search(r"\bwineventlog\b|\bevent\s*id\s*\d", text))


def _is_firewall_context(user_query: str) -> bool:
    text = user_query.lower()
    return bool(
        re.search(r"\b(syslog|cisco_asa|firewall|permit|permits)\b", text)
        and re.search(r"\b(port|zone|vlan|dmz|traffic)\b", text)
    )


def _is_off_shift_context(user_query: str) -> bool:
    text = (user_query or "").lower()
    return bool(re.search(r"\b(?:outside|after)\s+(?:normal\s+)?shift\s+hours?\b", text)) or bool(
        re.search(r"\boff[\s-]?shift\b|\bafter[\s-]?hours\b", text)
    )


def _is_substation_scope_context(user_query: str) -> bool:
    text = user_query.lower()
    return bool(re.search(r"\bsubstation\s+subnet", text))
