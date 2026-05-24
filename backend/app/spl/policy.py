from __future__ import annotations

from dataclasses import dataclass

from app.config import settings

POLICY_VERSION = "spl-policy-v1"


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
    )


def _csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    parsed = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    return parsed or default
