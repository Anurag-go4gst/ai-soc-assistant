"""Safeguards for MCP/search result rows before evidence packaging (P0 hardening)."""

from __future__ import annotations

from typing import Any

from app.safeguards.prompt_injection_filter import filter_prompt_injection


def scan_mcp_preview_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Scan row field values for prompt-injection patterns; rows are not mutated."""
    sensitivity_flags: list[str] = []
    warnings: list[str] = []
    for row in rows:
        for value in row.values():
            if not isinstance(value, str):
                continue
            injection = filter_prompt_injection(value)
            if not injection.get("allowed", True):
                sensitivity_flags.append("prompt_injection_detected_in_mcp_result")
                warnings.append("mcp_result_prompt_injection_blocked")
                return rows, sorted(set(sensitivity_flags)), warnings
    return rows, [], []
