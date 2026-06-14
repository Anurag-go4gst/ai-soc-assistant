"""Phase 3 — shadow-only LLM resource-plan proposal (never alters live dispatch)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.planner.llm_plan_bridge import bridge_trigger_match, propose_validated_llm_plan


@dataclass(frozen=True)
class ResourcePlanShadowResult:
    shadow_plan: dict[str, Any] | None = None
    deterministic_plan_source: str | None = None
    llm_called: bool = False
    promotion_blocked: bool = True
    skipped_reason: str | None = None
    provider_label: str | None = None

    def to_trace_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "shadow_only": True,
            "promotion_blocked": self.promotion_blocked,
            "llm_called": self.llm_called,
            "deterministic_plan_source": self.deterministic_plan_source,
            "skipped_reason": self.skipped_reason,
        }
        if self.shadow_plan is not None:
            payload["shadow_plan_source"] = self.shadow_plan.get("plan_source")
            payload["shadow_step_count"] = len(self.shadow_plan.get("steps") or [])
            payload["shadow_provenance"] = self.shadow_plan.get("provenance")
        if self.provider_label:
            payload["provider_label"] = self.provider_label
        return payload


def resource_plan_shadow_enabled() -> bool:
    """Shadow proposals run only when live synthesis is configured — never inline on planning."""
    return bool(
        settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def run_resource_plan_shadow(
    *,
    query: str,
    match_path: str | None,
    evidence_plan: dict[str, Any] | None,
    client: Any | None = None,
) -> ResourcePlanShadowResult:
    """Propose + validate a plan for trace/scorecard only; live ``resource_plan`` stays deterministic."""
    deterministic = None
    if isinstance(evidence_plan, dict):
        deterministic = evidence_plan.get("resource_plan")
    det_source = None
    if isinstance(deterministic, dict):
        det_source = str(deterministic.get("plan_source") or "deterministic")

    if not resource_plan_shadow_enabled():
        return ResourcePlanShadowResult(
            deterministic_plan_source=det_source,
            skipped_reason="shadow_disabled",
        )
    if not bridge_trigger_match(match_path):
        return ResourcePlanShadowResult(
            deterministic_plan_source=det_source,
            skipped_reason="match_path_not_eligible",
        )

    mcp_allowed = False
    action_mode = None
    if isinstance(evidence_plan, dict):
        mcp_allowed = bool(evidence_plan.get("mcp_allowed"))
        action_mode = str(evidence_plan.get("action_mode") or "") or None

    proposed = propose_validated_llm_plan(
        query=query,
        match_path=match_path,
        action_mode=action_mode,
        mcp_allowed=mcp_allowed,
        client=client,
        require_bridge_flags=False,
    )
    if proposed is None:
        return ResourcePlanShadowResult(
            deterministic_plan_source=det_source,
            llm_called=False,
            skipped_reason="no_valid_shadow_proposal",
        )

    shadow_dump = proposed.model_dump()
    return ResourcePlanShadowResult(
        shadow_plan=shadow_dump,
        deterministic_plan_source=det_source,
        llm_called=True,
        promotion_blocked=True,
    )
