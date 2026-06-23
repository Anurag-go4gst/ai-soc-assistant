"""Advisory MCP tool-plan shadow for /chat traces (deterministic on live path)."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.connectors.mcp.mcp_rbac import resolve_mcp_rbac_role, session_role_for_mcp_gate
from app.connectors.mcp.mcp_tool_chronology import review_proposed_tool_chronology
from app.connectors.mcp.mcp_tool_planner import plan_tool_chronology


def mcp_tool_plan_shadow_enabled() -> bool:
    """Emit tool-plan shadow when control plane or MCP evidence is in play."""
    return bool(settings.control_plane_enabled)


def mcp_tool_plan_llm_advisory_enabled() -> bool:
    """Optional LLM proposal for shadow only — never alters live dispatch."""
    return bool(
        settings.control_plane_enabled
        and settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    )


def run_mcp_tool_plan_shadow(
    *,
    query: str,
    target_index: str | None = None,
    spl_approved: bool = False,
    session_role: str | None = None,
    needs_mcp: bool = False,
    needs_spl: bool = False,
    allow_llm_advisory: bool = True,
    llm_advisory_skip_reason: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Return advisory chronology metadata for control_plane_trace; None when skipped."""
    if not needs_mcp and not needs_spl:
        return None
    if not mcp_tool_plan_shadow_enabled() and not needs_mcp:
        return None

    # Use the same unscoped default as the execution gate (demo_analyst) so the
    # advisory shadow matches what the gate would actually permit; an explicit
    # session role still resolves normally.
    rbac_role = resolve_mcp_rbac_role(session_role_for_mcp_gate(session_role))
    spl_ok = bool(spl_approved)

    if allow_llm_advisory and mcp_tool_plan_llm_advisory_enabled():
        plan_payload = plan_tool_chronology(
            query,
            target_index=target_index,
            spl_approved=spl_ok,
            rbac_role=rbac_role,
            client=client,
        )
    else:
        plan = review_proposed_tool_chronology(
            None,
            target_index=target_index,
            spl_approved=spl_ok,
            rbac_role=rbac_role,
        )
        plan_payload = plan.to_dict()
        plan_payload["planner"] = {
            "llm_called": False,
            "llm_label": None,
            "llm_unservable": [],
            "llm_error": None,
            "skipped_reason": "live_path_deterministic_only"
            if allow_llm_advisory
            else (llm_advisory_skip_reason or "llm_advisory_disabled_for_turn"),
        }

    return {
        "shadow_only": True,
        "promotion_blocked": True,
        "rbac_role": rbac_role,
        "approved_tools": list(plan_payload.get("approved_tools") or []),
        "decision_source": plan_payload.get("decision_source"),
        "dropped": plan_payload.get("dropped") or [],
        "warnings": plan_payload.get("warnings") or [],
        "planner": plan_payload.get("planner") or {},
    }
