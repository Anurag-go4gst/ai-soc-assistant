"""Binding-derived draft metadata for lab SPL previews.

When user-bound skeletons or incompatible/partially customized families are used,
visible assumptions, required fields, scope, and checklist must not leak stale text
from the nearest generic template family.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

from app.spl.template_compatibility import TemplateCompatibilityResult
from app.spl.binding_semantics import (
    is_profile_binding_slot,
    semantic_label_for_slot,
    semantic_meaning_for_slot,
)
from app.spl.output_projection import (
    binding_initial_assessment,
    binding_investigation_checklist,
    build_output_projection_from_bindings,
    infer_binding_source_family,
    resolved_scope_profile_bindings,
)
from app.spl.template_slot_bindings import skeleton_output_plan
from app.spl.user_constraint_bindings import UserConstraintBindings


def bindings_from_dict(data: dict[str, Any]) -> UserConstraintBindings:
    known = {item.name for item in fields(UserConstraintBindings)}
    return UserConstraintBindings(
        **{key: value for key, value in data.items() if key in known}
    )

_GENERATION_USER_BOUND_SKELETON = "user_bound_skeleton"
_GENERATION_PARTIAL_CUSTOM = "partial_custom_draft"

_GENERIC_CHECKLIST: tuple[str, ...] = (
    "Confirm bound index, sourcetype, and field mappings against your source profile.",
    "Validate placeholder substitutions and any lookup/CIDR bindings before review.",
    "Review draft SPL filters, time window, and result limit before any execution.",
    "Compare any matches with approved change or maintenance activity.",
    "Escalate only after required evidence is collected and documented.",
    "Do not declare compromise from this draft alone.",
)

_SLOT_REQUIRED_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "index": ("index",),
    "sourcetype": ("sourcetype",),
    "event_code": ("EventCode", "EventID", "event_code"),
    "function_code": ("function_code", "modbus_function_code", "function"),
    "user": ("user", "username", "account", "src_user"),
    "host": ("host", "dest_host", "device", "hostname"),
    "src_ip": ("src_ip", "source", "src"),
    "dest_ip": ("dest_ip", "destination", "dest"),
    "src_zone": ("src_zone", "src_network", "source_zone"),
    "dest_zone": ("dest_zone", "dest_network", "destination_zone"),
    "port": ("dest_port", "port", "destination_port"),
    "service": ("service", "app", "application"),
    "protocol": ("protocol", "proto", "protocol_name"),
    "threshold": ("count", "threshold"),
}


@dataclass
class DraftMetadata:
    assumptions: list[str] = field(default_factory=list)
    required_event_fields: list[str] = field(default_factory=list)
    required_log_fields: list[str] = field(default_factory=list)
    required_source_fields: list[str] = field(default_factory=list)
    required_source_profile_fields: list[str] = field(default_factory=list)
    required_source_profile_bindings: list[dict[str, str]] = field(default_factory=list)
    investigation_checklist: list[str] = field(default_factory=list)
    initial_assessment: list[str] = field(default_factory=list)
    binding_source_family: str = ""
    scope_notice: str = ""
    generation_mode: str | None = None
    metadata_source: str = "template_derived"
    stale_template_metadata_suppressed: bool = False
    trace: dict[str, Any] = field(default_factory=dict)


def needs_binding_derived_metadata(
    *,
    customization_meta: dict[str, Any],
    compatibility: TemplateCompatibilityResult | dict[str, Any] | None,
) -> bool:
    compat = _compat_dict(compatibility)
    if customization_meta.get("used_user_bound_skeleton"):
        return True
    if customization_meta.get("partial_customization"):
        return True
    if compat.get("use_user_bound_skeleton") and customization_meta.get("used_user_bound_skeleton"):
        return True
    return False


def build_draft_metadata(
    *,
    user_query: str,
    bindings: UserConstraintBindings,
    family_id: str | None,
    compatibility: TemplateCompatibilityResult | dict[str, Any] | None,
    customization_meta: dict[str, Any],
    time_window_label: str | None = None,
) -> DraftMetadata:
    del user_query
    compat = _compat_dict(compatibility)
    bound_slots = dict(bindings.normalized_slots)
    used_skeleton = bool(
        customization_meta.get("used_user_bound_skeleton") or compat.get("use_user_bound_skeleton")
    )
    if not needs_binding_derived_metadata(
        customization_meta=customization_meta,
        compatibility=compatibility,
    ):
        return DraftMetadata(metadata_source="template_derived")

    assumptions = _binding_assumptions(
        bindings,
        bound_slots,
        compat,
        time_window_label=time_window_label,
        used_skeleton=used_skeleton,
    )
    source_family = infer_binding_source_family(bindings, bound_slots)
    if used_skeleton:
        required_event_fields, _skeleton_table_fields, _eval_lines = build_output_projection_from_bindings(
            bindings, bound_slots, source_family=source_family
        )
    else:
        required_event_fields, _, _eval_lines = build_output_projection_from_bindings(
            bindings, bound_slots, source_family=source_family
        )
    required_profile_fields = _required_profile_bindings(customization_meta, bound_slots, bindings)
    required_profile_fields = _merge_resolved_scope_bindings(required_profile_fields, bindings, bound_slots)
    checklist = binding_investigation_checklist(source_family, bindings, bound_slots)
    initial_assessment = binding_initial_assessment(source_family, bindings, bound_slots)
    scope = _scope_notice(bindings, family_id, compat, used_skeleton=used_skeleton)
    trace = _metadata_trace(
        bindings=bindings,
        bound_slots=bound_slots,
        compat=compat,
        customization_meta=customization_meta,
        family_id=family_id,
        used_skeleton=used_skeleton,
    )
    generation_mode = _GENERATION_USER_BOUND_SKELETON if used_skeleton else _GENERATION_PARTIAL_CUSTOM
    return DraftMetadata(
        assumptions=assumptions,
        required_event_fields=required_event_fields,
        required_log_fields=required_event_fields,
        required_source_fields=list(
            dict.fromkeys(required_event_fields + [item['slot'] for item in required_profile_fields])
        ),
        required_source_profile_fields=[item['slot'] for item in required_profile_fields],
        required_source_profile_bindings=required_profile_fields,
        investigation_checklist=list(checklist),
        initial_assessment=list(initial_assessment),
        binding_source_family=source_family,
        scope_notice=scope,
        generation_mode=generation_mode,
        metadata_source="binding_derived",
        stale_template_metadata_suppressed=True,
        trace=trace,
    )


def apply_draft_metadata_to_preview(
    preview: dict[str, Any],
    metadata: DraftMetadata,
) -> dict[str, Any]:
    if metadata.metadata_source != "binding_derived":
        return preview
    updated = dict(preview)
    updated["assumptions"] = list(metadata.assumptions)
    updated["required_event_fields"] = list(metadata.required_event_fields)
    updated["required_log_fields"] = list(metadata.required_event_fields)
    updated["required_source_fields"] = list(metadata.required_source_fields)
    updated["required_source_profile_fields"] = list(metadata.required_source_profile_fields)
    updated["required_source_profile_bindings"] = list(metadata.required_source_profile_bindings)
    updated["investigation_checklist"] = list(metadata.investigation_checklist)
    updated["initial_assessment"] = list(metadata.initial_assessment)
    updated["binding_source_family"] = metadata.binding_source_family
    updated["scope_notice"] = metadata.scope_notice
    if metadata.generation_mode:
        updated["generation_mode"] = metadata.generation_mode
    updated.update(metadata.trace)
    if metadata.stale_template_metadata_suppressed:
        updated["stale_template_metadata_suppressed"] = True
        updated["metadata_source"] = metadata.metadata_source
    return updated


def _compat_dict(compatibility: TemplateCompatibilityResult | dict[str, Any] | None) -> dict[str, Any]:
    if compatibility is None:
        return {}
    if isinstance(compatibility, TemplateCompatibilityResult):
        return compatibility.to_dict()
    return dict(compatibility)




def _sanitize_incompatible_reasons(reasons: list[str]) -> list[str]:
    rows: list[str] = []
    for reason in reasons:
        if reason.startswith("broadens_protocol_without_request:"):
            rows.append("Selected template would broaden protocol scope beyond the user request.")
        elif reason.startswith("replaces_user_index:"):
            rows.append("Selected template would replace the user-specified index.")
        elif reason == "drops_explicit_function_codes":
            rows.append("Selected template would drop explicit function/status codes.")
        elif reason.startswith("drops_explicit_event_code:"):
            rows.append("Selected template would drop explicit event codes.")
        elif reason == "reverses_unexpected_ip_direction":
            rows.append("Selected template would reverse unexpected-IP direction semantics.")
        else:
            rows.append(reason.replace("_", " "))
    return list(dict.fromkeys(rows))


def _binding_assumptions(
    bindings: UserConstraintBindings,
    bound_slots: dict[str, str],
    compat: dict[str, Any],
    *,
    time_window_label: str | None,
    used_skeleton: bool,
) -> list[str]:
    rows: list[str] = []
    if bindings.explicit_indexes or bound_slots.get("index"):
        index = bindings.explicit_indexes[0] if bindings.explicit_indexes else bound_slots.get("index")
        source = bindings.slot_sources.get("index", "bound")
        rows.append(f"Search scope uses index={index} ({source.replace('_', ' ')}).")
    if bindings.explicit_protocols or bound_slots.get("protocol"):
        protocol = (
            bindings.explicit_protocols[0] if bindings.explicit_protocols else bound_slots.get("protocol", "")
        ).lower()
        rows.append(f"Protocol filter is limited to {protocol}; unrelated protocols are excluded.")
    if bindings.explicit_function_codes or bound_slots.get("function_code"):
        codes = bindings.explicit_function_codes or [bound_slots.get("function_code")]
        rows.append(
            "Function/status codes preserved: "
            + ", ".join(str(code) for code in codes if code is not None)
            + "."
        )
    if bindings.explicit_event_codes or bound_slots.get("event_code"):
        code = bindings.explicit_event_codes[0] if bindings.explicit_event_codes else bound_slots.get("event_code")
        rows.append(f"Event code filter uses EventCode/EventID={code}.")
    if bindings.explicit_users or bound_slots.get("user"):
        user = bindings.explicit_users[0] if bindings.explicit_users else bound_slots.get("user")
        rows.append(f"User/account filter uses {user}.")
    if bindings.explicit_hosts or bound_slots.get("host"):
        host = bindings.explicit_hosts[0] if bindings.explicit_hosts else bound_slots.get("host")
        rows.append(f"Host/device filter uses {host}.")
    if bindings.explicit_src_ips or bound_slots.get("src_ip"):
        ip = bindings.explicit_src_ips[0] if bindings.explicit_src_ips else bound_slots.get("src_ip")
        rows.append(f"Source IP filter uses {ip}.")
    if bindings.explicit_dest_ips or bound_slots.get("dest_ip"):
        ip = bindings.explicit_dest_ips[0] if bindings.explicit_dest_ips else bound_slots.get("dest_ip")
        rows.append(f"Destination IP filter uses {ip}.")
    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or bound_slots.get(
        "unexpected_ip_direction"
    )
    if direction:
        rows.append(f"Unexpected-IP semantics apply to {direction} addresses.")
    if bound_slots.get("approved_destination_lookup"):
        label = semantic_label_for_slot("approved_destination_lookup") or "approved_target_lookup"
        meaning = semantic_meaning_for_slot("approved_destination_lookup") or ""
        rows.append(
            f"{label} uses lookup {bound_slots['approved_destination_lookup']}"
            + (f" — {meaning}" if meaning else "")
            + "."
        )
    elif bound_slots.get("approved_destination_cidr"):
        label = semantic_label_for_slot("approved_destination_cidr") or "approved_destination_cidr"
        meaning = semantic_meaning_for_slot("approved_destination_cidr") or ""
        rows.append(
            f"{label} uses CIDR {bound_slots['approved_destination_cidr']}"
            + (f" — {meaning}" if meaning else "")
            + "."
        )
    elif bindings.explicit_allowlist_semantics:
        rows.append("Allowlist semantics require analyst-approved lookup or CIDR binding.")
    if bindings.explicit_lookups or bound_slots.get("lookup"):
        lookup = bindings.explicit_lookups[0] if bindings.explicit_lookups else bound_slots.get("lookup")
        label = semantic_label_for_slot("lookup") or "asset_inventory_lookup"
        meaning = semantic_meaning_for_slot("lookup") or ""
        rows.append(
            f"{label} uses {lookup}" + (f" — {meaning}" if meaning else "") + "."
        )
    if bindings.explicit_thresholds.get("threshold") or bound_slots.get("threshold"):
        threshold = bindings.explicit_thresholds.get("threshold") or bound_slots.get("threshold")
        rows.append(f"Threshold filter uses count > {threshold}.")
    if bindings.explicit_time_window or bound_slots.get("time_window"):
        label = time_window_label or bindings.explicit_time_window or bound_slots.get("time_window")
        rows.append(f"Time window: {label}.")
    else:
        rows.append("Time window: defaulted to last 24 hours.")
    if used_skeleton and compat.get("incompatible_reasons"):
        sanitized = _sanitize_incompatible_reasons(list(compat["incompatible_reasons"]))
        rows.append(
            "Template family was bypassed because it would erase explicit user constraints: "
            + "; ".join(sanitized)
            + "."
        )
    elif used_skeleton:
        rows.append("Rendered from a user-bound skeleton because the selected family was incompatible.")
    rows.append("Lab-only draft — not governed, not approved, and not executed.")
    return rows


def _required_event_fields_from_bindings(
    bindings: UserConstraintBindings,
    bound_slots: dict[str, str],
) -> list[str]:
    fields: list[str] = []
    slot_keys: list[str] = []
    if bindings.explicit_event_codes or bound_slots.get("event_code"):
        slot_keys.append("event_code")
    if bindings.explicit_function_codes or bound_slots.get("function_code"):
        slot_keys.append("function_code")
    if bindings.explicit_users or bound_slots.get("user"):
        slot_keys.append("user")
    if bindings.explicit_hosts or bound_slots.get("host"):
        slot_keys.append("host")
    if bindings.explicit_src_ips or bound_slots.get("src_ip"):
        slot_keys.append("src_ip")
    if bindings.explicit_dest_ips or bound_slots.get("dest_ip"):
        slot_keys.append("dest_ip")
    if bindings.explicit_src_zones or bound_slots.get("src_zone"):
        slot_keys.append("src_zone")
    if bindings.explicit_dest_zones or bound_slots.get("dest_zone"):
        slot_keys.append("dest_zone")
    if bindings.explicit_ports or bound_slots.get("port"):
        slot_keys.append("port")
    if bindings.explicit_services or bound_slots.get("service"):
        slot_keys.append("service")
    if bindings.explicit_protocols or bound_slots.get("protocol"):
        slot_keys.append("protocol")
    if bindings.explicit_thresholds.get("threshold") or bound_slots.get("threshold"):
        slot_keys.append("threshold")

    for slot in slot_keys:
        for alias in _SLOT_REQUIRED_FIELD_ALIASES.get(slot, (slot,)):
            if alias not in fields:
                fields.append(alias)
    return fields


def _required_profile_bindings(
    customization_meta: dict[str, Any],
    bound_slots: dict[str, str],
    bindings: UserConstraintBindings,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in customization_meta.get("source_profile_bindings_applied") or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        if not slot or slot in seen:
            continue
        seen.add(slot)
        rows.append(
            {
                "slot": slot,
                "value": str(item.get("value") or bound_slots.get(slot) or ""),
                "source": str(item.get("source") or "source_profile"),
                "semantic_label": str(
                    item.get("semantic_label") or semantic_label_for_slot(slot) or slot
                ),
            }
        )
    for slot, value in bound_slots.items():
        if slot in seen or not is_profile_binding_slot(slot):
            continue
        if bindings.slot_sources.get(slot) == "user_explicit" and slot in {"index", "sourcetype"}:
            continue
        if not value:
            continue
        seen.add(slot)
        rows.append(
            {
                "slot": slot,
                "value": str(value),
                "source": str(bindings.slot_sources.get(slot) or "source_profile"),
                "semantic_label": str(semantic_label_for_slot(slot) or slot),
            }
        )
    return rows



def _merge_resolved_scope_bindings(
    required_profile_fields: list[dict[str, str]],
    bindings: UserConstraintBindings,
    bound_slots: dict[str, str],
) -> list[dict[str, str]]:
    rows = list(required_profile_fields)
    seen = {str(item.get("slot")) for item in rows if isinstance(item, dict) and item.get("slot")}
    for item in resolved_scope_profile_bindings(bindings, bound_slots):
        slot = str(item.get("slot") or "")
        if not slot or slot in seen:
            continue
        rows.append(dict(item))
        seen.add(slot)
    return rows

def _scope_notice(
    bindings: UserConstraintBindings,
    family_id: str | None,
    compat: dict[str, Any],
    *,
    used_skeleton: bool,
) -> str:
    if used_skeleton:
        return (
            "Scope: Review-only user-bound SPL draft generated from validated query constraints; "
            "no governed template is authoritative and nothing was executed."
        )
    if family_id in {"esp_it_to_ot_connection", "firewall_vendor_vpn_jump"}:
        return (
            "Scope: IT-to-OT / remote-access review draft using bound firewall, VPN, jump-host, "
            "or PAM source-profile slots where configured."
        )
    if bindings.explicit_protocols:
        protocol = bindings.explicit_protocols[0]
        return (
            f"Scope: Review-only {protocol} hunt draft bound to explicit user constraints; "
            "validate source profile mappings before review."
        )
    if compat.get("compatible") is False:
        return (
            "Scope: Review-only partially customized draft; incompatible template metadata was suppressed."
        )
    return (
        "Scope: Review-only SPL draft for the requested query; validate source profile bindings before review."
    )


def _metadata_trace(
    *,
    bindings: UserConstraintBindings,
    bound_slots: dict[str, str],
    compat: dict[str, Any],
    customization_meta: dict[str, Any],
    family_id: str | None,
    used_skeleton: bool,
) -> dict[str, Any]:
    return {
        "generation_mode": _GENERATION_USER_BOUND_SKELETON if used_skeleton else _GENERATION_PARTIAL_CUSTOM,
        "user_bound_skeleton": used_skeleton,
        "template_compatibility_decision": compat,
        "selected_template_family": family_id,
        "accepted_slots": sorted(bound_slots.keys()),
        "bound_slots": dict(bound_slots),
        "source_profile_bindings_applied": list(
            customization_meta.get("source_profile_bindings_applied") or []
        ),
        "rejected_slots": dict(bindings.rejected_slots),
        "unbound_constraints": list(bindings.unbound_constraints)
        + list(customization_meta.get("unbound_constraints") or []),
        "metadata_source": "binding_derived",
        "stale_template_metadata_suppressed": True,
    }
