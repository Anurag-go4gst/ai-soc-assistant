"""Deterministic hard-token pre-parse for T1 SPL-native generation.

Before any LLM is asked to draft SPL, we extract the tokens the user wrote
verbatim (index, sourcetype, lookup file, explicit fields, time windows, unsafe
commands, operation hints).  These are *constraints*: the LLM must honour them
and the deterministic repair layer falls back to them, so a draft cannot drift
off the index/fields the analyst actually named.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.spl.t2_constraints import extract_semantic_constraints, resolve_shift_config_for_query

_INDEX_RE = re.compile(r"\bindex\s*=\s*([A-Za-z0-9_\-*]+)", re.IGNORECASE)
_SOURCETYPE_RE = re.compile(r"\bsourcetype\s*=\s*([A-Za-z0-9_:\-./]+)", re.IGNORECASE)
_LOOKUP_FILE_RE = re.compile(r"\b([A-Za-z0-9_\-]+\.csv)\b", re.IGNORECASE)
_EARLIEST_RE = re.compile(r"\bearliest\s*=\s*(-?\d+[smhdwy])\b", re.IGNORECASE)
_LATEST_RE = re.compile(r"\blatest\s*=\s*([A-Za-z0-9()\-]+)", re.IGNORECASE)
_RELATIVE_WINDOW_RE = re.compile(
    r"\b(?:last|past|previous)\s+(\d+)\s*"
    r"(seconds|second|sec|minutes|minute|min|hours|hour|hrs|hr|days|day|weeks|week|wks|wk|[smhdw])\b",
    re.IGNORECASE,
)

# Candidate field names worth preserving when the user spells them.
_KNOWN_FIELDS = (
    "rtu_id",
    "asset_id",
    "device_id",
    "dest_ip",
    "src_ip",
    "indicator_ip",
    "dest_port",
    "src_port",
    "transmission_error_count",
    "transmission_error",
    "error_count",
    "latency",
    "packet_loss",
    "bytes",
    "packets",
    "user",
    "action",
)

# Unsafe SPL commands that must never appear in a generated draft.
UNSAFE_SPL_COMMANDS: frozenset[str] = frozenset(
    {
        "delete",
        "outputlookup",
        "collect",
        "sendemail",
        "script",
        "map",
        "rest",
        "savedsearch",
    }
)

# Operation hint regexes -> canonical runtime_operation.  Word-boundary anchored
# so short tokens cannot match inside unrelated words (e.g. "top" in "laptop",
# "then" in "strengthen", "rank" in "frankly").
_OPERATION_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    ((r"baseline", r"stdev", r"std\s+dev", r"anomal\w*", r"z[-\s]?score", r"outlier\w*", r"deviation", r"threshold", r"breach"), "threshold_anomaly"),
    ((r"ioc", r"indicator\w*", r"lookup", r"threat\s+feed", r"threat\s+intel\w*", r"correlat\w*"), "lookup_correlation"),
    ((r"top\s+talkers?", r"highest\s+volume", r"most\s+frequent", r"\brank\b", r"\btop\b"), "aggregate_and_rank"),
    ((r"timeline", r"sequence\s+over\s+time", r"chronolog\w*"), "entity_timeline"),
    ((r"\bsequence\b", r"followed\s+by", r"\bthen\b"), "sequence_detection"),
)

_TIME_UNIT_TO_SUFFIX = {
    "second": "s",
    "seconds": "s",
    "sec": "s",
    "s": "s",
    "minute": "m",
    "minutes": "m",
    "min": "m",
    "m": "m",
    "hour": "h",
    "hours": "h",
    "hr": "h",
    "hrs": "h",
    "h": "h",
    "day": "d",
    "days": "d",
    "d": "d",
    "week": "w",
    "weeks": "w",
    "wk": "w",
    "wks": "w",
    "w": "w",
}


@dataclass
class PreParsedSplTokens:
    indexes: list[str] = field(default_factory=list)
    sourcetypes: list[str] = field(default_factory=list)
    lookup_files: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    earliest: str | None = None
    latest: str | None = None
    relative_windows: list[str] = field(default_factory=list)
    operation_hints: list[str] = field(default_factory=list)
    unsafe_commands: list[str] = field(default_factory=list)
    semantic_constraints: list[dict[str, object]] = field(default_factory=list)
    missing_constraint_bindings: list[str] = field(default_factory=list)

    def to_constraints(self) -> dict[str, object]:
        return {
            "indexes": self.indexes,
            "sourcetypes": self.sourcetypes,
            "lookup_files": self.lookup_files,
            "fields": self.fields,
            "earliest": self.earliest,
            "latest": self.latest,
            "relative_windows": self.relative_windows,
            "operation_hints": self.operation_hints,
            "unsafe_commands": self.unsafe_commands,
            "semantic_constraints": self.semantic_constraints,
            "missing_constraint_bindings": self.missing_constraint_bindings,
        }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def pre_parse_spl_tokens(query: str) -> PreParsedSplTokens:
    text = query or ""
    lowered = text.lower()

    indexes = _dedupe(_INDEX_RE.findall(text))
    sourcetypes = _dedupe(_SOURCETYPE_RE.findall(text))
    lookup_files = _dedupe(_LOOKUP_FILE_RE.findall(text))

    fields = [name for name in _KNOWN_FIELDS if re.search(rf"\b{re.escape(name)}\b", lowered)]

    earliest_match = _EARLIEST_RE.search(text)
    earliest = earliest_match.group(1) if earliest_match else None
    latest_match = _LATEST_RE.search(text)
    latest = latest_match.group(1) if latest_match else None

    relative_windows: list[str] = []
    for amount, unit in _RELATIVE_WINDOW_RE.findall(text):
        suffix = _TIME_UNIT_TO_SUFFIX.get(unit.lower())
        if suffix:
            relative_windows.append(f"{amount}{suffix}")
    relative_windows = _dedupe(relative_windows)

    operation_hints: list[str] = []
    for patterns, operation in _OPERATION_HINTS:
        if operation in operation_hints:
            continue
        if any(re.search(pattern, lowered) for pattern in patterns):
            operation_hints.append(operation)

    unsafe_commands = sorted({cmd for cmd in UNSAFE_SPL_COMMANDS if re.search(rf"\b{cmd}\b", lowered)})

    shift_config = resolve_shift_config_for_query(text)
    constraint_result = extract_semantic_constraints(text, shift_config=shift_config)
    return PreParsedSplTokens(
        indexes=indexes,
        sourcetypes=sourcetypes,
        lookup_files=lookup_files,
        fields=_dedupe(fields),
        earliest=earliest,
        latest=latest,
        relative_windows=relative_windows,
        operation_hints=operation_hints,
        unsafe_commands=unsafe_commands,
        semantic_constraints=[item.to_dict() for item in constraint_result.constraints],
        missing_constraint_bindings=list(constraint_result.missing_bindings),
    )
