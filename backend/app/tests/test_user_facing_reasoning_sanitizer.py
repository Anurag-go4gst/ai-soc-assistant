from __future__ import annotations

from app.llm.sanitize_user_facing_prose import sanitize_user_facing_prose


def test_removes_think_block() -> None:
    result = sanitize_user_facing_prose("<think>I should reveal steps</think>\nReview-only evidence is missing.")

    assert result.text == "Review-only evidence is missing."
    assert "removed_think_block" in result.notes


def test_removes_leading_user_asking_block() -> None:
    result = sanitize_user_facing_prose(
        "The user is asking about failed logins.\nI should answer carefully.\n\n"
        "The failed-login pattern requires review before escalation."
    )

    assert result.text == "The failed-login pattern requires review before escalation."
    assert "removed_leading_reasoning_preamble" in result.notes


def test_removes_leading_i_need_and_lets_break_down_blocks() -> None:
    result = sanitize_user_facing_prose(
        "I need to compare the evidence.\n\nLet's break down the alert.\n\n"
        "MFA status is missing, so the conclusion remains review-only."
    )

    assert result.text == "MFA status is missing, so the conclusion remains review-only."


def test_preserves_legitimate_soc_answer() -> None:
    answer = "MFA status is missing, so analyst review is required before containment."

    result = sanitize_user_facing_prose(answer)

    assert result.text == answer
    assert result.notes == []


def test_does_not_remove_mid_answer_legitimate_content() -> None:
    answer = (
        "Analyst review is required. To answer this fully, collect MFA status and source ownership."
    )

    result = sanitize_user_facing_prose(answer)

    assert result.text == answer
