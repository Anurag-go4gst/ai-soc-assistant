"""Binding-derived SPL output projection and review metadata."""

from __future__ import annotations

from app.spl.user_constraint_bindings import UserConstraintBindings

BindingSourceFamily = str

WINDOWS_LOGON_FAMILY = "windows_logon"
FIREWALL_FLOW_FAMILY = "firewall_flow"
PROTOCOL_COMMAND_FAMILY = "protocol_command"
LOOKUP_CORRELATION_FAMILY = "lookup_correlation"
GENERIC_FAMILY = "generic"


def infer_binding_source_family(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> BindingSourceFamily:
    slots = dict(slots or bindings.normalized_slots)
    if bindings.explicit_event_codes or slots.get("event_code"):
        return WINDOWS_LOGON_FAMILY
    if bindings.explicit_function_codes or slots.get("function_code"):
        return PROTOCOL_COMMAND_FAMILY
    if bindings.explicit_lookups or slots.get("lookup"):
        return LOOKUP_CORRELATION_FAMILY
    if (
        bindings.explicit_action_semantics
        or slots.get("action_semantic")
        or bindings.explicit_ports
        or slots.get("port")
        or bindings.explicit_src_zones
        or bindings.explicit_dest_zones
        or slots.get("src_zone")
        or slots.get("dest_zone")
    ):
        return FIREWALL_FLOW_FAMILY
    index = (bindings.explicit_indexes[0] if bindings.explicit_indexes else slots.get("index") or "").lower()
    sourcetype = (
        bindings.explicit_sourcetypes[0] if bindings.explicit_sourcetypes else slots.get("sourcetype") or ""
    ).lower()
    if "winevent" in index or "security" in sourcetype or "win" in sourcetype:
        return WINDOWS_LOGON_FAMILY
    if any(token in index for token in ("syslog", "cisco_asa", "firewall")):
        return FIREWALL_FLOW_FAMILY
    return GENERIC_FAMILY


def build_output_projection_from_bindings(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
    *,
    source_family: BindingSourceFamily | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Return required event fields, SPL table fields, and pre-where eval lines."""
    # Circular-import exception: final_spl_projection imports family constants from here.
    from app.spl.final_spl_projection import build_output_projection_from_bindings as _delegate

    return _delegate(bindings, slots, source_family=source_family)


def binding_initial_assessment(
    family: BindingSourceFamily,
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> list[str]:
    slots = dict(slots or bindings.normalized_slots)
    if family == WINDOWS_LOGON_FAMILY:
        code = bindings.explicit_event_codes[0] if bindings.explicit_event_codes else slots.get("event_code", "")
        user = bindings.explicit_users[0] if bindings.explicit_users else slots.get("user", "")
        rows = [
            "Review successful or routine Windows logon activity in scope — not confirmed compromise from Event ID alone.",
        ]
        if str(code) == "4624":
            rows.append(
                "Event ID 4624 indicates a successful logon; corroborate with shift hours and approved access paths."
            )
        if user:
            rows.append(f"Validate whether account {user} is expected for the source scope and destination host.")
        return rows
    if family == FIREWALL_FLOW_FAMILY:
        return [
            "Review permitted or denied firewall flows against approved IT-to-OT boundary policy.",
            "Corroborate zone, port, and action with change tickets before treating traffic as suspicious.",
        ]
    if family == PROTOCOL_COMMAND_FAMILY:
        return [
            "Review OT/protocol command activity against approved engineering and maintenance windows.",
            "Corroborate function codes and masters with change records before escalation.",
        ]
    if family == LOOKUP_CORRELATION_FAMILY:
        return [
            "Correlate traffic or hosts against the configured inventory lookup before declaring unmanaged assets.",
        ]
    return [
        "Review the bound search scope against expected operational activity for this source family.",
        "Do not declare compromise from the draft SPL alone.",
    ]


def binding_investigation_checklist(
    family: BindingSourceFamily,
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> list[str]:
    slots = dict(slots or bindings.normalized_slots)
    if family == WINDOWS_LOGON_FAMILY:
        return [
            "Confirm EventCode/EventID field mapping for your wineventlog sourcetype.",
            "Confirm user/account field mapping (user, Account_Name, TargetUserName).",
            "Confirm source IP/subnet mapping (Source_Network_Address, IpAddress, src_ip).",
            "Review destination host/computer and Logon_Type for the matched sessions.",
            "Compare activity with shift hours, approved access, and jump-host or VPN records.",
            "Do not infer compromise from Event ID 4624 alone.",
        ]
    if family == FIREWALL_FLOW_FAMILY:
        return [
            "Confirm firewall index/sourcetype and zone field mappings.",
            "Validate src/dest zones, ports, and permit/deny action semantics.",
            "Compare matches with approved IT-to-OT change windows.",
            "Do not treat permit logs as malicious without corroboration.",
        ]
    if family == PROTOCOL_COMMAND_FAMILY:
        return [
            "Confirm protocol and function-code field mappings.",
            "Validate source/destination IPs against approved OT targets.",
            "Review maintenance tickets for the affected assets.",
        ]
    return [
        "Confirm bound index, sourcetype, and field mappings against your source profile.",
        "Validate placeholder substitutions and any lookup/CIDR bindings before review.",
        "Review draft SPL filters, time window, and result limit before any execution.",
        "Do not declare compromise from this draft alone.",
    ]


def resolved_scope_profile_bindings(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Scope label + source-profile CIDR/lookup pairs shown as resolution, not conflict."""
    slots = dict(slots or bindings.normalized_slots)
    rows: list[dict[str, str]] = []
    src_scope = slots.get("src_scope")
    if src_scope:
        rows.append(
            {
                "slot": "src_scope",
                "value": _scope_display_label(src_scope),
                "source": bindings.slot_sources.get("src_scope", "user_explicit"),
                "semantic_label": "src_scope",
                "resolution": "user_or_llm_extracted_scope_label",
            }
        )
    if slots.get("approved_source_cidr"):
        rows.append(
            {
                "slot": "approved_source_cidr",
                "value": slots["approved_source_cidr"],
                "source": bindings.slot_sources.get("approved_source_cidr", "source_profile"),
                "semantic_label": "approved_source_cidr",
                "resolution": "source_profile_resolved_cidr",
            }
        )
    if slots.get("substation_mapping_lookup"):
        rows.append(
            {
                "slot": "substation_mapping_lookup",
                "value": slots["substation_mapping_lookup"],
                "source": bindings.slot_sources.get("substation_mapping_lookup", "source_profile"),
                "semantic_label": "subnet_scope_cidr",
                "resolution": "source_profile_resolved_lookup",
            }
        )
    return rows


def _scope_display_label(value: str) -> str:
    if value == "substation_subnet":
        return "substation subnets"
    return str(value).replace("_", " ")
