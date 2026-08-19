"""Stub remediation plan findings and artifact metadata."""

from __future__ import annotations

from typing import Any


def finding_for_remediation_step(
    step_id: str,
    *,
    status: str,
    normalized: dict[str, Any],
    applied: list[str] | None = None,
) -> dict[str, Any] | None:
    del normalized, applied
    return {
        "headline_finding": f"Remediation — {step_id} ({status})",
        "headlines_by_status": {
            "QUEUED": f"Queued — {step_id}",
            "RUNNING": f"Running — {step_id}",
            "COMPLETE": f"Complete — {step_id}",
            "VALIDATED": f"Validated — {step_id}",
        },
        "attention_state": "NORMAL",
    }


def enrich_remediation_steps(
    steps: list[dict[str, Any]],
    *,
    normalized: dict[str, Any],
    applied: list[str],
) -> list[dict[str, Any]]:
    del normalized, applied
    return steps


def build_remediation_summary(*, selected_count: int, total_count: int) -> dict[str, Any]:
    return {
        "title": "Remediation summary",
        "steps_completed": selected_count,
        "steps_total": total_count,
        "plan_steps": f"{selected_count}/{total_count} selected",
        "metrics": [],
    }


def build_remediation_conclusion(*, normalized: dict[str, Any]) -> dict[str, Any]:
    del normalized
    return {
        "title": "Remediation approach",
        "headline": "Headline for remediation phase",
        "narrative_points": ["Narrative point"],
    }
