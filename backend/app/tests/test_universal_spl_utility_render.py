"""Phase 9 — concise SPL-first rendering for universal/template-free authoring."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.review_only_spl_renderer import (
    render_review_only_spl_answer,
    _is_universal_spl_utility,
)

_UNIVERSAL_SPL = (
    "index=<your_index> earliest=-24h latest=now\n"
    '| eval hour_of_day=strftime(_time,"%H")\n'
    '| eval day_of_week_num=strftime(_time,"%w")\n'
    '| where day_of_week_num IN ("0","6")\n'
    "| table _time hour_of_day day_of_week sourcetype host\n"
    "| head 100"
)


def _resp():
    return SimpleNamespace(
        severity_label="Not assigned from this question alone",
        analyst_checklist=["should not appear"],
        draft_spl_code="",
    )


def test_universal_family_detected():
    assert _is_universal_spl_utility(
        {"detection_family": "universal_timestamp_spl"}, None
    )
    assert not _is_universal_spl_utility({"detection_family": "windows_lockout"}, None)


def test_universal_answer_is_concise_spl_first():
    draft_preview = {
        "detection_family": "universal_timestamp_spl",
        "draft_spl": _UNIVERSAL_SPL,
    }
    out = render_review_only_spl_answer(
        analyst_response=_resp(), draft_preview=draft_preview
    )
    # SPL-first + concise
    assert out.startswith("Review-only universal SPL draft. This was not executed.")
    assert "index=<your_index>" in out
    assert "%w" in out
    # no SOC-heavy framing
    assert "Severity:" not in out
    assert "SOC review checklist" not in out
    assert "Required source-profile bindings" not in out
    assert "should not appear" not in out


def test_non_universal_keeps_full_soc_render():
    draft_preview = {
        "detection_family": "windows_account_lockout",
        "draft_spl": "index=<windows_index> | head 100",
    }
    out = render_review_only_spl_answer(
        analyst_response=_resp(), draft_preview=draft_preview
    )
    assert "Severity:" in out
    assert "SOC review checklist" in out
