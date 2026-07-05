"""Data-silence advisory gate — metadata zero-footprint before splunk_run_query."""
from __future__ import annotations

from typing import Any

from app.orchestration.human_review import human_review

DATA_SILENCE_REVIEW_TYPE = "data_silence_advisory"


def build_data_silence_gate_review(advisory: dict[str, Any]) -> dict[str, Any]:
    return human_review(
        review_type=DATA_SILENCE_REVIEW_TYPE,
        reason="data_silence_metadata_zero_footprint",
        reviewer_role="analyst",
        allowed_actions=["proceed_anyway", "broaden", "halt"],
        safe_message_for_user=(
            "Metadata for the scoped target shows no recent events. "
            "The metadata lookback window may lag the proposed search window. "
            "Proceed anyway to run the search, request a broadened search, or halt."
        ),
        required=True,
        data_silence_advisory=advisory,
    )


def build_data_silence_halt_review() -> dict[str, Any]:
    return human_review(
        review_type=DATA_SILENCE_REVIEW_TYPE,
        reason="data_silence_analyst_halt",
        reviewer_role="analyst",
        allowed_actions=["halt"],
        safe_message_for_user=(
            "Search halted: metadata indicated no target footprint and the analyst chose not to proceed."
        ),
        required=False,
        data_silence_note=True,
    )


def resolve_data_silence_at_gate(
    advisory: dict[str, Any] | None,
    *,
    execution_review_action: str | None,
) -> tuple[str, dict[str, Any] | None]:
    """Return (disposition, review). disposition: proceed | block | halt."""
    if not isinstance(advisory, dict) or not advisory.get("active"):
        return "proceed", None
    action = (execution_review_action or "").strip().lower()
    if action == "proceed_anyway":
        return "proceed", None
    if action == "broaden":
        return "proceed", None
    if action in {"halt", "reject"}:
        return "halt", build_data_silence_halt_review()
    return "block", build_data_silence_gate_review(advisory)
