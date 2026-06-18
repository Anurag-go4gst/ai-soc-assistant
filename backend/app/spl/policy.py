from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.config import settings

POLICY_VERSION = "spl-policy-v1"
_LOOKUP_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.csv$", re.IGNORECASE)


@dataclass(frozen=True)
class SplValidationPolicy:
    enabled: bool
    allowed_indexes: tuple[str, ...]
    allowed_sourcetypes: tuple[str, ...]
    default_earliest: str
    default_latest: str
    max_result_limit: int
    allowed_commands: tuple[str, ...]
    blocked_commands: tuple[str, ...]
    allow_wildcard_indexes: bool = False
    allow_macros: bool = False
    allow_subsearches: bool = False
    allow_external_calls: bool = False
    allowed_lookups: tuple[str, ...] = ()
    allow_join: bool = False
    allow_transaction: bool = False
    policy_version: str = POLICY_VERSION


def load_spl_policy() -> SplValidationPolicy:
    return SplValidationPolicy(
        enabled=settings.spl_validation_enabled,
        allowed_indexes=_csv(settings.spl_allowed_indexes, ("pgcil_soc",)),
        allowed_sourcetypes=_csv(settings.spl_allowed_sourcetypes, ("pgcil:auth",)),
        default_earliest=settings.spl_default_earliest,
        default_latest=settings.spl_default_latest,
        max_result_limit=settings.spl_max_result_limit,
        allowed_commands=_csv(
            settings.spl_allowed_commands,
            ("search", "stats", "where", "table", "fields", "sort", "dedup", "rename", "eval", "timechart", "bin", "head"),
        ),
        blocked_commands=_csv(
            settings.spl_blocked_commands,
            ("delete", "collect", "outputlookup", "sendemail", "script", "map", "rest", "loadjob", "inputlookup"),
        ),
        allowed_lookups=_csv(settings.spl_allowed_lookups, ()),
        allow_join=settings.spl_allow_join_in_governed_templates,
        allow_transaction=settings.spl_allow_transaction_in_governed_templates,
    )


def policy_with_template_profile(
    policy: SplValidationPolicy,
    template_profile: dict[str, Any] | None,
) -> SplValidationPolicy:
    if not isinstance(template_profile, dict) or not template_profile:
        return policy

    allowed_commands = _profile_tuple(template_profile, "allowed_commands", policy.allowed_commands)
    allowed_command_set = set(allowed_commands)
    allowed_lookups = set(policy.allowed_lookups)
    if template_profile.get("allowed_lookups"):
        allowed_command_set.update({"lookup", "inputlookup"})
        allowed_lookups.update(_safe_lookup_name(str(item)) for item in template_profile.get("allowed_lookups") or [])
        allowed_lookups.discard("")

    allow_join = bool(template_profile.get("allow_join")) or policy.allow_join
    allow_transaction = bool(template_profile.get("allow_transaction")) or policy.allow_transaction
    if allow_join:
        allowed_command_set.add("join")
    if allow_transaction:
        allowed_command_set.add("transaction")

    return SplValidationPolicy(
        enabled=policy.enabled,
        allowed_indexes=_profile_tuple(template_profile, "allowed_indexes", policy.allowed_indexes),
        allowed_sourcetypes=_profile_tuple(template_profile, "allowed_sourcetypes", policy.allowed_sourcetypes),
        default_earliest=policy.default_earliest,
        default_latest=policy.default_latest,
        max_result_limit=policy.max_result_limit,
        allowed_commands=tuple(sorted(allowed_command_set)),
        blocked_commands=policy.blocked_commands,
        allow_wildcard_indexes=policy.allow_wildcard_indexes,
        allow_macros=policy.allow_macros,
        allow_subsearches=bool(template_profile.get("allow_subsearches")) or policy.allow_subsearches,
        allow_external_calls=policy.allow_external_calls,
        allowed_lookups=tuple(sorted(allowed_lookups)),
        allow_join=allow_join,
        allow_transaction=allow_transaction,
        policy_version=policy.policy_version,
    )


def _csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    parsed = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    return parsed or default


def _profile_tuple(
    template_profile: dict[str, Any],
    key: str,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    raw = template_profile.get(key)
    if isinstance(raw, list) and raw:
        parsed = tuple(str(item).strip().lower() for item in raw if str(item).strip())
        return parsed or fallback
    return fallback


def _safe_lookup_name(value: str) -> str:
    candidate = value.strip().strip('"').strip("'")
    if not _LOOKUP_NAME_RE.fullmatch(candidate):
        return ""
    if "/" in candidate or "\\" in candidate or ".." in candidate or "*" in candidate:
        return ""
    return candidate.lower()
