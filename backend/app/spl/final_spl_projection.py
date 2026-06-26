"""Unified final SPL projection and skeleton assembly."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.numeric_code_filter import (
    build_numeric_code_filter,
    numeric_code_aliases,
    split_code_list,
)
from app.spl.output_projection import (
    FIREWALL_FLOW_FAMILY,
    GENERIC_FAMILY,
    LOOKUP_CORRELATION_FAMILY,
    PROTOCOL_COMMAND_FAMILY,
    WINDOWS_LOGON_FAMILY,
    BindingSourceFamily,
    binding_initial_assessment,
    binding_investigation_checklist,
    infer_binding_source_family,
)
from app.spl.user_constraint_bindings import UserConstraintBindings

_SERVICE_PORT_MAP = {"smb": 445, "ssh": 22, "rdp": 3389, "dns": 53, "http": 80, "https": 443}
_EVAL_TARGET_RE = re.compile(r"\|\s*eval\s+(\w+)=", re.IGNORECASE)
_COALESCE_ARGS_RE = re.compile(r"coalesce\(([^)]+)\)", re.IGNORECASE)
_SPL_EVAL_LINE_RE = re.compile(r"\|\s*eval\s+[^|]+", re.IGNORECASE)


@dataclass
class FinalSplProjection:
    eval_lines: list[str] = field(default_factory=list)
    where_clauses: list[str] = field(default_factory=list)
    table_fields: list[str] = field(default_factory=list)
    required_event_fields: list[str] = field(default_factory=list)
    initial_assessment: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    lookup_spl: str | None = None
    threshold_spl: str | None = None
    destination_lookup_spl: str | None = None


def _eval_target_field(line: str) -> str | None:
    match = _EVAL_TARGET_RE.search(line)
    return match.group(1) if match else None


def _coalesce_alias_count(line: str) -> int:
    match = _COALESCE_ARGS_RE.search(line)
    if not match:
        return 0
    return len([part.strip() for part in match.group(1).split(",") if part.strip() and part.strip() != '""'])


def dedupe_eval_lines(eval_lines: list[str]) -> list[str]:
    """Drop duplicate eval targets, keeping the line with the richest coalesce alias list."""
    seen_fields: dict[str, int] = {}
    result: list[str] = []
    for line in eval_lines:
        target = _eval_target_field(line)
        if target is None:
            if line not in result:
                result.append(line)
            continue
        count = _coalesce_alias_count(line)
        if target not in seen_fields:
            seen_fields[target] = len(result)
            result.append(line)
        elif count > _coalesce_alias_count(result[seen_fields[target]]):
            result[seen_fields[target]] = line
    return result


def dedupe_spl_eval_lines(spl: str) -> str:
    """Remove duplicate eval lines from rendered SPL, keeping richer coalesce variants."""
    matches = list(_SPL_EVAL_LINE_RE.finditer(spl))
    if not matches:
        return spl
    eval_lines = [match.group(0).strip() for match in matches]
    deduped = dedupe_eval_lines(eval_lines)
    if len(deduped) == len(eval_lines) and all(left == right for left, right in zip(deduped, eval_lines)):
        return spl
    without_eval = _SPL_EVAL_LINE_RE.sub("", spl)
    without_eval = re.sub(r"\s{2,}", " ", without_eval).strip()
    search_end = re.search(
        r"(?:earliest=[^\s|]+(?:\s+latest=[^\s|]+)?)",
        without_eval,
        flags=re.IGNORECASE,
    )
    if search_end:
        insert_at = search_end.end()
        prefix = without_eval[:insert_at].rstrip()
        suffix = without_eval[insert_at:].lstrip()
        eval_block = " ".join(deduped)
        return f"{prefix} {eval_block} {suffix}".strip()
    return f"{without_eval} {' '.join(deduped)}".strip()


def build_final_spl_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
    *,
    source_family: BindingSourceFamily | None = None,
) -> FinalSplProjection:
    slots = dict(slots or bindings.normalized_slots)
    family = source_family or infer_binding_source_family(bindings, slots)
    if family == FIREWALL_FLOW_FAMILY:
        projection = _build_firewall_projection(bindings, slots)
    elif family == WINDOWS_LOGON_FAMILY:
        projection = _build_windows_projection(bindings, slots)
    elif family == PROTOCOL_COMMAND_FAMILY:
        projection = _build_protocol_command_projection(bindings, slots)
    elif family == LOOKUP_CORRELATION_FAMILY:
        projection = _build_lookup_projection(bindings, slots)
    else:
        projection = _build_generic_projection(bindings, slots, family)
    projection.eval_lines = dedupe_eval_lines(projection.eval_lines)
    projection.initial_assessment = binding_initial_assessment(family, bindings, slots)
    projection.checklist = binding_investigation_checklist(family, bindings, slots)
    return projection


def build_output_projection_from_bindings(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None = None,
    *,
    source_family: BindingSourceFamily | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Backwards-compatible tuple wrapper over :func:`build_final_spl_projection`."""
    projection = build_final_spl_projection(bindings, slots, source_family=source_family)
    return (
        list(dict.fromkeys(projection.required_event_fields)),
        list(dict.fromkeys(projection.table_fields)),
        list(projection.eval_lines),
    )


