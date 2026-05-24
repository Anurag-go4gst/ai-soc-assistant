from __future__ import annotations

from typing import Any


def human_review(
    review_type: str,
    reason: str,
    reviewer_role: str,
    allowed_actions: list[str],
    safe_message_for_user: str,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "required": required,
        "review_type": review_type,
        "reason": reason,
        "reviewer_role": reviewer_role,
        "allowed_actions": allowed_actions,
        "safe_message_for_user": safe_message_for_user,
    }


def no_human_review() -> dict[str, Any]:
    return {
        "required": False,
        "review_type": "execution_approval",
        "reason": "policy_checks_passed",
        "reviewer_role": "analyst",
        "allowed_actions": [],
        "safe_message_for_user": "Execution policy checks passed for mock/local mode.",
    }
