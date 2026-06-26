"""Canonical HIL-required resolution for trace and rendered panels."""

from __future__ import annotations

from typing import Any

_HIL_REQUIRED_STATUSES = frozenset({"required", "missing_evidence_review", "execution_approval"})


def resolve_effective_hil_required(
    *,
    evidence_plan: dict[str, Any] | None = None,
    answer_contract: Any | None = None,
    human_review: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    live_data_request: bool = False,
    execution_authorized: bool = False,
    intent_requires_hil: bool = False,
) -> bool:
    """Single HIL gate for debug bundles and analyst-facing panels."""
    needs_hil = bool((evidence_plan or {}).get("needs_hil"))
    hil_status = ""
    if answer_contract is not None:
        hil_status = str(getattr(answer_contract, "hil_status", None) or "")
        if not hil_status and isinstance(answer_contract, dict):
            hil_status = str(answer_contract.get("hil_status") or "")
    review_required = bool((human_review or {}).get("required"))
    exec_status = str((execution or {}).get("status") or "").lower()
    execution_review_required = exec_status in {
        "blocked",
        "pending",
        "skipped",
        "denied",
    } and bool((execution or {}).get("block_reason") or review_required)
    return bool(
        needs_hil
        or intent_requires_hil
        or hil_status in _HIL_REQUIRED_STATUSES
        or review_required
        or execution_review_required
        or (live_data_request and not execution_authorized)
    )