def assemble_skeleton_spl(
    bindings: UserConstraintBindings,
    slots: dict[str, str] | None,
    projection: FinalSplProjection,
) -> str:
    slots = dict(slots or bindings.normalized_slots)
    indexes = bindings.explicit_indexes or ([slots["index"]] if slots.get("index") else ["*"])
    index_clause = " OR ".join(f"index={idx}" for idx in indexes)
    time_bounds = slots.get("time_window") or bindings.explicit_time_window or "earliest=-24h latest=now"
    sourcetype_clause = f" sourcetype={slots['sourcetype']}" if slots.get("sourcetype") else ""
    base = f"search ({index_clause}){sourcetype_clause} {time_bounds}"

    if projection.lookup_spl:
        return projection.lookup_spl.replace("{base}", base)

    pre_where_commands = list(projection.eval_lines)
    filters = list(projection.where_clauses)

    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or slots.get(
        "unexpected_ip_direction"
    )
    allowlist = bindings.explicit_allowlist_semantics.get("allowlist_semantic") or slots.get(
        "allowlist_semantic"
    )
    if projection.destination_lookup_spl:
        return projection.destination_lookup_spl.format(
            base=base,
            pre_where=" ".join(pre_where_commands),
            where_clause=" AND ".join(filters) if filters else "1=1",
            table=_skeleton_table_clause(projection.table_fields),
        )

    if allowlist or direction == "destination":
        src_field = _safe_field(slots.get("src_ip_field"), "src_ip")
        dest_field = _safe_field(slots.get("dest_ip_field"), "dest_ip")
        if not any("src_ip_norm=" in line for line in pre_where_commands):
            pre_where_commands.append(
                f"| eval src_ip_norm={_coalesce_field_expr(src_field, ('src_ip', 'src', 'source'))}"
            )
        if not any("dest_ip_norm=" in line for line in pre_where_commands):
            pre_where_commands.append(
                f"| eval dest_ip_norm={_coalesce_field_expr(dest_field, ('dest_ip', 'dest', 'destination'))}"
            )
        if slots.get("approved_destination_lookup"):
            lookup = slots["approved_destination_lookup"]
            where_clause = " AND ".join(filters) if filters else "1=1"
            pre_where = f" {' '.join(pre_where_commands)}" if pre_where_commands else ""
            return (
                f"{base}{pre_where} | where {where_clause} "
                f"| lookup {lookup} dest_ip as dest_ip_norm OUTPUT dest_ip as approved_dest_ip "
                f"| where isnull(approved_dest_ip) "
                f"| table {_skeleton_table_clause(projection.table_fields)} | head 100"
            )
        cidr = slots.get("approved_destination_cidr") or "<approved_ot_destination_cidr>"
        if not any("NOT cidrmatch" in clause for clause in filters):
            filters.append(f'NOT cidrmatch("{cidr}", dest_ip_norm)')

    src_scope = slots.get("src_scope")
    if src_scope == "substation_subnet" and slots.get("substation_mapping_lookup"):
        lookup = slots["substation_mapping_lookup"]
        if not any("src_ip_norm=" in cmd for cmd in pre_where_commands):
            pre_where_commands.append('| eval src_ip_norm=coalesce(src_ip, src, source, "")')
        pre_where_commands.append(f"| lookup {lookup} ip as src_ip_norm OUTPUT substation_id")
        filters.append("isnotnull(substation_id)")
    elif src_scope == "substation_subnet" and slots.get("approved_source_cidr"):
        cidr = slots["approved_source_cidr"]
        if not any("src_ip_norm=" in cmd for cmd in pre_where_commands):
            pre_where_commands.append(
                '| eval src_ip_norm=coalesce(src_ip, Source_Network_Address, IpAddress, source_ip, src, source, "")'
            )
        filters.append(f'cidrmatch("{cidr}", src_ip_norm)')

    if projection.threshold_spl:
        pre_where = f" {' '.join(pre_where_commands)}" if pre_where_commands else ""
        return projection.threshold_spl.format(
            base=base,
            pre_where=pre_where,
            where_clause=" AND ".join(filters) if filters else "1=1",
        )

    where_clause = " AND ".join(filters) if filters else "1=1"
    pre_where = f" {' '.join(pre_where_commands)}" if pre_where_commands else ""
    return (
        f"{base}{pre_where} | where {where_clause} "
        f"| table {_skeleton_table_clause(projection.table_fields)} | head 100"
    )


