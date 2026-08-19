"""Stub normalized investigation spine — feeds remediation copy."""

from __future__ import annotations

from typing import Any


def build_normalized_investigation_state(
    *,
    applied: list[str],
    agent_state: dict[str, Any],
    outcome: dict[str, Any],
    investigation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    del applied, agent_state, outcome, investigation_steps
    return {
        "investigation_summary": {
            "title": "Investigation summary",
            "steps_completed": 0,
            "steps_total": 0,
            "metrics": [],
        },
        "investigation_conclusion": {
            "headline": "Investigation headline",
            "narrative_points": ["Point one"],
        },
        "outstanding_uncertainty": [],
        "missing_evidence": [],
        "affected_asset_ids": [],
        "anomalous_asset_ids": [],
        "patch_id": None,
        "patch_scope_asset_ids": [],
        "compromise_status": "not confirmed",
    }
