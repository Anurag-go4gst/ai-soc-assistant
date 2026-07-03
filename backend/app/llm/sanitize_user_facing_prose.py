"""Conservative sanitizer for analyst-visible LLM prose.

This module is intentionally display-only. Do not run it before JSON extraction,
SPL validation, audit hashing, or any deterministic validator that must inspect
the raw model output honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_THINK_OPEN = r"<\s*(?:redacted_thinking|think)\b[^>]*>"
_THINK_CLOSE = r"<\s*/\s*(?:redacted_thinking|think)\s*>"
_THINK_BLOCK = re.compile(
    rf"{_THINK_OPEN}.*?{_THINK_CLOSE}",
    re.IGNORECASE | re.DOTALL,
)
_ORPHAN_THINK_CLOSE = re.compile(_THINK_CLOSE, re.IGNORECASE)
_THINK_OPEN_ONLY = re.compile(_THINK_OPEN, re.IGNORECASE)
_LEADING_PREAMBLE = re.compile(
    r"^\s*(?:"
    r"the user is asking\b|"
    r"i need to\b|"
    r"we need to\b|"
    r"let(?:'|’|`)s break down\b|"
    r"possible angles\b|"
    r"to answer this\b|"
    r"the scenario states\b|"
    r"i should\b|"
    r"this request involves\b|"
    r"as a security-conscious ai\b"
    r")",
    re.IGNORECASE,
)
_FINAL_MARKER = re.compile(r"\b(?:final answer|answer|analyst answer)\s*:\s*", re.IGNORECASE)
_EMPTY_FALLBACK = (
    "The model response was not safe to display because it contained internal reasoning. "
    "Please retry or use the deterministic answer."
)


@dataclass(frozen=True)
class SanitizedUserFacingProse:
    text: str
    notes: list[str] = field(default_factory=list)


def sanitize_user_facing_prose(text: str) -> SanitizedUserFacingProse:
    """Strip common hidden-reasoning leakage before text reaches the analyst."""
    original = str(text or "")
    notes: list[str] = []
    sanitized = original

    stripped_blocks = _THINK_BLOCK.sub("", sanitized)
    if stripped_blocks != sanitized:
        notes.append("removed_think_block")
        sanitized = stripped_blocks

    sanitized, removed_orphan = _remove_orphan_think_prefix(sanitized)
    if removed_orphan:
        notes.append("removed_orphan_think_prefix")

    sanitized, removed_preamble = _remove_leading_reasoning_preamble(sanitized)
    if removed_preamble:
        notes.append("removed_reasoning_preamble")

    sanitized = _normalize_spacing(sanitized)
    if not sanitized.strip():
        notes.append("empty_after_sanitization_fallback")
        sanitized = _EMPTY_FALLBACK

    return SanitizedUserFacingProse(text=sanitized, notes=notes)


def _remove_orphan_think_prefix(text: str) -> tuple[str, bool]:
    """Remove leading text through the first closing think tag when no opening tag precedes it."""
    close_match = _ORPHAN_THINK_CLOSE.search(text)
    if close_match is None:
        return text, False
    prefix = text[: close_match.start()]
    if _THINK_OPEN_ONLY.search(prefix):
        return text, False
    remaining = text[close_match.end() :].lstrip()
    return remaining, True


def _remove_leading_reasoning_preamble(text: str) -> tuple[str, bool]:
    remaining = text.lstrip()
    removed = False
    while remaining:
        marker = _FINAL_MARKER.search(remaining[:1200])
        first_paragraph, separator, rest = remaining.partition("\n\n")
        if not _LEADING_PREAMBLE.search(first_paragraph):
            break
        if marker:
            remaining = remaining[marker.end() :].lstrip()
        elif separator:
            remaining = rest.lstrip()
        else:
            remaining = ""
        removed = True
    return remaining, removed


def _normalize_spacing(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                collapsed.append("")
            blank = True
            continue
        collapsed.append(line.strip())
        blank = False
    return "\n".join(collapsed).strip()
