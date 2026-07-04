"""Item 6.2 wire-up — attach pending action proposals to live /chat responses."""

from __future__ import annotations

from typing import Any, Mapping

from app.actions.action_lane import ActionProposal, propose_action
from app.actions.action_proposal_builder import CREATE_TICKET_TOOL, build_create_ticket_payload_from_state
from app.config import settings


def attach_live_action_proposals(
    state: Mapping[str, Any],
    *,
    trace_id: str | None,
) -> list[dict[str, Any]]:
    if not settings.ai_soc_action_lane_live_proposals_enabled:
        return []
    payload = build_create_ticket_payload_from_state(state)
    if payload is None:
        return []
    proposal = propose_action(
        tool_id=CREATE_TICKET_TOOL,
        payload=payload,
        trace_id=trace_id,
    )
    if proposal.status != "pending_approval":
        return []
    return [proposal.model_dump()]
