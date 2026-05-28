"""Resolve question_ref / question text from Stage 3K-Q0 taxonomy markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from registries import TAXONOMY_PATH

_TABLE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|",
    re.MULTILINE,
)


@dataclass(frozen=True)
class TaxonomyRow:
    number: int
    question: str
    pattern_type: str
    question_ref: str


def normalize_question_ref(value: str) -> str:
    text = value.strip().lower()
    if text.startswith("q0."):
        return text
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise ValueError(f"Invalid question_ref: {value!r}")
    return f"q0.q{int(digits):03d}"


def load_taxonomy_rows(path: Path | None = None) -> list[TaxonomyRow]:
    taxonomy_path = path or TAXONOMY_PATH
    content = taxonomy_path.read_text(encoding="utf-8")
    rows: list[TaxonomyRow] = []
    for match in _TABLE_ROW.finditer(content):
        number = int(match.group(1))
        question = match.group(2).strip()
        pattern_type = match.group(4).strip()
        rows.append(
            TaxonomyRow(
                number=number,
                question=question,
                pattern_type=pattern_type,
                question_ref=f"q0.q{number:03d}",
            )
        )
    return rows


def resolve_question_input(
    *,
    question: str | None = None,
    question_ref: str | None = None,
    taxonomy_path: Path | None = None,
) -> tuple[str, str, str | None]:
    """Return (question_text, question_ref, pattern_type)."""
    rows = load_taxonomy_rows(taxonomy_path)
    by_ref = {row.question_ref: row for row in rows}
    by_num = {row.number: row for row in rows}

    if question_ref:
        ref = normalize_question_ref(question_ref)
        row = by_ref.get(ref)
        if row is None:
            num = int(ref.split(".")[-1].lstrip("q"))
            row = by_num.get(num)
        if row is None:
            raise ValueError(f"question_ref not found in taxonomy: {ref}")
        return row.question, row.question_ref, row.pattern_type

    if question:
        text = question.strip()
        for row in rows:
            if row.question.lower() == text.lower():
                return row.question, row.question_ref, row.pattern_type
        for row in rows:
            if text.lower() in row.question.lower() or row.question.lower() in text.lower():
                return row.question, row.question_ref, row.pattern_type
        return text, "q0.q_unresolved", None

    raise ValueError("Provide --question or --question-ref")
