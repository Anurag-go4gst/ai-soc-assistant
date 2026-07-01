from __future__ import annotations

from app.chat.coe_checklist_repair import (
    collapse_duplicate_soc_review_checklist_text,
    repair_duplicate_soc_review_checklist,
)
from app.schemas.responses import AnalystResponseEnvelope


def test_collapse_duplicate_checklist_sections_in_text() -> None:
    text = (
        "Investigate VPN failures.\n\n"
        "SOC review checklist:\n"
        "- Check geo\n"
        "- Review MFA\n\n"
        "SOC review checklist before execution:\n"
        "1. Check geo\n"
        "2. Validate account lockout"
    )
    out = collapse_duplicate_soc_review_checklist_text(text)
    assert out.lower().count("soc review checklist") == 1
    assert "Check geo" in out
    assert "Validate account lockout" in out


def test_repair_preserves_guidance_checklist_in_summary() -> None:
    envelope = AnalystResponseEnvelope(
        direct_answer_summary=(
            "VPN investigation guidance.\n\n"
            "SOC review checklist:\n"
            "- Check geo\n"
            "- Review MFA"
        ),
        analyst_checklist=["Check geo", "Review MFA"],
        recommended_actions=["Check geo"],
    )
    repaired, message = repair_duplicate_soc_review_checklist(
        envelope,
        "",
        path_type="guided_investigation",
    )
    assert repaired is not None
    summary = str(repaired.direct_answer_summary or "")
    assert "SOC review checklist" in summary
    assert "Check geo" in summary


def test_repair_strips_inline_checklist_when_structured_fields_own_items() -> None:
    envelope = AnalystResponseEnvelope(
        response_profile="spl_only",
        direct_answer_summary=(
            "VPN investigation guidance.\n\n"
            "SOC review checklist:\n"
            "- Check geo\n"
            "- Review MFA"
        ),
        analyst_checklist=["Check geo", "Review MFA"],
        recommended_actions=["Check geo"],
    )
    repaired, message = repair_duplicate_soc_review_checklist(envelope, "", path_type="spl_review")
    assert repaired is not None
    summary = str(repaired.direct_answer_summary or "")
    assert summary.lower().count("soc review checklist") == 0
    assert summary.startswith("VPN investigation guidance.")


def test_repair_leaves_single_checklist_unchanged() -> None:
    envelope = AnalystResponseEnvelope(
        direct_answer_summary="SOC review checklist:\n- One item only",
    )
    repaired, message = repair_duplicate_soc_review_checklist(envelope, "", path_type="spl_review")
    assert repaired is not None
    assert "One item only" in str(repaired.direct_answer_summary or "")
