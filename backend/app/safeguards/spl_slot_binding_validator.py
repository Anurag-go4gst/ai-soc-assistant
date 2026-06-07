"""Validate that candidate SPL encodes user-requested control-plane slots."""

from __future__ import annotations

import re
from typing import Any

from app.spl.template_registry import SplTemplateDefinition, get_spl_template

POLICY_VERSION = "2026-06-spl-slot-binding-v1"


def validate_spl_slot_bindings(
    spl_validation: dict[str, Any],
    *,
    user_query: str,
    query_signals: dict[str, Any] | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    """Fail closed when requested slots are missing from otherwise valid SPL."""
    constraints = extract_slot_constraints(user_query, query_signals=query_signals)
    if not constraints:
        return spl_validation

    result = dict(spl_validation)
    reject_reasons = list(result.get("reject_reasons") or [])
    warnings = list(result.get("warnings") or [])
    spl = str(result.get("normalized_spl") or "")

    template = get_spl_template(template_id)
    if template is None:
        reject_reasons.extend(["user_constraints_not_encoded", "missing_template_for_slot_binding"])
        return _rejected(result, reject_reasons, warnings)

    missing = missing_slot_bindings(
        spl=spl,
        constraints=constraints,
        template=template,
    )
    if missing:
        reject_reasons.append("user_constraints_not_encoded")
        reject_reasons.extend(f"missing_binding:{item}" for item in missing)
        return _rejected(result, reject_reasons, warnings)

    warnings.append("slot_binding_validated")
    result["warnings"] = sorted(set(warnings))
    result["policy_version"] = f"{result.get('policy_version', 'unknown')}+{POLICY_VERSION}"
    return result


def extract_slot_constraints(
    user_query: str,
    *,
    query_signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals = query_signals if isinstance(query_signals, dict) else {}
    normalized = " ".join(user_query.lower().split())
    constraints: dict[str, Any] = {}

    if signals.get("time_window_24h") or any(
        token in normalized for token in ("last 24 hours", "last 24h", "past 24 hours", "24 hours", "24h")
    ):
        constraints["time_window"] = "last_24h"

    if signals.get("exclude_service_accounts") or "exclude service account" in normalized or "excluding service account" in normalized:
        constraints["exclude_service_accounts"] = True

    top_n = _extract_top_n(normalized)
    if top_n is not None:
        constraints["result_limit"] = top_n

    if any(token in normalized for token in ("failed login", "failed logins", "login failure", "login failures")):
        constraints["event_type"] = "failure"

    if any(token in normalized for token in ("top users", "by user", "which users")):
        constraints["group_by"] = "user"
        constraints["entity_type"] = "user"

    return constraints


def missing_slot_bindings(
    *,
    spl: str,
    constraints: dict[str, Any],
    template: SplTemplateDefinition,
) -> list[str]:
    lowered = spl.lower()
    missing: list[str] = []

    if constraints.get("time_window") == "last_24h":
        if not _template_can_bind(template, "earliest") and "earliest=-24h" not in lowered:
            missing.append("last_24h")
        elif "earliest=-24h" not in lowered:
            missing.append("last_24h")

    if constraints.get("exclude_service_accounts"):
        if not _has_service_account_exclusion(lowered):
            missing.append("exclude_service_accounts")

    result_limit = constraints.get("result_limit")
    if isinstance(result_limit, int):
        if f"head {result_limit}" not in lowered and f"limit={result_limit}" not in lowered:
            missing.append(f"top_{result_limit}")

    if constraints.get("event_type") == "failure":
        if not any(token in lowered for token in ("action=failure", "action=\"failure\"", "authentication.action=failure")):
            missing.append("failure_event_type")

    if constraints.get("group_by") == "user":
        if not re.search(r"\bby\s+(?:authentication\.)?user\b", lowered) and not re.search(
            r"\bby\s+useridentity\.(?:arn|username)\b", lowered
        ):
            missing.append("group_by_user")

    if not _has_index_or_datamodel(lowered):
        missing.append("index_or_datamodel")

    return sorted(set(missing))


def _template_can_bind(template: SplTemplateDefinition, parameter: str) -> bool:
    if template.render_pattern and f"{{{parameter}}}" in template.render_pattern:
        return True
    if parameter in template.required_parameters or parameter in template.optional_parameters:
        return True
    return parameter in template.parameter_value_patterns


def _has_service_account_exclusion(lowered_spl: str) -> bool:
    if "service account" in lowered_spl and any(token in lowered_spl for token in ("not ", "!=", "not like", "not match")):
        return True
    if re.search(r"\bnot\s*\([^)]*\buser\s*=\s*\"[^\"]*(svc|service)[^\"]*\"", lowered_spl):
        return True
    return bool(
        re.search(r"\bnot\s+(?:like|match)\s*\(\s*(?:authentication\.)?user\s*,\s*\"[^\"]*(svc|service)[^\"]*\"", lowered_spl)
        or re.search(r"\b(?:authentication\.)?user\s*!=\s*\"?[^\s\"]*(svc|service)[^\s\"]*\"?", lowered_spl)
        or re.search(r"\bnot\s+(?:authentication\.)?user\s*=\s*\"?[^\s\"]*(svc|service)[^\s\"]*\"?", lowered_spl)
    )


def _has_index_or_datamodel(lowered_spl: str) -> bool:
    return "index=" in lowered_spl or "from datamodel=" in lowered_spl or "datamodel=" in lowered_spl


def _extract_top_n(normalized_query: str) -> int | None:
    patterns = (
        r"\btop\s+(\d+)\b",
        r"\bfirst\s+(\d+)\b",
        r"\blimit\s+(\d+)\b",
        r"\bhead\s+(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized_query)
        if match:
            return int(match.group(1))
    return None


def _rejected(
    result: dict[str, Any],
    reject_reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    result["approved"] = False
    result["normalized_spl"] = None
    result["reject_reasons"] = sorted(set(reject_reasons))
    result["warnings"] = sorted(set(warnings))
    result["policy_version"] = f"{result.get('policy_version', 'unknown')}+{POLICY_VERSION}"
    return result
