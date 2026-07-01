"""HIL contract wiring for explicit run-SPL requests (distinct from unsafe_blocked)."""

from __future__ import annotations

from typing import Any

from app.chat.guidance_templates import (
    build_spl_execution_refusal_guidance,
    is_explicit_run_spl_query,
    is_unsafe_blocked_path,
)
from app.orchestration.human_review import human_review as build_human_review


def apply_explicit_run_spl_hil_wiring(
    *,
    user_query: str,
    path_type: str | None,
    human_review: dict[str, Any] | None,
    execution: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Force HIL + blocked execution for explicit run-SPL on spl_review paths."""
    if not is_explicit_run_spl_query(user_query):
        return human_review or {}, execution or {}
    if is_unsafe_blocked_path(path_type):
        return human_review or {}, execution or {}

    path = str(path_type or "")
    if path != "spl_review":
        return human_review or {}, execution or {}

    refusal = build_spl_execution_refusal_guidance()
    review = build_human_review(
        "execution_approval",
        "explicit_run_spl_requires_hil",
        "soc_analyst",
        ["approve_spl_execution", "cancel"],
        refusal,
        required=True,
    )
    exec_payload = dict(execution or {})
    exec_payload.update(
        {
            "status": "requires_human_review",
            "execution_intent": "spl_search",
            "block_reason": "explicit_run_spl_requires_hil",
            "tool_selection_status": "blocked",
            "tool_selection_reason": "explicit_run_spl_requires_hil",
            "execution_status_label": "not_executed",
            "executed_spl": None,
            "result_count": 0,
            "results_preview": [],
        }
    )
    return review, exec_payload
