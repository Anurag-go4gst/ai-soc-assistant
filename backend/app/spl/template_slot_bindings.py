"""Table-driven SPL slot binding for governed templates and lab drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.spl_slot_binding_validator import escape_spl_quoted_string
from app.spl.user_constraint_bindings import UserConstraintBindings

_TIME_BOUNDS_RE = re.compile(r"\bearliest=[^\s|]+(?:\s+latest=[^\s|]+)?")
_SERVICE_PORT_MAP = {"smb": 445, "ssh": 22, "rdp": 3389, "dns": 53, "http": 80, "https": 443}


@dataclass(frozen=True)
class TemplateSlotBindingSpec:
    accepted_slots: frozenset[str]
    required_slots: frozenset[str] = frozenset()
    optional_slots: frozenset[str] = frozenset()
    slot_injection_strategy: str = "base_search"


_TEMPLATE_SLOT_SPECS: dict[str, TemplateSlotBindingSpec] = {
    "auth_success_after_failure": TemplateSlotBindingSpec(
        accepted_slots=frozenset({"host", "user", "alert_id", "time_window", "index", "sourcetype"}),
        optional_slots=frozenset({"host", "user", "alert_id", "time_window"}),
    ),
    "scada_dnp3_modbus_write": TemplateSlotBindingSpec(
        accepted_slots=frozenset(
            {
                "index",
                "sourcetype",
                "protocol",
                "function_code",
                "time_window",
                "unexpected_ip_direction",
                "allowlist_semantic",
                "action_semantic",
            }
        ),
        slot_injection_strategy="ot_protocol",
    ),
    "default": TemplateSlotBindingSpec(
        accepted_slots=frozenset(
            {
                "index",
                "indexes",
                "sourcetype",
                "host",
                "user",
                "src_ip",
                "dest_ip",
                "port",
                "protocol",
                "event_code",
                "function_code",
                "time_window",
                "threshold",
                "threshold_comparison",
                "src_zone",
                "dest_zone",
                "service",
                "lookup",
                "action_semantic",
                "unexpected_ip_direction",
                "allowlist_semantic",
                "cidr",
            }
        ),
    ),
}


def accepted_slots_for_template(template_id: str | None) -> frozenset[str]:
    spec = _TEMPLATE_SLOT_SPECS.get(str(template_id or "")) or _TEMPLATE_SLOT_SPECS["default"]
    return spec.accepted_slots


@dataclass
class RenderBindingOutcome:
    spl: str
    bound_slots: dict[str, str] = field(default_factory=dict)
    unbound_constraints: list[dict[str, Any]] = field(default_factory=list)
    used_user_bound_skeleton: bool = False


def render_spl_with_bindings(
    template_id: str,
    spl_text: str,
    bindings: UserConstraintBindings,
    *,
    normalized_slots: dict[str, str] | None = None,
    force_user_skeleton: bool = False,
) -> RenderBindingOutcome:
    slots = dict(normalized_slots or bindings.normalized_slots)
    spec = _TEMPLATE_SLOT_SPECS.get(template_id) or _TEMPLATE_SLOT_SPECS["default"]
    if force_user_skeleton:
        return RenderBindingOutcome(
            spl=build_user_bound_skeleton(bindings, slots),
            bound_slots=slots,
            used_user_bound_skeleton=True,
        )

    if template_id == "auth_success_after_failure":
        return _render_auth_success_after_failure(spl_text, slots, spec)

    if template_id == "scada_dnp3_modbus_write" or _is_ot_modbus_family(template_id, slots):
        return _render_ot_modbus_draft(spl_text, bindings, slots, spec)

    return _render_generic_search(spl_text, slots, spec)


def customize_template_spl_with_bindings(
    template_id: str,
    spl_text: str,
    bindings: UserConstraintBindings,
    *,
    normalized_slots: dict[str, str] | None = None,
) -> RenderBindingOutcome:
    slots = dict(normalized_slots or bindings.normalized_slots)
    time_bounds = slots.get("time_window")
    if template_id == "auth_success_after_failure":
        outcome = render_spl_with_bindings(template_id, spl_text, bindings, normalized_slots=slots)
        return outcome
    if time_bounds:
        spl_text = _apply_time_window(spl_text, time_bounds)
    outcome = render_spl_with_bindings(template_id, spl_text, bindings, normalized_slots=slots)
    return outcome


def build_user_bound_skeleton(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> str:
    slots = dict(slots or bindings.normalized_slots)
    indexes = bindings.explicit_indexes or ([slots["index"]] if slots.get("index") else ["*"])
    index_clause = " OR ".join(f"index={idx}" for idx in indexes)
    time_bounds = slots.get("time_window") or bindings.explicit_time_window or "earliest=-24h latest=now"
    base = f"search ({index_clause}) {time_bounds}"

    filters: list[str] = []
    if bindings.explicit_protocols or slots.get("protocol"):
        protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()
        filters.append(f'like(lower(coalesce(protocol, proto, protocol_name, "")), "%{protocol}%")')
    if bindings.explicit_function_codes or slots.get("function_code"):
        codes = _function_codes(bindings, slots)
        code_terms = " OR ".join(
            f'function_code="{c}" OR modbus_function_code="{c}" OR function="{c}"' for c in codes
        )
        filters.append(f"({code_terms})")
    if bindings.explicit_event_codes or slots.get("event_code"):
        code = str(bindings.explicit_event_codes[0] if bindings.explicit_event_codes else slots.get("event_code"))
        filters.append(f'(EventCode={code} OR EventID={code})')
    if bindings.explicit_users or slots.get("user"):
        user = bindings.explicit_users[0] if bindings.explicit_users else slots["user"]
        filters.append(f'user="{user}"')
    if bindings.explicit_hosts or slots.get("host"):
        host = bindings.explicit_hosts[0] if bindings.explicit_hosts else slots["host"]
        filters.append(f'host="{host}"')
    if bindings.explicit_src_ips or slots.get("src_ip"):
        ip = bindings.explicit_src_ips[0] if bindings.explicit_src_ips else slots["src_ip"]
        filters.append(f'src_ip="{ip}"')
    if bindings.explicit_dest_ips or slots.get("dest_ip"):
        ip = bindings.explicit_dest_ips[0] if bindings.explicit_dest_ips else slots["dest_ip"]
        filters.append(f'dest_ip="{ip}"')
    if bindings.explicit_ports or slots.get("port"):
        port = bindings.explicit_ports[0] if bindings.explicit_ports else int(slots["port"])
        filters.append(f"dest_port={port}")
    if bindings.explicit_services or slots.get("service"):
        service = (bindings.explicit_services[0] if bindings.explicit_services else slots.get("service", "")).lower()
        port = _SERVICE_PORT_MAP.get(service)
        if port:
            filters.append(f"(dest_port={port} OR service=\"{service}\")")
        else:
            filters.append(f'service="{service}"')
    if bindings.explicit_src_zones or slots.get("src_zone"):
        zone = bindings.explicit_src_zones[0] if bindings.explicit_src_zones else slots["src_zone"]
        filters.append(f'src_zone="{zone}"')
    if bindings.explicit_dest_zones or slots.get("dest_zone"):
        zone = bindings.explicit_dest_zones[0] if bindings.explicit_dest_zones else slots["dest_zone"]
        filters.append(f'dest_zone="{zone}"')
    if bindings.explicit_action_semantics or slots.get("action_semantic"):
        action = bindings.explicit_action_semantics[0] if bindings.explicit_action_semantics else slots["action_semantic"]
        filters.append(f'like(lower(coalesce(action, status, result, "")), "%{action}%")')
    if bindings.explicit_thresholds.get("threshold") or slots.get("threshold"):
        threshold = bindings.explicit_thresholds.get("threshold") or slots.get("threshold")
        comparison = bindings.explicit_thresholds.get("comparison") or slots.get("threshold_comparison") or "greater_than"
        op = ">" if comparison in {"greater_than", "more_than", "gt"} else ">="
        return (
            f"{base} | stats count by user | where count {op} {threshold} | sort - count | head 100"
        )
    if bindings.explicit_lookups or slots.get("lookup"):
        lookup = bindings.explicit_lookups[0] if bindings.explicit_lookups else slots["lookup"]
        return (
            f"{base} | lookup {lookup} asset_ip OUTPUT asset_name | where isnull(asset_name) "
            f"| table _time src_ip dest_ip asset_name | head 100"
        )

    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or slots.get("unexpected_ip_direction")
    allowlist = bindings.explicit_allowlist_semantics.get("allowlist_semantic") or slots.get("allowlist_semantic")
    if allowlist or direction == "destination":
        lookup_placeholder = "<approved_ot_destination_allowlist>"
        filters.append(
            f"NOT cidrmatch(\"{lookup_placeholder}\", coalesce(dest_ip, dest, destination, \"\"))"
        )

    where_clause = " AND ".join(filters) if filters else "1=1"
    return f"{base} | where {where_clause} | table _time src_ip dest_ip protocol function_code action | head 100"


def _render_auth_success_after_failure(
    base_spl: str,
    slots: dict[str, str],
    spec: TemplateSlotBindingSpec,
) -> RenderBindingOutcome:
    alert_id = slots.get("alert_id")
    host = slots.get("host")
    time_bounds = slots.get("time_window") or _extract_time_bounds(base_spl) or "earliest=-60m latest=now"
    index = slots.get("index", "pgcil_soc")
    sourcetype = slots.get("sourcetype", "pgcil:auth")

    search_prefix = f"search index={index} sourcetype={sourcetype}"
    if alert_id:
        search_prefix = f'{search_prefix} alert_id="{alert_id}"'
    if host:
        search_prefix = f'{search_prefix} host="{host}"'
    search_prefix = f"{search_prefix} {time_bounds}"

    remainder = re.sub(
        r"^search\s+index=\S+\s+sourcetype=\S+(?:\s+\S+)*?\s+",
        "",
        base_spl,
        count=1,
    )
    remainder = re.sub(r"^earliest=[^\s|]+(?:\s+latest=[^\s|]+)?\s+", "", remainder, count=1)
    return RenderBindingOutcome(spl=f"{search_prefix} {remainder}".strip(), bound_slots=slots)


def _render_ot_modbus_draft(
    spl_text: str,
    bindings: UserConstraintBindings,
    slots: dict[str, str],
    spec: TemplateSlotBindingSpec,
) -> RenderBindingOutcome:
    unbound: list[dict[str, Any]] = []
    index = slots.get("index") or (bindings.explicit_indexes[0] if bindings.explicit_indexes else None)
    protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()

    if index:
        spl_text = re.sub(r"index=<[^>]+>", f"index={index}", spl_text, count=1)
    else:
        unbound.append({"slot": "index", "reason": "missing_source_profile"})

    if protocol == "modbus":
        spl_text = spl_text.replace("(*dnp3* OR *modbus*)", "*modbus*")
        spl_text = re.sub(
            r"\|\s*where\s*\(\s*like\(protocol_norm,\s*\"%dnp3%\"\)\s*OR\s*like\(protocol_norm,\s*\"%modbus%\"\)\s*\)",
            '| where like(protocol_norm, "%modbus%")',
            spl_text,
        )
    elif protocol == "dnp3":
        spl_text = spl_text.replace("(*dnp3* OR *modbus*)", "*dnp3*")

    codes = bindings.explicit_function_codes or _as_list(slots.get("function_code"))
    if codes:
        code_filter = " OR ".join(
            f'command_norm="{c}" OR function_code="{c}" OR modbus_function_code="{c}"' for c in codes
        )
        spl_text = re.sub(
            r"AND \(\s*like\(command_norm, \"%write%\"\).*?\)",
            f"AND ({code_filter})",
            spl_text,
            flags=re.DOTALL,
        )

    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or slots.get("unexpected_ip_direction")
    if direction == "destination" or bindings.explicit_allowlist_semantics:
        spl_text = spl_text.replace(
            'NOT cidrmatch("<engineering_workstation_cidr>", src_ip_norm)',
            'NOT cidrmatch("<approved_ot_destination_allowlist>", dest_ip_norm)',
        )

    time_bounds = slots.get("time_window")
    if time_bounds:
        spl_text = _apply_time_window(spl_text, time_bounds)

    for slot_name, value in slots.items():
        if slot_name not in spec.accepted_slots and slot_name not in {"indexes"}:
            unbound.append({"slot": slot_name, "value": value, "reason": "unsupported_by_template"})

    return RenderBindingOutcome(spl=spl_text.strip(), bound_slots=slots, unbound_constraints=unbound)


def _render_generic_search(
    spl_text: str,
    slots: dict[str, str],
    spec: TemplateSlotBindingSpec,
) -> RenderBindingOutcome:
    unbound: list[dict[str, Any]] = []
    result = spl_text
    if slots.get("index"):
        result = re.sub(r"index=\S+", f"index={slots['index']}", result, count=1)
    if slots.get("sourcetype"):
        result = re.sub(r"sourcetype=\S+", f"sourcetype={slots['sourcetype']}", result, count=1)
    if slots.get("time_window"):
        result = _apply_time_window(result, slots["time_window"])
    for slot_name, value in slots.items():
        if slot_name in {"index", "sourcetype", "time_window"}:
            continue
        if slot_name not in spec.accepted_slots:
            unbound.append({"slot": slot_name, "value": value, "reason": "unsupported_by_template"})
    return RenderBindingOutcome(spl=result, bound_slots=slots, unbound_constraints=unbound)


def _is_ot_modbus_family(template_id: str, slots: dict[str, str]) -> bool:
    return template_id == "scada_dnp3_modbus_write" or (
        slots.get("protocol", "").lower() == "modbus" and "scada" in template_id
    )


def _apply_time_window(spl_text: str, time_bounds: str) -> str:
    if _TIME_BOUNDS_RE.search(spl_text):
        return _TIME_BOUNDS_RE.sub(time_bounds, spl_text, count=1)
    match = re.search(r"^(search\s+index=\S+(?:\s+sourcetype=\S+)?)", spl_text, flags=re.IGNORECASE)
    if match:
        prefix = match.group(1)
        remainder = spl_text[match.end() :].lstrip()
        return f"{prefix} {time_bounds} {remainder}".strip()
    return spl_text


def _extract_time_bounds(spl_text: str) -> str | None:
    match = _TIME_BOUNDS_RE.search(spl_text)
    return match.group(0).strip() if match else None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _function_codes(bindings: UserConstraintBindings, slots: dict[str, str]) -> list[str]:
    if bindings.explicit_function_codes:
        return [str(code) for code in bindings.explicit_function_codes]
    raw = slots.get("function_code")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(code) for code in raw]
    return [part.strip() for part in str(raw).split(",") if part.strip()]
