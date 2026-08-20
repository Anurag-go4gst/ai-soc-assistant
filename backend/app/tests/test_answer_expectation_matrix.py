from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_answer_expectation_matrix_covers_105_and_catalog() -> None:
    matrix_path = Path(__file__).resolve().parents[3] / "docs/evals/out/answer_expectation_matrix.json"
    if not matrix_path.is_file():
        # docs/evals/out/* is gitignored, so this artifact does not exist in a
        # fresh clone or worktree and the suite was red there for anyone who
        # had not run the generator.
        #
        # Deliberately NOT auto-generated from a fixture: running
        # scripts/generate_answer_expectation_matrix.py rewrites the tracked
        # goldens, and those have been hand-reconciled since they were last
        # generated (e.g. catalog.soc_generate_spl expects spl_generation with
        # the note "Reconciled to catalogue/runtime authority", which the
        # generator reverts to knowledge_recall / "Auto-generated shallow
        # expectation"). A test must not silently rewrite expectations.
        pytest.skip(
            "docs/evals/out/answer_expectation_matrix.json absent (gitignored). "
            "Generate with: PYTHONPATH=backend:. python3 "
            "scripts/generate_answer_expectation_matrix.py — note it also "
            "rewrites tracked goldens, so review its diff before committing."
        )
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    q_rows = [row for row in rows if row.get("row_kind") == "question_105"]
    c_rows = [row for row in rows if row.get("row_kind") == "use_case_catalog"]
    assert len(q_rows) == 105
    # Derived from the catalogue, not a literal. This asserted 46 while the
    # catalogue holds 65, so it failed for anyone who actually generated the
    # matrix — the literal silently went stale as use cases were added, and the
    # test only looked green because the artifact was usually absent.
    from app.use_cases.registry import load_use_case_catalog

    assert len(c_rows) == len(load_use_case_catalog())
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
