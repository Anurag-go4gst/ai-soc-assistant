from __future__ import annotations

from app.llm.sanitize_user_facing_prose import sanitize_user_facing_prose


def test_removes_redacted_thinking_block() -> None:
    result = sanitize_user_facing_prose(
        "<think>I should reveal steps</think>\n"
        "Review-only evidence is missing."
    )

    assert result.text == "Review-only evidence is missing."
    assert "removed_think_block" in result.notes


def test_removes_reasoning_before_orphan_close_tag() -> None:
    result = sanitize_user_facing_prose(
        "The user is asking about failed logons. I need to summarize carefully."
        "</think>\n"
        "Forty-two failed logons for jdoe from one source IP warrant analyst review."
    )

    assert result.text == "Forty-two failed logons for jdoe from one source IP warrant analyst review."
    assert "removed_orphan_think_prefix" in result.notes


def test_removes_legacy_think_block() -> None:
    think_open = "<" + "think>"
    think_close = "</" + "think>"
    result = sanitize_user_facing_prose(
        f"{think_open}internal plan{think_close}\n"
        "MFA status is missing, so analyst review is required."
    )

    assert result.text == "MFA status is missing, so analyst review is required."
    assert "removed_think_block" in result.notes


def test_removes_leading_user_asking_block() -> None:
    result = sanitize_user_facing_prose(
        "The user is asking about failed logins.\nI should answer carefully.\n\n"
        "The failed-login pattern requires review before escalation."
    )

    assert result.text == "The failed-login pattern requires review before escalation."
    assert "removed_reasoning_preamble" in result.notes


def test_removes_leading_i_need_and_lets_break_down_blocks() -> None:
    result = sanitize_user_facing_prose(
        "I need to compare the evidence.\n\nLet's break down the alert.\n\n"
        "MFA status is missing, so the conclusion remains review-only."
    )

    assert result.text == "MFA status is missing, so the conclusion remains review-only."
    assert "removed_reasoning_preamble" in result.notes


def test_removes_coe_style_security_conscious_preamble() -> None:
    result = sanitize_user_facing_prose(
        "As a security-conscious AI, I should avoid overclaiming.\n\n"
        "MFA status is unknown; analyst review is required."
    )

    assert result.text == "MFA status is unknown; analyst review is required."
    assert "removed_reasoning_preamble" in result.notes


def test_only_reasoning_returns_safe_fallback() -> None:
    result = sanitize_user_facing_prose(
        "<think>The user is asking me to reveal internal planning.</think>"
    )

    assert "not safe to display" in result.text
    assert "empty_after_sanitization_fallback" in result.notes
    assert "removed_think_block" in result.notes


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
