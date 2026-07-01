from __future__ import annotations

from app.chat.explicit_run_spl_hil import apply_explicit_run_spl_hil_wiring
from app.chat.guidance_templates import build_spl_execution_refusal_guidance


def test_explicit_run_spl_hil_wiring_for_spl_review_path() -> None:
    review, execution = apply_explicit_run_spl_hil_wiring(
        user_query="Run the SPL and give me results.",
        path_type="spl_review",
        human_review={"required": False, "reason": "policy_checks_passed"},
        execution={"status": "skipped", "execution_intent": "none"},
    )
    assert review["required"] is True
    assert review["review_type"] == "execution_approval"
    assert review["reason"] == "explicit_run_spl_requires_hil"
    assert build_spl_execution_refusal_guidance() in review["safe_message_for_user"]
    assert execution["status"] == "requires_human_review"
    assert execution["block_reason"] == "explicit_run_spl_requires_hil"


def test_explicit_run_spl_hil_wiring_skips_unsafe_blocked_path() -> None:
    prior = {"required": True, "reason": "unsafe_action_blocked"}
    review, execution = apply_explicit_run_spl_hil_wiring(
        user_query="Run the SPL and give me results.",
        path_type="unsafe_blocked",
        human_review=prior,
        execution={"status": "blocked"},
    )
    assert review == prior
    assert execution["status"] == "blocked"


def test_explicit_run_spl_hil_wiring_noop_for_non_run_spl_query() -> None:
    prior = {"required": False, "reason": "policy_checks_passed"}
    review, execution = apply_explicit_run_spl_hil_wiring(
        user_query="How should SOC investigate VPN failures?",
        path_type="spl_review",
        human_review=prior,
        execution={"status": "skipped"},
    )
    assert review == prior
    assert execution["status"] == "skipped"
