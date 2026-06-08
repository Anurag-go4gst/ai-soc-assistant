"""Backward-compatible lint facade for SOC-STD-SPL-001 draft quality."""

from __future__ import annotations

from app.spl.draft_quality import (
    STANDARD_ID,
    DraftQualityReport,
    QualityFinding,
    _scrub_lab_disclaimers,
    evaluate_draft_quality,
    lint_draft_spl,
)


def lint_quoted_string_newlines(spl: str) -> list[str]:
    report = evaluate_draft_quality(spl)
    return [item.rule_id for item in report.findings if item.rule_id.endswith("Q01")]


def lint_windows_path_escaping(spl: str) -> list[str]:
    report = evaluate_draft_quality(spl)
    return [item.rule_id for item in report.findings if item.rule_id.endswith("Q02")]


def lint_strftime_for_time_fields(spl: str) -> list[str]:
    report = evaluate_draft_quality(spl)
    return [item.rule_id for item in report.findings if item.rule_id.endswith("U02")]


def lint_prohibited_claims(text: str) -> list[str]:
    report = evaluate_draft_quality("", extra_text=text)
    return [item.rule_id for item in report.findings if item.rule_id.endswith("Q05")]


__all__ = [
    "STANDARD_ID",
    "DraftQualityReport",
    "QualityFinding",
    "_scrub_lab_disclaimers",
    "evaluate_draft_quality",
    "lint_draft_spl",
    "lint_prohibited_claims",
    "lint_quoted_string_newlines",
    "lint_strftime_for_time_fields",
    "lint_windows_path_escaping",
]