def _skeleton_table_clause(table_fields: list[str]) -> str:
    return " ".join(dict.fromkeys(table_fields))


def _safe_field(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}", text):
        return text
    return fallback


def _coalesce_field_expr(primary: str, fallbacks: tuple[str, ...]) -> str:
    fields: list[str] = []
    for field_name in (primary, *fallbacks):
        safe = _safe_field(field_name, "")
        if safe and safe not in fields:
            fields.append(safe)
    return f'coalesce({", ".join(fields)}, "")'


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _add_ip_norm_eval(
    eval_lines: list[str],
    required: list[str],
    table: list[str],
    *,
    field: str,
    aliases: tuple[str, ...],
    expr: str,
) -> None:
    for alias in aliases:
        if alias not in required:
            required.append(alias)
    if field not in required:
        required.append(field)
    if field not in table:
        table.append(field)
    if not any(f"{field}=" in line for line in eval_lines):
        eval_lines.append(expr)


def _numeric_code_parts(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
    *,
    binding_attr: str,
    slot_key: str,
    norm_field: str,
    aliases: tuple[str, ...],
) -> tuple[str | None, list[str]]:
    raw_codes = getattr(bindings, binding_attr) or slots.get(slot_key)
    if not raw_codes:
        return None, []
    codes = split_code_list(raw_codes)
    eval_line, where_clause = build_numeric_code_filter(codes, norm_field=norm_field, aliases=aliases)
    return where_clause, [eval_line]


def _quoted_spl(value: str) -> str:
    from app.spl.spl_slot_binding_validator import escape_spl_quoted_string

    return escape_spl_quoted_string(str(value))


def _action_semantic_where(action_semantic: str | None) -> str | None:
    if not action_semantic:
        return None
    action = str(action_semantic).strip().lower()
    if action in {"failed_login", "failure", "failed", "denied"}:
        return (
            '(like(action_norm, "%fail%") OR like(action_norm, "%denied%") '
            'OR like(action_norm, "%deny%") OR like(action_norm, "%block%"))'
        )
    if action in {"permit", "allowed", "allow", "accept"}:
        return (
            '(like(action_norm, "%permit%") OR like(action_norm, "%allow%") '
            'OR like(action_norm, "%accept%"))'
        )
    return f'like(action_norm, "%{_quoted_spl(action)}%")'


