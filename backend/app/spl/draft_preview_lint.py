"""Lint rules for lab-only SPL draft preview quality."""

from __future__ import annotations

import re

# Double-quoted SPL string; supports escaped quotes inside.
_QUOTED_STRING = re.compile(r'"(?:\\.|[^"\\])*"', re.DOTALL)

# Unescaped single backslash before a path token, e.g. "*\w3wp.exe" or "C:\Windows".
_UNESCAPED_WINDOWS_PATH = re.compile(
    r'"[^"]*(?<![\\])[\\](?![\\/"%])[A-Za-z0-9_.-]+',
)

_EARLIEST_LATEST_RAW = re.compile(r"\b(?:earliest|latest)\(_time\)", re.IGNORECASE)
_STRFTIME = re.compile(r"\bstrftime\s*\(", re.IGNORECASE)

_PROHIBITED_CLAIMS = re.compile(
    r"\b("
    r"results?\s+(?:were\s+)?found|"
    r"found\s+\d+\s+(?:events?|results?)|"
    r"catalog[\s-]?approved|"
    r"governed\s+spl|"
    r"approved\s+for\s+execution|"
    r"execution\s+eligible|"
    r"was\s+executed|"
    r"executed\s+successfully"
    r")\b",
    re.IGNORECASE,
)


def lint_quoted_string_newlines(spl: str) -> list[str]:
    violations: list[str] = []
    for match in _QUOTED_STRING.finditer(spl):
        if "\n" in match.group(0) or "\r" in match.group(0):
            violations.append("quoted_string_contains_newline")
    return violations


def lint_windows_path_escaping(spl: str) -> list[str]:
    violations: list[str] = []
    for match in _UNESCAPED_WINDOWS_PATH.finditer(spl):
        violations.append(f"unescaped_windows_path_backslash:{match.group(0)[:48]}")
    return violations


def lint_strftime_for_time_fields(spl: str) -> list[str]:
    if not _EARLIEST_LATEST_RAW.search(spl):
        return []
    if _STRFTIME.search(spl):
        return []
    return ["earliest_or_latest_time_without_strftime"]


def _scrub_lab_disclaimers(text: str) -> str:
    scrubbed = (text or "").lower()
    for safe in (
        "not catalog-approved",
        "not catalog approved",
        "not governed",
        "not approved",
        "do not execute",
        "without soc review",
    ):
        scrubbed = scrubbed.replace(safe, "")
    return scrubbed


def lint_prohibited_claims(text: str) -> list[str]:
    if _PROHIBITED_CLAIMS.search(_scrub_lab_disclaimers(text)):
        return ["prohibited_results_or_approval_claim"]
    return []


def lint_draft_spl(spl: str, *, extra_text: str = "") -> list[str]:
    """Return lint violation ids for a draft SPL preview query."""
    violations: list[str] = []
    violations.extend(lint_quoted_string_newlines(spl))
    violations.extend(lint_windows_path_escaping(spl))
    violations.extend(lint_strftime_for_time_fields(spl))
    violations.extend(lint_prohibited_claims(spl))
    violations.extend(lint_prohibited_claims(extra_text))
    return violations
