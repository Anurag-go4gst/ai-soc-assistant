"""O5c — broaden-on-empty orchestration wiring.

When a primary governed search executes and returns zero rows, the
`broaden_scope_on_empty` recipe (O5a) offers a single bounded, LLM-proposed,
HIL-approved broadened retry. This module is the thin integration layer between
that recipe and the live execution node.

Governance and guarding:
- Activates ONLY when MCP execution actually ran AND
  `AI_SOC_LLM_SPL_FALLBACK_ENABLED` is on. Both are default-off, so the default
  pipeline behaviour is unchanged single-call — no new flag is introduced
  (reuses existing execution + LLM-fallback flags).
- The broadened query is LLM-proposed but advisory: it is generated through the
  existing governed `generate_llm_spl_fallback` path (relevance + quality +
  deterministic validation) and surfaced for analyst approval. It never
  auto-executes; approval rides the existing `pending_execution_confirmation`
  gate (B4), so the approved broadened SPL runs through the same MCP gate.
- Empty != failed. A still-empty broadened result is honest negative evidence;
  the recipe's `on_empty` is terminal, and re-broadening is blocked because the
  trigger only fires on a fresh turn (no incoming execution_review_action).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.orchestration.human_review import human_review
from app.orchestration.mcp_orchestration import (
    CallBudget,
    McpCallRecord,
    McpCallSpec,
    McpOrchestration,
)
from app.planner.recipe_registry import get_recipe
from app.spl.llm_fallback import generate_llm_spl_fallback

BROADEN_RECIPE_ID = "broaden_scope_on_empty"

_BROADEN_RELEVANCE_FEEDBACK = [
    "The primary governed search returned zero rows.",
    "Propose a broadened equivalent search: widen the time window within policy "
    "bounds or use an allowed alternative sourcetype. Do not change result caps "
    "or leave the allowlist.",
]


@dataclass
class BroadenDecision:
    review: dict[str, Any]
    orchestration: dict[str, Any]
    pending_execution_confirmation: dict[str, Any]
    proposed_spl: str


def broaden_recipe_active(selected_skill: str) -> bool:
    recipe = get_recipe(BROADEN_RECIPE_ID)
    return recipe is not None and selected_skill in recipe.eligible_skills


def should_attempt_broaden(
    *,
    selected_skill: str,
    execution: dict[str, Any] | None,
    has_incoming_review_action: bool,
) -> bool:
    """Trigger only on a fresh turn whose primary search executed empty."""
    if has_incoming_review_action:
        # A confirm/update/reject response is mid-flight; never re-broaden here
        # (this is also what blocks a second broaden after an approved retry).
        return False
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return False
    if not broaden_recipe_active(selected_skill):
        return False
    if not isinstance(execution, dict):
        return False
    if execution.get("status") != "executed":
        return False
    return int(execution.get("result_count") or 0) == 0


def _spl_hash(normalized_spl: str) -> str:
    return hashlib.sha256(normalized_spl.encode("utf-8")).hexdigest()[:16]


def _truncate(spl: str, limit: int = 240) -> str:
    spl = spl.strip()
    return f"{spl[:limit - 3]}..." if len(spl) > limit else spl


def build_spl_broaden_confirmation_review(
    *,
    primary_spl: str,
    proposed_spl: str,
    selected_mcp_tool: str,
    selected_mcp_server: str,
) -> dict[str, Any]:
    """The broaden-specific HIL: shows the empty-primary context and the
    LLM-proposed broadened SPL for the analyst to approve, edit, or reject."""
    return human_review(
        review_type="spl_broaden_confirmation",
        reason="primary_search_empty_broaden_proposed",
        reviewer_role="analyst",
        allowed_actions=[
            "confirm_execution",
            "provide_updated_spl",
            "reject_execution",
        ],
        safe_message_for_user=(
            "The primary search returned no results. A broadened search has been "
            "proposed (LLM-suggested, validated, not yet run). "
            f"Original: {_truncate(primary_spl)} "
            f"Proposed broadened: {_truncate(proposed_spl)} "
            f"Tool: {selected_mcp_tool} on {selected_mcp_server}. "
            "Reply Confirm to run the broadened search, paste an updated SPL to "
            "replace it, or Reject to keep the negative result."
        ),
        required=True,
        primary_normalized_spl=primary_spl,
        proposed_normalized_spl=proposed_spl,
        selected_mcp_tool=selected_mcp_tool,
        selected_mcp_server=selected_mcp_server,
    )


def _orchestration_envelope(
    *,
    trace_id: str,
    primary_execution: dict[str, Any],
    proposed_spl: str,
    selected_mcp_server: str,
    selected_mcp_tool: str,
) -> dict[str, Any]:
    recipe = get_recipe(BROADEN_RECIPE_ID)
    max_calls = recipe.max_calls if recipe is not None else 2
    primary_record = McpCallRecord(
        call_id="c1_primary_search",
        sequence=1,
        outcome="empty",
        result_count=0,
        result_envelope_ref=str(primary_execution.get("executed_spl") or "") or None,
    )
    next_call = McpCallSpec(
        call_id="c2_broadened_search",
        sequence=2,
        depends_on=["c1_primary_search"],
        purpose="LLM-proposed broadened search after empty primary; HIL-gated.",
        call_class="evidence_search",
        server=selected_mcp_server,
        tool=selected_mcp_tool,
        normalized_spl_hash=_spl_hash(proposed_spl),
        required_policy_checks=["r5_relevance", "source_resolve", "validate_spl", "allowlist", "approval"],
        requires_hil=True,
        approval_state="pending",
    )
    envelope = McpOrchestration(
        orchestration_id=f"{trace_id}:broaden",
        recipe_id=BROADEN_RECIPE_ID,
        status="awaiting_approval",
        call_budget=CallBudget(
            max_calls=max_calls, calls_planned=2, calls_started=1, calls_completed=1
        ),
        unresolved_evidence_keys=["broadened_search_rows"],
        calls=[primary_record],
        next_call=next_call,
        stop_reason=None,
    )
    return envelope.model_dump()


def maybe_build_broaden_decision(
    *,
    trace_id: str,
    user_query: str,
    execution: dict[str, Any],
) -> BroadenDecision | None:
    """Generate the broadened proposal and HIL, or None if nothing to offer.

    Caller is responsible for the activation guard (`should_attempt_broaden`).
    Returns None when no valid broadened candidate could be produced — in which
    case the honest empty result and its existing review stand.
    """
    primary_spl = str(execution.get("executed_spl") or "")
    server = str(execution.get("selected_mcp_server") or "")
    tool = str(execution.get("selected_mcp_tool") or "")
    if not primary_spl or not server or not tool:
        return None

    result = generate_llm_spl_fallback(
        user_query=user_query,
        relevance_feedback=list(_BROADEN_RELEVANCE_FEEDBACK),
        context={"prior_empty_spl": primary_spl},
    )
    if result is None or not result.approved:
        return None
    normalized = str((result.validation or {}).get("normalized_spl") or "").strip()
    if not normalized:
        return None
    # Do not offer an identical query as a "broadened" retry.
    if normalized == primary_spl.strip():
        return None

    review = build_spl_broaden_confirmation_review(
        primary_spl=primary_spl,
        proposed_spl=normalized,
        selected_mcp_tool=tool,
        selected_mcp_server=server,
    )
    pending = {
        "normalized_spl": normalized,
        "selected_mcp_server": server,
        "selected_mcp_tool": tool,
        "trace_id": trace_id,
        "selected_skill": None,
        "source": "broaden_scope_on_empty",
    }
    orchestration = _orchestration_envelope(
        trace_id=trace_id,
        primary_execution=execution,
        proposed_spl=normalized,
        selected_mcp_server=server,
        selected_mcp_tool=tool,
    )
    return BroadenDecision(
        review=review,
        orchestration=orchestration,
        pending_execution_confirmation=pending,
        proposed_spl=normalized,
    )
