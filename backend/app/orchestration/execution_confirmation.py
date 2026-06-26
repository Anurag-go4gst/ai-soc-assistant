"""Analyst confirm-or-update gate before MCP search execution."""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.orchestration.human_review import human_review
from app.safeguards.spl_validator import validate_spl


def confirmation_required() -> bool:
    return bool(settings.ai_soc_require_spl_execution_confirmation)


def build_execution_confirmation_review(
    *,
    normalized_spl: str,
    selected_mcp_tool: str,
    selected_mcp_server: str,
) -> dict[str, Any]:
    preview = normalized_spl.strip()
    if len(preview) > 240:
        preview = f"{preview[:237]}..."
    return human_review(
        review_type="spl_execution_confirmation",
        reason="analyst_confirmation_required",
        reviewer_role="analyst",
        allowed_actions=[
            "confirm_execution",
            "provide_updated_spl",
            "reject_execution",
        ],
        safe_message_for_user=(
            "Review the proposed search before it runs in Splunk. "
            f"Tool: {selected_mcp_tool} on {selected_mcp_server}. "
            f"Proposed SPL: {preview} "
            "Reply with Confirm to run it as-is, paste an updated SPL/query to replace it, "
            "or Reject to cancel."
        ),
        required=True,
        proposed_normalized_spl=normalized_spl,
        selected_mcp_tool=selected_mcp_tool,
        selected_mcp_server=selected_mcp_server,
    )


def build_updated_spl_revision_review(*, reject_reasons: list[str]) -> dict[str, Any]:
    reasons = ", ".join(reject_reasons) or "validation_failed"
    return human_review(
        review_type="spl_revision",
        reason="analyst_updated_spl_validation_failed",
        reviewer_role="analyst",
        allowed_actions=["provide_updated_spl", "confirm_execution", "reject_execution"],
        safe_message_for_user=(
            "The updated SPL did not pass safety checks. "
            f"Reasons: {reasons}. "
            "Please fix the query and try again, confirm the original proposed SPL, or reject execution."
        ),
        required=True,
    )


def build_execution_rejected_review() -> dict[str, Any]:
    return human_review(
        review_type="execution_approval",
        reason="analyst_rejected_execution",
        reviewer_role="analyst",
        allowed_actions=["reject_execution"],
        safe_message_for_user="Search execution was cancelled at analyst request.",
        required=False,
    )


def safe_validate_for_execution(spl: str) -> dict[str, Any]:
    """Deterministic SPL safety check immediately before MCP call."""
    return validate_spl(spl)


def resolve_execution_spl(
    *,
    spl_validation: dict[str, Any],
    execution_review_action: str | None,
    analyst_provided_spl: str | None,
    pending_execution: dict[str, Any] | None,
    require_confirmation: bool | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (spl_validation_to_execute, blocking_review)."""
    action = (execution_review_action or "").strip().lower()
    if action == "reject":
        return None, build_execution_rejected_review()

    if action == "update_spl":
        raw = (analyst_provided_spl or "").strip()
        if not raw:
            return None, build_updated_spl_revision_review(reject_reasons=["empty_spl"])
        validation = safe_validate_for_execution(raw)
        if not validation.get("approved") or not validation.get("normalized_spl"):
            return None, build_updated_spl_revision_review(
                reject_reasons=[str(item) for item in validation.get("reject_reasons") or ["validation_failed"]]
            )
        return validation, None

    if action == "confirm":
        pending_spl = str((pending_execution or {}).get("normalized_spl") or "").strip()
        current_spl = str(spl_validation.get("normalized_spl") or "").strip()
        target = pending_spl or current_spl
        if not target:
            return None, build_updated_spl_revision_review(reject_reasons=["normalized_spl_null"])
        validation = safe_validate_for_execution(target)
        if not validation.get("approved") or not validation.get("normalized_spl"):
            return None, build_updated_spl_revision_review(
                reject_reasons=[str(item) for item in validation.get("reject_reasons") or ["validation_failed"]]
            )
        return validation, None

    if confirmation_required() if require_confirmation is None else require_confirmation:
        return None, None
    validation = safe_validate_for_execution(str(spl_validation.get("normalized_spl") or ""))
    if not validation.get("approved"):
        return None, build_updated_spl_revision_review(
            reject_reasons=[str(item) for item in validation.get("reject_reasons") or ["validation_failed"]]
        )
    return validation, None
