from __future__ import annotations

import json
from pathlib import Path


def test_answer_expectation_matrix_covers_105_and_catalog() -> None:
    matrix_path = Path(__file__).resolve().parents[3] / "docs/evals/out/answer_expectation_matrix.json"
    assert matrix_path.is_file(), "run scripts/generate_answer_expectation_matrix.py"
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    q_rows = [row for row in rows if row.get("row_kind") == "question_105"]
    c_rows = [row for row in rows if row.get("row_kind") == "use_case_catalog"]
    assert len(q_rows) == 105
    assert len(c_rows) == 46
    assert all(row.get("expected_outcome_category") for row in rows)


def test_shallow_golden_jsonl_files_exist() -> None:
    golden_dir = Path(__file__).resolve().parents[1] / "evals/golden_answers"
    q_path = golden_dir / "question_105_golden.jsonl"
    c_path = golden_dir / "use_case_catalog_golden.jsonl"
    fixture = Path(__file__).resolve().parents[1] / "evals/fixtures/control_plane_critical_flows.jsonl"
    assert q_path.is_file()
    assert c_path.is_file()
    assert fixture.is_file()
    assert sum(1 for line in q_path.read_text(encoding="utf-8").splitlines() if line.strip()) == 105
    assert sum(1 for line in c_path.read_text(encoding="utf-8").splitlines() if line.strip()) == 46
