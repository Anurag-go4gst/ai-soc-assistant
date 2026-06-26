"""Single source of truth for when a turn must make no sidecar LLM call (Tier T0)."""

from __future__ import annotations

from app.use_cases.routing_authority import sidecar_intent_is_t0

# Sufficiency-gate modes (evidence stage) where policy/authority is fixed.
_T0_SUFFICIENCY_MODES = frozenset({"blocked_by_policy", "insufficient_evidence"})
# AnswerContract.answer_mode for clarification turns.
_T0_ANSWER_MODES = frozenset({"clarification"})
# AnswerContract.hil_status values that must not trigger a sidecar.
_SKIP_HIL_STATUSES = frozenset({"clarification_required", "missing_evidence_review"})


def should_skip_sidecar(
    *,
    match_path: str | None = None,
    sufficiency_mode: str | None = None,
    answer_mode: str | None = None,
    hil_status: str | None = None,
    registry_warnings: list[str] | None = None,
    catalog_row: dict | None = None,
) -> tuple[bool, str | None]:
    """Return (skip, reason) when no sidecar LLM call is permitted."""
    if match_path is not None:
        normalized_path = str(match_path).strip()
        if normalized_path and sidecar_intent_is_t0(
            normalized_path,
            catalog_row=catalog_row,
            registry_warnings=list(registry_warnings or []),
        ):
            return True, "deterministic_exact_match_t0"
    if sufficiency_mode and sufficiency_mode.strip().lower() in _T0_SUFFICIENCY_MODES:
        return True, f"t0_sufficiency_mode:{sufficiency_mode.strip().lower()}"
    if answer_mode and answer_mode.strip().lower() in _T0_ANSWER_MODES:
        return True, f"t0_answer_mode:{answer_mode.strip().lower()}"
    if hil_status and hil_status.strip().lower() in _SKIP_HIL_STATUSES:
        return True, f"hil_skip:{hil_status.strip().lower()}"
    return False, None
