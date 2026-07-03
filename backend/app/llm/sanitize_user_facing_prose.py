"""Conservative sanitizer for analyst-visible LLM prose.

This module is intentionally display-only. Do not run it before JSON extraction,
SPL validation, audit hashing, or any deterministic validator that must inspect
the raw model output honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_THINK_BLOCK = re.compile(r"<\s*think\b[^>]*>.*?<\s*/\s*think\s*>", re.IGNORECASE | re.DOTALL)
_LEADING_PREAMBLE = re.compile(
    r"^\s*(?:"
    r"the user is asking\b|"
    r"i need to\b|"
    r"let(?:'|’)s break down\b|"
    r"possible angles\b|"
    r"to answer this\b"
    r")",
    re.IGNORECASE,
)
_FINAL_MARKER = re.compile(r"\b(?:final answer|answer|analyst answer)\s*:\s*", re.IGNORECASE)


@dataclass(frozen=True)
class SanitizedUserFacingProse:
    text: str
    notes: list[str] = field(default_factory=list)


def sanitize_user_facing_prose(text: str) -> SanitizedUserFacingProse:
    """Strip common hidden-reasoning leakage before text reaches the analyst."""
    original = str(text or "")
    notes: list[str] = []
    sanitized = _THINK_BLOCK.sub("", original)
    if sanitized != original:
        notes.append("removed_think_block")

    sanitized, removed = _remove_leading_reasoning_preamble(sanitized)
    if removed:
        notes.append("removed_leading_reasoning_preamble")

    sanitized = _normalize_spacing(sanitized)
    return SanitizedUserFacingProse(text=sanitized, notes=notes)


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
