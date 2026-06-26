"""Binding-derived SPL output projection and review metadata."""

from __future__ import annotations

from app.spl.numeric_code_filter import numeric_code_aliases
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
    slots = dict(slots or bindings.normalized_slots)
    family = source_family or infer_binding_source_family(bindings, slots)
    required: list[str] = ["_time"]
    table: list[str] = ["_time"]
    eval_lines: list[str] = []

    if bindings.explicit_event_codes or slots.get("event_code"):
        for alias in numeric_code_aliases("event_code"):
            if alias not in required:
                required.append(alias)
        required.append("event_code_norm")
        table.append("event_code_norm")
        eval_lines.append(
            "| eval event_code_norm=tonumber(coalesce(EventCode, EventID, event_code))"
        )

    if bindings.explicit_users or slots.get("user"):
        for alias in ("user", "Account_Name", "TargetUserName", "Target_User_Name", "account", "username"):
            if alias not in required:
                required.append(alias)
        required.append("user_norm")
        table.append("user_norm")
        eval_lines.append(
            '| eval user_norm=lower(coalesce(user, Account_Name, TargetUserName, Target_User_Name, account, ""))'
        )

    src_bound = bool(
        bindings.explicit_src_ips
        or slots.get("src_ip")
        or slots.get("src_scope")
        or slots.get("approved_source_cidr")
        or slots.get("substation_mapping_lookup")
    )
    if src_bound:
        for alias in ("src_ip", "Source_Network_Address", "IpAddress", "source_ip", "src", "source"):
            if alias not in required:
                required.append(alias)
        required.append("src_ip_norm")
        table.append("src_ip_norm")
        eval_lines.append(
            '| eval src_ip_norm=coalesce(src_ip, Source_Network_Address, IpAddress, source_ip, src, source, "")'
        )

    dest_host_bound = bool(bindings.explicit_hosts or slots.get("host")) or family == WINDOWS_LOGON_FAMILY
    if dest_host_bound:
        for alias in ("host", "ComputerName", "dest_host", "dest", "Computer"):
            if alias not in required:
                required.append(alias)
        required.append("dest_host_norm")
        table.append("dest_host_norm")
        eval_lines.append(
            '| eval dest_host_norm=coalesce(host, ComputerName, dest_host, dest, Computer, "")'
        )

    if bindings.explicit_dest_ips or slots.get("dest_ip"):
        for alias in ("dest_ip", "destination", "dest"):
            if alias not in required:
                required.append(alias)
        required.append("dest_ip_norm")
        if "dest_ip_norm" not in table:
            table.append("dest_ip_norm")
        if not any("dest_ip_norm=" in line for line in eval_lines):
            eval_lines.append('| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")')

    direction_bound = bool(
        bindings.explicit_directionality.get("unexpected_ip_direction")
        or slots.get("unexpected_ip_direction")
        or bindings.explicit_allowlist_semantics
        or slots.get("allowlist_semantic")
        or slots.get("approved_destination_cidr")
        or slots.get("approved_destination_lookup")
    )
    if direction_bound:
        for alias in ("src_ip", "src", "source", "source_ip"):
            if alias not in required:
                required.append(alias)
        if "src_ip_norm" not in table:
            required.append("src_ip_norm")
            table.append("src_ip_norm")
        if not any("src_ip_norm=" in line for line in eval_lines):
            eval_lines.append('| eval src_ip_norm=coalesce(src_ip, src, source, source_ip, "")')
        for alias in ("dest_ip", "destination", "dest"):
            if alias not in required:
                required.append(alias)
        if "dest_ip_norm" not in table:
            required.append("dest_ip_norm")
            table.append("dest_ip_norm")
        if not any("dest_ip_norm=" in line for line in eval_lines):
            eval_lines.append('| eval dest_ip_norm=coalesce(dest_ip, dest, destination, "")')
        if "action" not in table:
            table.append("action")

    if bindings.explicit_protocols or slots.get("protocol"):
        required.extend(["protocol", "proto", "protocol_name", "protocol_norm"])
        table.append("protocol_norm")
        eval_lines.append('| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, ""))')

    if bindings.explicit_function_codes or slots.get("function_code"):
        function_field = slots.get("function_code_field") or "function_code"
        for alias in numeric_code_aliases("function_code", primary_field=function_field):
            if alias not in required:
                required.append(alias)
        required.append("function_code_norm")
        table.append("function_code_norm")

    if bindings.explicit_ports or slots.get("port"):
        for alias in ("dest_port", "port", "destination_port"):
            if alias not in required:
                required.append(alias)
        table.append("dest_port_norm")
        eval_lines.append('| eval dest_port_norm=tonumber(coalesce(dest_port, port, destination_port))')

    if bindings.explicit_services or slots.get("service"):
        for alias in ("service", "app", "application"):
            if alias not in required:
                required.append(alias)
        table.append("service_norm")
        eval_lines.append('| eval service_norm=lower(coalesce(service, app, application, ""))')

    if bindings.explicit_src_zones or slots.get("src_zone"):
        for alias in ("src_zone", "src_network", "source_zone"):
            if alias not in required:
                required.append(alias)
        table.append("src_zone")

    if bindings.explicit_dest_zones or slots.get("dest_zone"):
        for alias in ("dest_zone", "dest_network", "destination_zone"):
            if alias not in required:
                required.append(alias)
        table.append("dest_zone")

    if bindings.explicit_action_semantics or slots.get("action_semantic"):
        for alias in ("action", "status", "result"):
            if alias not in required:
                required.append(alias)
        if "action" not in table:
            table.append("action")

    if family == WINDOWS_LOGON_FAMILY:
        for field in ("Logon_Type", "Workstation_Name", "Authentication_Package"):
            if field not in table:
                table.append(field)

    if bindings.explicit_lookups or slots.get("lookup"):
        for alias in ("asset_name", "asset_ip", "src_ip"):
            if alias not in table:
                table.append(alias)

    if "action" not in table and family == FIREWALL_FLOW_FAMILY:
        table.append("action")

    return (
        list(dict.fromkeys(required)),
        list(dict.fromkeys(table)),
        list(dict.fromkeys(eval_lines)),
    )


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
