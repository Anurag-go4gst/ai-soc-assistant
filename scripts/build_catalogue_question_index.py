#!/usr/bin/env python3
"""Reference index of the use-case catalogue and the 105 questions, and how they link.

Answers, in one place: what use cases exist, what questions exist, which use case
serves which question, and which entries are unbindable or artifact-less.

Deliberately GENERATED, not hand-maintained — a hand list of 65 use cases and 105
questions goes stale silently, which is how a "46 catalog use cases" literal
survived in both a test and the /knowledge page while the catalogue held 65.

  PYTHONPATH=backend:. python3 scripts/build_catalogue_question_index.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "evals" / "catalogue_question_index.json"
OUT_MD = ROOT / "docs" / "catalogue_and_questions.md"


def build() -> dict:
    from app.knowledge.mapping_exports import build_catalogue_question_index

    return build_catalogue_question_index()


def render_markdown(payload: dict) -> str:
    counts = payload["counts"]
    lines = [
        "# Catalogue and questions — reference index",
        "",
        "**Generated** by `scripts/build_catalogue_question_index.py`. Do not hand-edit;",
        "regenerate instead. Machine-readable copy: `docs/evals/catalogue_question_index.json`.",
        "",
        f"- Use cases: **{counts['use_cases']}** "
        f"({counts['use_cases_bindable']} bindable, {counts['use_cases_with_template']} with an SPL template)",
        f"- Questions: **{counts['questions']}** "
        f"({counts['questions_binding_a_use_case']} bind a use case)",
        "",
        "A use case with no `intent_patterns` is **unbindable by design** — the `sample_*`",
        "entries exist as SPL template-registry bindings, not as things user text can match.",
        "",
        "## Use cases",
        "",
        "| use case | skill | SPL template | bindable | serves a 105 question | patterns |",
        "|---|---|---|---|---|---|",
    ]
    for u in payload["use_cases"]:
        pats = ", ".join(f"`{p}`" for p in u["intent_patterns"][:4]) or "—"
        if len(u["intent_patterns"]) > 4:
            pats += f" (+{len(u['intent_patterns']) - 4})"
        lines.append(
            f"| `{u['use_case_id']}` | {u['primary_skill']} | "
            f"{'`' + u['default_spl_template'] + '`' if u['default_spl_template'] else '—'} | "
            f"{'yes' if u['bindable'] else 'no'} | {'yes' if u['binds_a_105_question'] else 'no'} | {pats} |"
        )
    lines += ["", "## Questions", "", "| ref | question | binds | coverage |", "|---|---|---|---|"]
    for q in payload["questions"]:
        lines.append(
            f"| `{q['question_ref']}` | {q['question']} | "
            f"{'`' + q['binds_use_case_id'] + '`' if q['binds_use_case_id'] else '—'} | "
            f"{q['bind_coverage_score'] if q['bind_coverage_score'] is not None else '—'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = build()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(f"use cases: {payload['counts']['use_cases']} | questions: {payload['counts']['questions']}")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
