"""Generic tonumber/coalesce numeric code filters for SPL drafts."""

from __future__ import annotations

from typing import Any


def numeric_code_aliases(
    slot: str,
    *,
    primary_field: str | None = None,
) -> tuple[str, ...]:
    if slot == "event_code":
        return ("EventCode", "EventID", "event_code")
    if slot == "function_code":
        fields = []
        if primary_field:
            fields.append(primary_field)
        fields.extend(["function_code", "modbus_function_code", "function"])
        return tuple(dict.fromkeys(fields))
    if slot in {"status_code", "http_status"}:
        return ("status_code", "http_status", "status", "response_code")
    if primary_field:
        return (primary_field, slot)
    return (slot,)


def build_numeric_code_filter(
    codes: list[str],
    *,
    norm_field: str,
    aliases: tuple[str, ...],
) -> tuple[str, str]:
    unique_aliases = [alias for alias in aliases if alias]
    coalesce_expr = ", ".join(unique_aliases) if unique_aliases else norm_field
    eval_line = f"| eval {norm_field}=tonumber(coalesce({coalesce_expr}))"
    numeric_codes = ", ".join(str(int(code)) if str(code).isdigit() else str(code) for code in codes)
    where_clause = f"{norm_field} IN ({numeric_codes})"
    return eval_line, where_clause


def split_code_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]
