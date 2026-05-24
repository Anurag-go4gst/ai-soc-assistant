from __future__ import annotations

import re
from typing import Any

from app.spl.policy import SplValidationPolicy, load_spl_policy

SECRET_PATTERNS = (
    re.compile(r"\b(password|passwd|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)


def validate_spl(query: str, policy: SplValidationPolicy | None = None) -> dict[str, Any]:
    policy = policy or load_spl_policy()
    spl = _normalize_whitespace(query)
    lowered = spl.lower()
    reject_reasons: list[str] = []
    warnings: list[str] = []

    if not policy.enabled:
        reject_reasons.append("spl_validation_disabled")
    if not spl:
        reject_reasons.append("empty_spl")

    commands = _extract_commands(spl)
    blocked = sorted(set(commands).intersection(policy.blocked_commands))
    disallowed = sorted(command for command in set(commands) if command not in policy.allowed_commands)
    indexes = _extract_field_values(spl, "index")
    sourcetypes = _extract_field_values(spl, "sourcetype")

    if blocked:
        reject_reasons.append(f"blocked_command:{','.join(blocked)}")
    if disallowed:
        reject_reasons.append(f"disallowed_command:{','.join(disallowed)}")
    if not commands or commands[0] != "search":
        reject_reasons.append("first_command_must_be_search")
    if "earliest=" not in lowered or "latest=" not in lowered:
        reject_reasons.append("missing_time_bounds")
    if "earliest=0" in lowered or "earliest=all" in lowered or "alltime" in lowered:
        reject_reasons.append("unbounded_all_time_search")
    if not set(commands).intersection({"stats", "timechart"}):
        reject_reasons.append("missing_aggregation")
    if not indexes:
        reject_reasons.append("missing_index")
    if any(index not in policy.allowed_indexes for index in indexes):
        reject_reasons.append("disallowed_index")
    if any("*" in index for index in indexes) and not policy.allow_wildcard_indexes:
        reject_reasons.append("wildcard_index_not_allowed")
    if not sourcetypes:
        reject_reasons.append("missing_sourcetype")
    if any(sourcetype not in policy.allowed_sourcetypes for sourcetype in sourcetypes):
        reject_reasons.append("disallowed_sourcetype")
    if re.search(r"`[^`]+`", spl) and not policy.allow_macros:
        reject_reasons.append("macros_not_allowed")
    if ("[" in spl or "]" in spl) and not policy.allow_subsearches:
        reject_reasons.append("subsearches_not_allowed")
    if re.search(r"\b(https?://|curl\b|wget\b|webhook\b)\b", lowered) and not policy.allow_external_calls:
        reject_reasons.append("external_calls_not_allowed")
    if any(pattern.search(spl) for pattern in SECRET_PATTERNS):
        reject_reasons.append("credential_or_secret_pattern")

    enforced_limits = {
        "max_result_limit": policy.max_result_limit,
        "result_limit_enforced": True,
        "enforcement_mode": "out_of_band",
        "default_earliest": policy.default_earliest,
        "default_latest": policy.default_latest,
    }
    limit_value = _result_limit_value(spl)
    if limit_value is None:
        reject_reasons.append("missing_result_limit")
    elif limit_value > policy.max_result_limit:
        reject_reasons.append("result_limit_exceeds_policy")

    approved = not reject_reasons
    normalized_spl = spl if approved else None
    return {
        "approved": approved,
        "normalized_spl": normalized_spl,
        "reject_reasons": reject_reasons,
        "warnings": warnings,
        "enforced_limits": enforced_limits,
        "policy_version": policy.policy_version,
        # Backward-compatible aliases for existing tests and debug surfaces.
        "valid": approved,
        "errors": reject_reasons,
        "blocked_commands": blocked,
        "requires_human_approval": bool(reject_reasons),
    }


def _normalize_whitespace(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())


def _extract_commands(spl: str) -> list[str]:
    parts = [part.strip() for part in spl.split("|") if part.strip()]
    commands: list[str] = []
    for index, part in enumerate(parts):
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", part)
        if not match:
            continue
        command = match.group(1).lower()
        if index == 0 and command not in {"search", "tstats", "inputlookup"}:
            commands.append("search")
        else:
            commands.append(command)
    return commands


def _extract_field_values(spl: str, field: str) -> list[str]:
    return [match.group(1).strip('"').lower() for match in re.finditer(rf"\b{field}=([^\s|]+)", spl, re.IGNORECASE)]


def _has_result_limit(spl: str) -> bool:
    return _result_limit_value(spl) is not None


def _result_limit_value(spl: str) -> int | None:
    lowered = spl.lower()
    head_match = re.search(r"\|\s*head\s+(\d+)", lowered)
    if head_match:
        return int(head_match.group(1))
    sort_match = re.search(r"\|\s*sort\s+(\d+)\s+", lowered)
    if sort_match:
        return int(sort_match.group(1))
    return None
