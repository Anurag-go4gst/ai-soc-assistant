"""Guided hybrid dispatch eligibility helper (shared with pipeline)."""

from __future__ import annotations

from typing import Any

from app.config import settings


def uses_guided_hybrid_dispatch_from_state(state: dict[str, Any]) -> bool:
    if not settings.control_plane_enabled:
        return False
    if not settings.ai_soc_guided_hybrid_investigation_enabled:
        return False
    planning = state.get("planning_decision")
    if not isinstance(planning, dict) or planning.get("path_type") != "guided_investigation":
        return False
    evidence = state.get("evidence_plan")
    if not isinstance(evidence, dict):
        return False
    if evidence.get("answer_mode") != "guided_investigation":
        return False
    return evidence.get("investigation_planning_enabled") is True