def _build_firewall_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
) -> FinalSplProjection:
    required: list[str] = [
        "_time",
        "action",
        "status",
        "result",
        "disposition",
        "action_norm",
        "src_zone",
        "source_zone",
        "src_network",
        "dest_zone",
        "destination_zone",
        "dest_network",
        "src_ip",
        "source_ip",
        "dest_ip",
        "destination_ip",
        "dest_port",
        "destination_port",
        "dport",
        "port",
        "protocol",
        "proto",
        "service",
        "app",
        "rule",
        "policy",
        "acl_name",
    ]
    table: list[str] = [
        "_time",
        "src_zone_norm",
        "dest_zone_norm",
        "src_ip_norm",
        "dest_ip_norm",
        "dest_port_norm",
        "protocol_norm",
        "action_norm",
        "rule",
        "policy",
        "acl_name",
    ]
    eval_lines: list[str] = [
        '| eval action_norm=lower(coalesce(action, status, result, disposition, ""))',
        '| eval src_zone_norm=coalesce(src_zone, source_zone, src_network, zone_src, "")',
        '| eval dest_zone_norm=coalesce(dest_zone, destination_zone, dest_network, zone_dest, "")',
        '| eval src_ip_norm=coalesce(src_ip, source_ip, src, source, "")',
        '| eval dest_ip_norm=coalesce(dest_ip, destination_ip, dest, destination, "")',
        '| eval dest_port_norm=tonumber(coalesce(dest_port, destination_port, dport, port))',
        '| eval protocol_norm=lower(coalesce(protocol, proto, service, app, ""))',
    ]
    where_clauses: list[str] = []

    if bindings.explicit_action_semantics or slots.get("action_semantic"):
        action_semantic = (
            bindings.explicit_action_semantics[0]
            if bindings.explicit_action_semantics
            else slots.get("action_semantic")
        )
        action_where = _action_semantic_where(action_semantic)
        if action_where:
            where_clauses.append(action_where)

    if bindings.explicit_ports or slots.get("port"):
        port = bindings.explicit_ports[0] if bindings.explicit_ports else int(slots["port"])
        where_clauses.append(f"dest_port_norm={port}")

    if bindings.explicit_services or slots.get("service"):
        service = (bindings.explicit_services[0] if bindings.explicit_services else slots.get("service", "")).lower()
        mapped_port = _SERVICE_PORT_MAP.get(service)
        if mapped_port:
            where_clauses.append(
                f'(dest_port_norm={mapped_port} OR like(protocol_norm, "%{_quoted_spl(service)}%"))'
            )
        else:
            where_clauses.append(f'like(protocol_norm, "%{_quoted_spl(service)}%")')

    if bindings.explicit_src_zones or slots.get("src_zone"):
        zone = bindings.explicit_src_zones[0] if bindings.explicit_src_zones else slots["src_zone"]
        where_clauses.append(f'src_zone_norm="{_quoted_spl(zone)}"')

    if bindings.explicit_dest_zones or slots.get("dest_zone"):
        zone = bindings.explicit_dest_zones[0] if bindings.explicit_dest_zones else slots["dest_zone"]
        where_clauses.append(f'dest_zone_norm="{_quoted_spl(zone)}"')

    if bindings.explicit_protocols or slots.get("protocol"):
        protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()
        where_clauses.append(f'like(protocol_norm, "%{_quoted_spl(protocol)}%")')

    return FinalSplProjection(
        eval_lines=eval_lines,
        where_clauses=where_clauses,
        table_fields=list(dict.fromkeys(table)),
        required_event_fields=list(dict.fromkeys(required)),
    )


