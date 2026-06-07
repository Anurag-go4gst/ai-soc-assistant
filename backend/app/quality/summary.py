"""Aggregate metrics for the answer-quality review dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.quality.store import list_chat_turns

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "docs/evals/out/answer_expectation_matrix.json"
GOLDEN_DIR = REPO_ROOT / "backend/app/evals/golden_answers"
EVAL_JSON = REPO_ROOT / "docs/evals/out/golden_answer_eval.json"


def _count_jsonl_cases(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.strip().startswith("#"):
            count += 1
    return count


def build_quality_summary() -> dict[str, Any]:
    turns = list_chat_turns(limit=10_000)
    total = len(turns)
    flagged = sum(1 for row in turns if row.get("quality_status") == "flagged")
    in_review = sum(1 for row in turns if row.get("quality_status") == "in_review")
    golden_candidates = sum(1 for row in turns if row.get("golden_candidate"))
    matrix_rows = 0
    if MATRIX_PATH.is_file():
        matrix_rows = len(json.loads(MATRIX_PATH.read_text(encoding="utf-8")).get("rows") or [])

    golden_coverage = {
        "tier0": _count_jsonl_cases(GOLDEN_DIR / "tier0_control_plane.jsonl"),
        "question_105": _count_jsonl_cases(GOLDEN_DIR / "question_105_golden.jsonl"),
        "use_case_catalog": _count_jsonl_cases(GOLDEN_DIR / "use_case_catalog_golden.jsonl"),
        "flagged_regressions": _count_jsonl_cases(GOLDEN_DIR / "flagged_regressions.jsonl"),
    }

    eval_summary: dict[str, Any] = {}
    if EVAL_JSON.is_file():
        payload = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
        eval_summary = {
            "overall_pass": payload.get("overall_pass"),
            "case_count": payload.get("case_count"),
            "failed_count": payload.get("failed_count"),
            "by_tier": payload.get("by_tier"),
        }

    flagged_rate = round(flagged / total, 4) if total else 0.0
    return {
        "total_turns": total,
        "flagged_turns": flagged,
        "in_review_turns": in_review,
        "golden_candidate_turns": golden_candidates,
        "flagged_rate": flagged_rate,
        "expectation_matrix_rows": matrix_rows,
        "golden_coverage": golden_coverage,
        "latest_golden_eval": eval_summary,
    }
