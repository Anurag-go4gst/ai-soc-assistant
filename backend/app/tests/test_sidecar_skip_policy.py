from __future__ import annotations

from app.llm.sidecar_skip_policy import should_skip_sidecar


_AUTHORITY_READY = {
    "effective_promotion_status": "authority_ready",
}


def test_exact_match_skips_only_when_promotion_lifecycle_ready() -> None:
    skip, reason = should_skip_sidecar(match_path="exact_105_question")
    assert skip is False
    assert reason is None

    skip, reason = should_skip_sidecar(
        match_path="exact_105_question",
        promotion_lifecycle_summary=_AUTHORITY_READY,
    )
    assert skip is True
    assert reason == "deterministic_exact_match_t0"


def test_near_exact_does_not_skip() -> None:
    skip, reason = should_skip_sidecar(match_path="near_105_question")
    assert skip is False
    assert reason is None


def test_blocked_sufficiency_mode_skips() -> None:
    skip, reason = should_skip_sidecar(sufficiency_mode="blocked_by_policy")
    assert skip is True
    assert reason == "t0_sufficiency_mode:blocked_by_policy"


def test_clarification_answer_mode_skips() -> None:
    skip, reason = should_skip_sidecar(answer_mode="clarification")
    assert skip is True
    assert reason == "t0_answer_mode:clarification"


def test_clarification_hil_skips() -> None:
    skip, reason = should_skip_sidecar(hil_status="clarification_required")
    assert skip is True
    assert reason == "hil_skip:clarification_required"


def test_out_of_registry_does_not_skip() -> None:
    skip, reason = should_skip_sidecar(match_path="out_of_registry")
    assert skip is False
    assert reason is None