def _build_windows_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
) -> FinalSplProjection:
    required: list[str] = ["_time"]
    table: list[str] = ["_time"]
    eval_lines: list[str] = []
    where_clauses: list[str] = []

    if bindings.explicit_event_codes or slots.get("event_code"):
        for alias in numeric_code_aliases("event_code"):
            if alias not in required:
                required.append(alias)
        required.append("event_code_norm")
        table.append("event_code_norm")
        eval_lines.append("| eval event_code_norm=tonumber(coalesce(EventCode, EventID, event_code))")
        codes = split_code_list(
            bindings.explicit_event_codes if bindings.explicit_event_codes else slots.get("event_code")
        )
        where_clauses.append(f"event_code_norm IN ({', '.join(codes)})")

    if bindings.explicit_users or slots.get("user"):
        for alias in ("user", "Account_Name", "TargetUserName", "Target_User_Name", "account", "username"):
            if alias not in required:
                required.append(alias)
        required.append("user_norm")
        table.append("user_norm")
        eval_lines.append(
            '| eval user_norm=lower(coalesce(user, Account_Name, TargetUserName, Target_User_Name, account, ""))'
        )
        user = bindings.explicit_users[0] if bindings.explicit_users else slots["user"]
        where_clauses.append(f'user_norm="{str(user).lower()}"')

    src_bound = bool(
        bindings.explicit_src_ips
        or slots.get("src_ip")
        or slots.get("src_scope")
        or slots.get("approved_source_cidr")
        or slots.get("substation_mapping_lookup")
    )
    if src_bound:
        _add_ip_norm_eval(
            eval_lines,
            required,
            table,
            field="src_ip_norm",
            aliases=("src_ip", "Source_Network_Address", "IpAddress", "source_ip", "src", "source"),
            expr='| eval src_ip_norm=coalesce(src_ip, Source_Network_Address, IpAddress, source_ip, src, source, "")',
        )

    for alias in ("host", "ComputerName", "dest_host", "dest", "Computer"):
        if alias not in required:
            required.append(alias)
    required.append("dest_host_norm")
    table.append("dest_host_norm")
    eval_lines.append('| eval dest_host_norm=coalesce(host, ComputerName, dest_host, dest, Computer, "")')
    if bindings.explicit_hosts or slots.get("host"):
        host = bindings.explicit_hosts[0] if bindings.explicit_hosts else slots["host"]
        where_clauses.append(f'dest_host_norm="{_quoted_spl(host)}"')

    for field in ("Logon_Type", "Workstation_Name", "Authentication_Package"):
        if field not in table:
            table.append(field)

    threshold = bindings.explicit_thresholds.get("threshold") or slots.get("threshold")
    threshold_spl = None
    if threshold:
        comparison = (
            bindings.explicit_thresholds.get("comparison")
            or slots.get("threshold_comparison")
            or "greater_than"
        )
        op = ">" if comparison in {"greater_than", "more_than", "gt"} else ">="
        subject = slots.get("aggregation_subject") or "user"
        by_field = "user_norm" if subject == "user" else _safe_field(subject, "user")
        threshold_spl = (
            "{base}{pre_where} | where {where_clause} "
            f"| stats count by {by_field} | where count {op} {threshold} | sort - count | head 100"
        )

    return FinalSplProjection(
        eval_lines=eval_lines,
        where_clauses=where_clauses,
        table_fields=list(dict.fromkeys(table)),
        required_event_fields=list(dict.fromkeys(required)),
        threshold_spl=threshold_spl,
    )


def _build_protocol_command_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
) -> FinalSplProjection:
    required: list[str] = ["_time"]
    table: list[str] = ["_time", "action"]
    eval_lines: list[str] = []
    where_clauses: list[str] = []

    if bindings.explicit_protocols or slots.get("protocol"):
        protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()
        _append_unique(required, ["protocol", "proto", "protocol_name", "protocol_norm"])
        table.append("protocol_norm")
        eval_lines.append('| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, ""))')
        where_clauses.append(f'like(protocol_norm, "%{protocol}%")')

    function_field = slots.get("function_code_field") or "function_code"
    where_clause, code_evals = _numeric_code_parts(
        bindings,
        slots,
        binding_attr="explicit_function_codes",
        slot_key="function_code",
        norm_field="function_code_norm",
        aliases=numeric_code_aliases("function_code", primary_field=function_field),
    )
    if code_evals:
        eval_lines.extend(code_evals)
        for alias in numeric_code_aliases("function_code", primary_field=function_field):
            if alias not in required:
                required.append(alias)
        required.append("function_code_norm")
        table.append("function_code_norm")
        if where_clause:
            where_clauses.append(where_clause)

    direction = bindings.explicit_directionality.get("unexpected_ip_direction") or slots.get(
        "unexpected_ip_direction"
    )
    allowlist = bindings.explicit_allowlist_semantics.get("allowlist_semantic") or slots.get(
        "allowlist_semantic"
    )
    if allowlist or direction == "destination" or slots.get("approved_destination_cidr"):
        src_field = _safe_field(slots.get("src_ip_field"), "src_ip")
        dest_field = _safe_field(slots.get("dest_ip_field"), "dest_ip")
        _add_ip_norm_eval(
            eval_lines,
            required,
            table,
            field="src_ip_norm",
            aliases=(src_field, "src_ip", "src", "source"),
            expr=f"| eval src_ip_norm={_coalesce_field_expr(src_field, ('src_ip', 'src', 'source'))}",
        )
        _add_ip_norm_eval(
            eval_lines,
            required,
            table,
            field="dest_ip_norm",
            aliases=(dest_field, "dest_ip", "dest", "destination"),
            expr=f"| eval dest_ip_norm={_coalesce_field_expr(dest_field, ('dest_ip', 'dest', 'destination'))}",
        )
        if slots.get("approved_destination_lookup"):
            return FinalSplProjection(
                eval_lines=eval_lines,
                where_clauses=where_clauses,
                table_fields=list(dict.fromkeys(table)),
                required_event_fields=list(dict.fromkeys(required)),
                destination_lookup_spl=(
                    "{base}{pre_where} | where {where_clause} "
                    "| lookup {lookup} dest_ip as dest_ip_norm OUTPUT dest_ip as approved_dest_ip "
                    "| where isnull(approved_dest_ip) "
                    "| table {table} | head 100"
                ).replace("{lookup}", slots["approved_destination_lookup"]),
            )
        cidr = slots.get("approved_destination_cidr") or "<approved_ot_destination_cidr>"
        where_clauses.append(f'NOT cidrmatch("{cidr}", dest_ip_norm)')

    return FinalSplProjection(
        eval_lines=eval_lines,
        where_clauses=where_clauses,
        table_fields=list(dict.fromkeys(table)),
        required_event_fields=list(dict.fromkeys(required)),
    )

