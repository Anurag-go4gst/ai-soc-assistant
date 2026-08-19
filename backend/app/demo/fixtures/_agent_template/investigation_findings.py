"""Stub investigation findings — implement per step_id."""

from __future__ import annotations

from typing import Any


def finding_for_investigation_step(
    step_id: str,
    *,
    status: str,
    applied: list[str] | None = None,
    agent_state: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    selected: bool = True,
) -> dict[str, Any] | None:
    if not selected or status.upper() == "SKIPPED":
        return None
    return {
        "headline_finding": f"Finding for {step_id} ({status})",
        "headlines_by_status": {
            "QUEUED": f"Queued — {step_id}",
            "RUNNING": f"Running — {step_id}",
            "COMPLETE": f"Complete — {step_id}",
        },
        "attention_state": "NORMAL",
        "evidence_sources": [],
    }
