"""Table-driven SPL slot binding for governed templates and lab drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.spl_slot_binding_validator import escape_spl_quoted_string
from app.spl.numeric_code_filter import (
    build_numeric_code_filter,
    numeric_code_aliases,
    split_code_list,
)
from app.spl.final_spl_projection import (
    assemble_skeleton_spl,
    build_final_spl_projection,
    dedupe_spl_eval_lines,
)
from app.spl.t2_constraints import apply_constraints_to_projection, validate_constraint_coverage
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
                "approved_destination_lookup",
                "approved_destination_cidr",
                "src_ip_field",
                "dest_ip_field",
                "function_code_field",
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
                "src_scope",
                "dest_scope",
                "aggregation_subject",
                "cidr",
                "approved_destination_lookup",
                "approved_destination_cidr",
                "src_ip_field",
                "dest_ip_field",
                "function_code_field",
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


def skeleton_output_plan(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return required event log fields and SPL table fields for a user-bound skeleton."""
    slots = dict(slots or bindings.normalized_slots)
    projection = build_final_spl_projection(bindings, slots)
    return projection.required_event_fields, projection.table_fields


def skeleton_eval_lines(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> list[str]:
    slots = dict(slots or bindings.normalized_slots)
    projection = build_final_spl_projection(bindings, slots)
    return projection.eval_lines




def _skeleton_table_clause(table_fields: list[str]) -> str:
    return " ".join(dict.fromkeys(table_fields))


def build_user_bound_skeleton(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
) -> str:
    slots = dict(slots or bindings.normalized_slots)
    projection = build_final_spl_projection(bindings, slots)
    constraints = list(getattr(bindings, "semantic_constraints", None) or [])
    updated = apply_constraints_to_projection(projection, constraints, slots)
    spl = assemble_skeleton_spl(bindings, slots, projection)
    serialized, missing = validate_constraint_coverage(updated, spl)
    bindings.semantic_constraints = serialized
    bindings.missing_constraints = missing
    return spl




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
    sourcetype = slots.get("sourcetype") or (bindings.explicit_sourcetypes[0] if bindings.explicit_sourcetypes else None)
    protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()

    if index:
        spl_text = re.sub(r"index=<[^>]+>", f"index={index}", spl_text, count=1)
    else:
        unbound.append({"slot": "index", "reason": "missing_source_profile"})
    if sourcetype:
        spl_text = re.sub(r"sourcetype=<[^>]+>", f"sourcetype={sourcetype}", spl_text, count=1)

    if protocol == "modbus":
        spl_text = spl_text.replace("(*dnp3* OR *modbus*)", "*modbus*")
        spl_text = re.sub(
            r"\|\s*where\s*\(\s*like\(protocol_norm,\s*\"%dnp3%\"\)\s*OR\s*like\(protocol_norm,\s*\"%modbus%\"\)\s*\)",
            '| where like(protocol_norm, "%modbus%")',
            spl_text,
        )
    elif protocol == "dnp3":
        spl_text = spl_text.replace("(*dnp3* OR *modbus*)", "*dnp3*")

    codes = bindings.explicit_function_codes or split_code_list(slots.get("function_code"))
    if codes:
        function_field = _safe_field(slots.get("function_code_field"), "function_code")
        eval_line, where_clause = build_numeric_code_filter(
            [str(code) for code in codes],
            norm_field="function_code_norm",
            aliases=numeric_code_aliases("function_code", primary_field=function_field),
        )
        command_eval = '| eval command_norm=lower(coalesce(action, command, event_action, function, function_code, ""))'
        spl_text = spl_text.replace(command_eval, f"{command_eval}\n{eval_line}", 1)
        spl_text = re.sub(
            r"AND \(\s*like\(command_norm, \"%write%\"\).*?\)",
            f"AND ({where_clause})",
            spl_text,
            flags=re.DOTALL,
        )

    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or slots.get("unexpected_ip_direction")
    if direction == "destination" or bindings.explicit_allowlist_semantics:
        if slots.get("dest_ip_field"):
            dest_field = _safe_field(slots.get("dest_ip_field"), "dest_ip")
            spl_text = re.sub(
                r"\|\s*eval\s+dest_ip_norm=coalesce\([^\n]+\)",
                f"| eval dest_ip_norm={_coalesce_field_expr(dest_field, ('dest_ip', 'dest', 'destination'))}",
                spl_text,
                count=1,
            )
        if slots.get("src_ip_field"):
            src_field = _safe_field(slots.get("src_ip_field"), "src_ip")
            spl_text = re.sub(
                r"\|\s*eval\s+src_ip_norm=coalesce\([^\n]+\)",
                f"| eval src_ip_norm={_coalesce_field_expr(src_field, ('src_ip', 'src', 'source'))}",
                spl_text,
                count=1,
            )
        if slots.get("approved_destination_lookup"):
            lookup = slots["approved_destination_lookup"]
            spl_text = spl_text.replace(
                'NOT cidrmatch("<engineering_workstation_cidr>", src_ip_norm)',
                f'1=1\n| lookup {lookup} dest_ip as dest_ip_norm OUTPUT dest_ip as approved_dest_ip\n| where isnull(approved_dest_ip)',
            )
        else:
            cidr = slots.get("approved_destination_cidr") or "<approved_ot_destination_cidr>"
            spl_text = spl_text.replace(
                'NOT cidrmatch("<engineering_workstation_cidr>", src_ip_norm)',
                f'NOT cidrmatch("{cidr}", dest_ip_norm)',
            )

    time_bounds = slots.get("time_window")
    if time_bounds:
        spl_text = _apply_time_window(spl_text, time_bounds)

    for slot_name, value in slots.items():
        if slot_name not in spec.accepted_slots and slot_name not in {"indexes"}:
            unbound.append({"slot": slot_name, "value": value, "reason": "unsupported_by_template"})

    return RenderBindingOutcome(spl=dedupe_spl_eval_lines(spl_text.strip()), bound_slots=slots, unbound_constraints=unbound)


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


def _safe_field(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}", text):
        return text
    return fallback


def _coalesce_field_expr(primary: str, fallbacks: tuple[str, ...]) -> str:
    fields: list[str] = []
    for field in (primary, *fallbacks):
        safe = _safe_field(field, "")
        if safe and safe not in fields:
            fields.append(safe)
    return f'coalesce({", ".join(fields)}, "")'


def _function_codes(bindings: UserConstraintBindings, slots: dict[str, str]) -> list[str]:
    if bindings.explicit_function_codes:
        return [str(code) for code in bindings.explicit_function_codes]
    raw = slots.get("function_code")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(code) for code in raw]
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _function_code_terms(
    code: Any,
    function_field: str,
    *,
    include_function: bool = True,
) -> tuple[str, ...]:
    fields = [function_field, "function_code", "modbus_function_code"]
    if include_function:
        fields.append("function")
    unique_fields: list[str] = []
    for field in fields:
        safe = _safe_field(field, "")
        if safe and safe not in unique_fields:
            unique_fields.append(safe)
    return tuple(f'{field}="{code}"' for field in unique_fields)
