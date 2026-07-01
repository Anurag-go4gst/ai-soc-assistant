"""Filter internal orchestration verbs from analyst-facing guided steps."""

from __future__ import annotations

import re

_INTERNAL_STEP_MARKERS = re.compile(
    r"\b("
    r"draft[_\s-]?investigation[_\s-]?note|"
    r"generate[_\s-]?spl|"
    r"regenerate[_\s-]?spl|"
    r"explain|"
    r"show[_\s-]?sop|"
    r"saia_|"
    r"skill:spl_generation|"
    r"llm_role:"
    r")\b",
    re.IGNORECASE,
)

_PRIORITY_PREFIX = re.compile(r"^\s*P[1-4]\s*[—–-]\s*", re.IGNORECASE)


def is_internal_orchestration_step(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return True
    normalized = _PRIORITY_PREFIX.sub("", body).strip()
    return bool(_INTERNAL_STEP_MARKERS.search(normalized))


def filter_analyst_facing_steps(steps: list[str] | None) -> list[str]:
    """Drop planner/orchestration-only steps from user-visible lists."""
    if not steps:
        return []
    filtered: list[str] = []
    seen: set[str] = set()
    for item in steps:
        text = str(item or "").strip()
        if not text or is_internal_orchestration_step(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        filtered.append(text)
    return filtered
