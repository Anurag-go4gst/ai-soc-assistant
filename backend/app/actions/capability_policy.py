from __future__ import annotations

from pydantic import BaseModel, Field

ALLOWED_ACTION_TIERS = (1,)
BLOCKED_EXECUTION_ACTIONS = ("block_ip", "disable_user", "isolate_endpoint", "containment", "close_incident", "create_ticket")


class ActionCapability(BaseModel):
    current_tier: int
    tier_label: str
    allowed_actions: list[str] = Field(default_factory=list)
    unavailable_actions: list[str] = Field(default_factory=list)
    hil_required: bool
    audit_required: bool
    reason: str


def action_capability_for(
    use_case_id: str | None,
    severity_label: str | None,
    *,
    hil_required: bool | None = None,
) -> ActionCapability:
    allowed = ["summarize", "explain", "show_sop", "generate_spl", "draft_investigation_note"]
    unavailable = ["run_saved_search", "create_ticket", "block_ip", "disable_user", "isolate_endpoint"]
    return ActionCapability(
        current_tier=1,
        tier_label="Tier 1 - Prepare",
        allowed_actions=allowed,
        unavailable_actions=unavailable,
        hil_required=bool(hil_required) if hil_required is not None else False,
        audit_required=True,
        reason=f"Use case {use_case_id or 'unknown'} with severity {severity_label or 'unknown'} is limited to inform/prepare actions in this stage.",
    )