def _is_ioc_lookup_correlation(lookup: str, slots: dict[str, str]) -> bool:
    lookup_lower = str(lookup or "").lower()
    if "ioc" in lookup_lower or "indicator" in lookup_lower:
        return True
    if slots.get("lookup_match_field") == "indicator_ip":
        return True
    if re.search(r"\bindicator_ip\b", " ".join(slots.values()), re.IGNORECASE):
        return True
    return False


def _ioc_lookup_correlation_spl(lookup: str, slots: dict[str, str]) -> str:
    log_field = slots.get("log_match_field") or slots.get("dest_ip") or "dest_ip"
    lookup_field = slots.get("lookup_match_field") or "indicator_ip"
    return (
        f"{{base}} | lookup {lookup} {lookup_field} as {log_field} "
        f"OUTPUT {lookup_field} as matched_ioc\n"
        "| where isnotnull(matched_ioc)\n"
        "| stats count as event_count values(action) as actions by src_ip dest_ip matched_ioc\n"
        "| table src_ip dest_ip actions event_count matched_ioc\n"
        "| sort -event_count"
    )


def _build_lookup_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
) -> FinalSplProjection:
    lookup = bindings.explicit_lookups[0] if bindings.explicit_lookups else slots.get("lookup", "")
    if lookup and _is_ioc_lookup_correlation(lookup, slots):
        return FinalSplProjection(
            table_fields=["src_ip", "dest_ip", "matched_ioc", "actions", "event_count"],
            required_event_fields=["src_ip", "dest_ip", "action"],
            lookup_spl=_ioc_lookup_correlation_spl(lookup, slots),
            initial_assessment=[
                "Correlate firewall or traffic logs against the named IOC/threat-feed lookup.",
                "Review matched indicator hits with context before escalation.",
            ],
            checklist=[
                "Confirm lookup CSV field mappings (indicator_ip as log match field).",
                "Validate index/sourcetype and dest_ip/src_ip field mappings.",
                "Tune the 24h window with operations before any execution.",
                "Do not declare compromise from lookup hits alone.",
            ],
        )
    return FinalSplProjection(
        table_fields=["_time", "src_ip", "dest_ip", "asset_name"],
        required_event_fields=["_time", "src_ip", "dest_ip", "asset_name"],
        lookup_spl=(
            "{base} | lookup "
            f"{lookup} asset_ip OUTPUT asset_name | where isnull(asset_name) "
            "| table _time src_ip dest_ip asset_name | head 100"
        ),
    )


