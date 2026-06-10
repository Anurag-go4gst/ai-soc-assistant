"""Prompt-injection detection for untrusted text (T4.2 hardening).

Primary consumer is the MCP-results→evidence path (attacker-controlled Splunk
fields such as cmdline, url, user_agent). Patterns are deliberately tight to
avoid flagging legitimate SOC log values; additions must only ever make the
filter stricter.
"""

from __future__ import annotations

import re

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|all)\b.{0,20}\binstructions?\b", re.IGNORECASE),
    re.compile(r"\byou are now\b", re.IGNORECASE),
    re.compile(r"\bnew instructions?\s*:", re.IGNORECASE),
    re.compile(r"\b(system|assistant)\s*:\s*(override|ignore|you must|do anything)", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"<\|(system|user|assistant)\|>", re.IGNORECASE),
    re.compile(r"\[/?INST\]", re.IGNORECASE),
    re.compile(r"\breveal\b.{0,30}\bsystem prompt\b", re.IGNORECASE),
    re.compile(r"\bdo anything now\b", re.IGNORECASE),
)


def filter_prompt_injection(text: str) -> dict[str, object]:
    """Classify untrusted text; suspicious text must never reach an LLM prompt."""
    suspicious = any(pattern.search(text) for pattern in _INJECTION_PATTERNS)
    return {"allowed": not suspicious, "suspicious": suspicious}