def _build_generic_projection(
    bindings: UserConstraintBindings,
    slots: dict[str, str],
    family: BindingSourceFamily,
) -> FinalSplProjection:
    required: list[str] = ["_time"]
    table: list[str] = ["_time"]
    eval_lines: list[str] = []
    where_clauses: list[str] = []

    if bindings.explicit_event_codes or slots.get("event_code"):
        where_clause, code_evals = _numeric_code_parts(
            bindings,
            slots,
            binding_attr="explicit_event_codes",
            slot_key="event_code",
            norm_field="event_code_norm",
            aliases=numeric_code_aliases("event_code"),
        )
        if code_evals:
            eval_lines.extend(code_evals)
            for alias in numeric_code_aliases("event_code"):
                if alias not in required:
                    required.append(alias)
            required.append("event_code_norm")
            table.append("event_code_norm")
            if where_clause:
                where_clauses.append(where_clause)

    if bindings.explicit_users or slots.get("user"):
        for alias in ("user", "Account_Name", "TargetUserName", "Target_User_Name", "account", "username"):
            if alias not in required:
                required.append(alias)
        required.append("user_norm")
        table.append("user_norm")
        eval_lines.append(
            '| eval user_norm=lower(coalesce(user, Account_Name, TargetUserName, Target_User_Name, account, ""))'
        )
        user = bindings.explicit_users[0] if bindings.explicit_users else slots["user"]
        if eval_lines:
            where_clauses.append(f'user_norm="{str(user).lower()}"')
        else:
            where_clauses.append(f'user="{user}"')

    if bindings.explicit_hosts or slots.get("host"):
        host = bindings.explicit_hosts[0] if bindings.explicit_hosts else slots["host"]
        where_clauses.append(f'host="{host}"')

    if bindings.explicit_src_ips or slots.get("src_ip"):
        ip = bindings.explicit_src_ips[0] if bindings.explicit_src_ips else slots["src_ip"]
        where_clauses.append(f'src_ip="{ip}"')

    if bindings.explicit_dest_ips or slots.get("dest_ip"):
        ip = bindings.explicit_dest_ips[0] if bindings.explicit_dest_ips else slots["dest_ip"]
        where_clauses.append(f'dest_ip="{ip}"')

    if bindings.explicit_ports or slots.get("port"):
        _append_unique(required, ["dest_port", "port", "destination_port", "dest_port_norm"])
        table.append("dest_port_norm")
        eval_lines.append("| eval dest_port_norm=tonumber(coalesce(dest_port, port, destination_port))")
        port = bindings.explicit_ports[0] if bindings.explicit_ports else int(slots["port"])
        where_clauses.append(f"dest_port_norm={port}")

    if bindings.explicit_protocols or slots.get("protocol"):
        protocol = (bindings.explicit_protocols[0] if bindings.explicit_protocols else slots.get("protocol", "")).lower()
        _append_unique(required, ["protocol", "proto", "protocol_name", "protocol_norm"])
        table.append("protocol_norm")
        eval_lines.append('| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, ""))')
        where_clauses.append(f'like(protocol_norm, "%{protocol}%")')

    if family == FIREWALL_FLOW_FAMILY and "action" not in table:
        table.append("action")

    threshold = bindings.explicit_thresholds.get("threshold") or slots.get("threshold")
    threshold_spl = None
    if threshold:
        comparison = (
            bindings.explicit_thresholds.get("comparison")
            or slots.get("threshold_comparison")
            or "greater_than"
        )
        op = ">" if comparison in {"greater_than", "more_than", "gt"} else ">="
        subject = slots.get("aggregation_subject") or "user"
        by_field = "user" if subject == "user" else _safe_field(subject, "user")
        threshold_spl = (
            "{base}{pre_where} | where {where_clause} "
            f"| stats count by {by_field} | where count {op} {threshold} | sort - count | head 100"
        )

    return FinalSplProjection(
        eval_lines=eval_lines,
        where_clauses=where_clauses,
        table_fields=list(dict.fromkeys(table)),
        required_event_fields=list(dict.fromkeys(required)),
        threshold_spl=threshold_spl,
    )


def _action_semantic_filter(action_semantic: str | None) -> str | None:
    if not action_semantic:
        return None
    action = str(action_semantic).strip().lower()
    if action in {"failed_login", "failure", "failed", "denied"}:
        return (
            '| eval action_norm=lower(coalesce(action, status, result, signature, "")) '
            '| where like(action_norm, "%fail%") OR like(action_norm, "%denied%")'
        )
    if action in {"permit", "allowed", "allow", "accept"}:
        return (
            '| eval action_norm=lower(coalesce(action, status, result, "")) '
            '| where like(action_norm, "%permit%") OR like(action_norm, "%allow%") '
            'OR like(action_norm, "%accept%")'
        )
    return (
        f'| eval action_norm=lower(coalesce(action, status, result, "")) '
        f'| where like(action_norm, "%{action}%")'
    )
